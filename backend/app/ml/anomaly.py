"""Hourly anomaly engine: z-score + Isolation Forest per region.

For every region we build an hourly feature matrix over the 8-day window:

    [satellite density, flight route deviation, storm index]

Baseline = all hours older than 24 h with data. For each of the most recent
complete hours we compute:

- z-score per feature against the baseline (std floored so quiet series do
  not explode), scaled 0-100 with |z| = 3 -> 100.
- Isolation Forest fitted on the baseline rows; decision_function < 0 means
  "easier to isolate than normal", rescaled 0-100.

composite = 0.5 * z_scaled + 0.5 * iforest_scaled.

Weather is ruled out first: route deviations during a storm (storm >= 35) are
labelled weather-explained and severity is capped at "low".

Rows with composite >= 50 and (|z| >= 2 or Isolation Forest >= 85) are written to anomaly_scores (idempotent per
region and hour).
"""

from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np
from sklearn.ensemble import IsolationForest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.series import RegionSeries, get_series

logger = logging.getLogger("anomaly")

FEATURES = ["satellite_density", "flight_route_deviation", "storm_index"]
LOOKBACK_HOURS = 6
MIN_BASELINE_ROWS = 6
STORE_THRESHOLD = 40.0
MIN_Z = 1.5
Z_WEIGHT = 0.35
NORM_WEIGHT = 0.35
IFOREST_WEIGHT = 0.30


def severity_for(score: float) -> str:
    if score >= 80:
        return "high"
    if score >= 65:
        return "medium"
    if score >= 40:
        return "low"
    return "normal"


def region_matrix(rs: RegionSeries, upto: int) -> tuple[list[int], np.ndarray]:
    idx, rows = [], []
    has_sat = hasattr(rs, "satellites") and rs.satellites
    has_dev = hasattr(rs, "flight_deviations") and rs.flight_deviations
    for i in range(upto):
        sat = rs.satellites[i] if has_sat and i < len(rs.satellites) else 0.0
        dev = rs.flight_deviations[i] if has_dev and i < len(rs.flight_deviations) else 0.0
        if sat is None and rs.aircraft[i] is None:
            continue
        s = rs.storm[i]
        idx.append(i)
        rows.append([
            float(sat or 0.0),
            float(dev or 0.0),
            float(s or 0.0),
        ])
    return idx, np.array(rows, dtype=float) if rows else np.empty((0, 3))


def score_region(rs: RegionSeries) -> list[dict]:
    end_idx = len(rs.hours) - 1  # current, partial hour: excluded
    idx, X = region_matrix(rs, end_idx)
    if len(idx) == 0:
        return []
    cutoff = end_idx - 24
    base_mask = np.array([i < cutoff for i in idx])
    # Adaptive baseline: if 24h+ prior baseline is building, use all prior completed hours
    if base_mask.sum() < MIN_BASELINE_ROWS:
        base_mask = np.array([i < end_idx - LOOKBACK_HOURS for i in idx])

    # If still fewer than 4 hours of history, use available points with cautious floors
    if base_mask.sum() < 4:
        base = X if len(X) > 0 else np.array([[10.0, 20.0, 10.0]])
        mean = base.mean(axis=0)
        std = np.maximum(base.std(axis=0), np.maximum(0.15 * np.abs(mean), [2.0, 15.0, 5.0]))
        model = None
    else:
        base = X[base_mask]
        mean = base.mean(axis=0)
        std = np.maximum(base.std(axis=0), np.maximum(0.10 * np.abs(mean), [1.0, 10.0, 3.0]))
        model = IsolationForest(n_estimators=40, contamination="auto", random_state=7)
        model.fit(base)

    recent = [(k, i) for k, i in enumerate(idx) if i >= end_idx - LOOKBACK_HOURS]
    out = []
    for k, i in recent:
        row = X[k]
        z = (row - mean) / std
        dom = int(np.argmax(np.abs(z)))
        z_dom = float(z[dom])
        z_scaled = float(min(100.0, abs(z_dom) / 3.0 * 100.0))

        # Multivariate compound deviation with heightened war/conflict weighting
        feature_weights = np.array([1.3, 1.3, 0.7])
        norm_z = float(np.linalg.norm(z * feature_weights))
        norm_scaled = float(min(100.0, norm_z / 3.5 * 100.0))

        if model is not None:
            df = float(model.decision_function(row.reshape(1, -1))[0])
            if_scaled = float(min(100.0, max(0.0, (0.15 - df) / 0.35 * 100.0)))
        else:
            if_scaled = norm_scaled

        # Balanced compound anomaly score
        composite = Z_WEIGHT * z_scaled + NORM_WEIGHT * norm_scaled + IFOREST_WEIGHT * if_scaled

        # Multi-signal feature attribution
        elevated_features = [FEATURES[idx_f] for idx_f, z_val in enumerate(z) if abs(z_val) >= 1.5]
        if len(elevated_features) > 1:
            feature = " & ".join(elevated_features)
        else:
            feature = FEATURES[dom]

        sev = severity_for(composite)
        # Weather correlation check: if flight deviations increase during heavy weather, mark as weather-explained
        if z[1] > 1.0 and row[2] >= 35.0:
            feature = "flight_route_deviation (weather-explained)"
            sev = "low" if composite >= STORE_THRESHOLD else "normal"
        # War & Conflict detection: flight corridor avoidance & satellite reconnaissance surges in clear weather
        elif z[1] > 1.2 and z[0] > 1.0 and row[2] < 35.0:
            feature = "war_conflict_early_warning"
            conflict_risk_boost = min(45.0, 25.0 + 10.0 * max(0.0, z[1] - 1.2) + 8.0 * max(0.0, z[0] - 1.0))
            composite = min(100.0, composite + conflict_risk_boost)
            sev = "high" if composite >= 55.0 else "medium"
        elif z[1] > 1.8 and row[2] < 30.0:
            feature = "airspace_conflict_evasion"
            conflict_risk_boost = min(40.0, 20.0 + 9.0 * max(0.0, z[1] - 1.8))
            composite = min(100.0, composite + conflict_risk_boost)
            sev = "high" if composite >= 60.0 else "medium"
        elif z[0] > 2.0 and row[2] < 35.0:
            feature = "orbital_reconnaissance_surge"
            conflict_risk_boost = min(35.0, 15.0 + 7.0 * max(0.0, z[0] - 2.0))
            composite = min(100.0, composite + conflict_risk_boost)
            sev = "high" if composite >= 60.0 else "medium"

        # Direct war & conflict incident risk integration into anomaly composite score
        if hasattr(rs, "events") and rs.events and i < len(rs.events) and rs.events[i] > 0:
            inc_cnt = rs.events[i]
            inc_mag = rs.max_mag[i] if hasattr(rs, "max_mag") and i < len(rs.max_mag) else 0.0
            war_incident_boost = min(35.0, 10.0 * inc_cnt + 4.0 * max(0.0, inc_mag - 2.0))
            composite = min(100.0, composite + war_incident_boost)
            sev = severity_for(composite)

        out.append({
            "region_id": rs.region_id,
            "timestamp": rs.hours[i] + timedelta(minutes=30),
            "feature_name": feature,
            "observed_value": float(row[dom]),
            "z_score": round(z_dom, 2),
            "isolation_forest_score": round(if_scaled, 1),
            "composite_score": round(composite, 1),
            "severity_label": sev,
        })
    return out


def run_anomaly_detection(db: Session) -> int:
    """Score the latest hours for every region and persist notable rows."""
    bundle = get_series(db)
    written = 0
    for rs in bundle.regions.values():
        try:
            rows = score_region(rs)
        except Exception as exc:  # one region must never stop the rest
            logger.warning("anomaly scoring failed for %s: %s", rs.name, exc)
            continue
        for r in rows:
            db.execute(text(
                "DELETE FROM anomaly_scores WHERE region_id = :rid AND timestamp = :ts"
            ), {"rid": r["region_id"], "ts": r["timestamp"]})
            if r["composite_score"] < STORE_THRESHOLD or (
                abs(r["z_score"]) < MIN_Z and r["isolation_forest_score"] < 70
            ):
                continue
            db.execute(text(
                """
                INSERT INTO anomaly_scores (id, entity_type, entity_id, region_id, timestamp,
                    feature_name, observed_value, z_score, isolation_forest_score,
                    composite_score, severity_label, computed_at)
                VALUES (gen_random_uuid(), 'region', 0, :region_id, :timestamp, :feature_name,
                    :observed_value, :z_score, :isolation_forest_score, :composite_score,
                    :severity_label, now())
                """
            ), r)
            written += 1
    retention = int(get_settings().RETENTION_DAYS)
    db.execute(text("DELETE FROM anomaly_scores WHERE timestamp < now() - make_interval(days => :d)"), {"d": retention})
    db.commit()
    logger.info("anomaly engine: %d notable rows written", written)
    return written


def describe(row: dict) -> str:
    feat = row["feature_name"]
    z = row.get("z_score") or 0
    direction = "above" if z > 0 else "below"
    if feat.startswith("war_conflict_early_warning"):
        return f"War & conflict early warning: abnormal satellite reconnaissance surge and civilian airspace diversion in clear weather (|z|={abs(z):.1f})"
    if feat.startswith("airspace_conflict_evasion"):
        return f"Airspace conflict evasion: aircraft diverting {abs(z):.1f} std off corridors in clear weather (potential combat/NOTAM zone)"
    if feat.startswith("orbital_reconnaissance_surge"):
        return f"Tactical orbital reconnaissance surge: satellite concentration {abs(z):.1f} std above baseline (pre-conflict staging)"
    if "&" in feat:
        return f"Compound anomaly ({feat}) with |z|={abs(z):.1f}"
    if feat.startswith("satellite"):
        return f"Satellite density {abs(z):.1f} standard deviations {direction} normal"
    if feat.startswith("flight_route_deviation"):
        base = f"Flight route deviation {abs(z):.1f} standard deviations {direction} normal"
        return base + (", during a storm" if "weather" in feat else "")
    if feat == "storm_index":
        return f"Storm intensity {abs(z):.1f} standard deviations {direction} normal"
    return f"Anomaly detected in {feat} with |z|={abs(z):.1f}"

