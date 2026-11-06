"""Hourly anomaly engine: z-score + Isolation Forest per region.

For every region we build an hourly feature matrix over the 8-day window:

    [aircraft per hour, storm index, event count]

Baseline = all hours older than 24 h with data. For each of the most recent
complete hours we compute:

- z-score per feature against the baseline (std floored so quiet series do
  not explode), scaled 0-100 with |z| = 3 -> 100.
- Isolation Forest fitted on the baseline rows; decision_function < 0 means
  "easier to isolate than normal", rescaled 0-100.

composite = 0.5 * z_scaled + 0.5 * iforest_scaled.

Weather is ruled out first: a traffic *drop* during a storm (storm >= 50) is
labelled weather-explained and its severity is capped at "low".

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

from app.services.series import RegionSeries, get_series

logger = logging.getLogger("anomaly")

FEATURES = ["aircraft_per_hour", "storm_index", "event_count"]
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
    for i in range(upto):
        a, s = rs.aircraft[i], rs.storm[i]
        if a is None:
            continue
        idx.append(i)
        rows.append([a, s if s is not None else 0.0, float(rs.events[i])])
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
        base = X if len(X) > 0 else np.array([[100.0, 10.0, 0.0]])
        mean = base.mean(axis=0)
        std = np.maximum(base.std(axis=0), np.maximum(0.15 * np.abs(mean), [5.0, 5.0, 1.0]))
        model = None
    else:
        base = X[base_mask]
        mean = base.mean(axis=0)
        std = np.maximum(base.std(axis=0), np.maximum(0.10 * np.abs(mean), [2.0, 3.0, 0.5]))
        model = IsolationForest(n_estimators=100, contamination="auto", random_state=7)
        model.fit(base)

    recent = [(k, i) for k, i in enumerate(idx) if i >= end_idx - LOOKBACK_HOURS]
    out = []
    for k, i in recent:
        row = X[k]
        z = (row - mean) / std
        dom = int(np.argmax(np.abs(z)))
        z_dom = float(z[dom])
        z_scaled = float(min(100.0, abs(z_dom) / 3.0 * 100.0))

        # Multivariate compound deviation (L2 norm of feature deviations)
        norm_z = float(np.linalg.norm(z))
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
        # Weather correlation check: if traffic drops during heavy weather, mark as weather-explained
        if z[0] < -0.8 and row[1] >= 35.0:
            feature = "aircraft_per_hour (weather-explained)"
            sev = "low" if composite >= STORE_THRESHOLD else "normal"

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
    db.execute(text("DELETE FROM anomaly_scores WHERE timestamp < now() - interval '8 days'"))
    db.commit()
    logger.info("anomaly engine: %d notable rows written", written)
    return written


def describe(row: dict) -> str:
    feat = row["feature_name"]
    z = row.get("z_score") or 0
    direction = "above" if z > 0 else "below"
    if "&" in feat:
        return f"Compound anomaly ({feat}) with |z|={abs(z):.1f}"
    if feat.startswith("aircraft"):
        base = f"Air traffic {abs(z):.1f} standard deviations {direction} normal"
        return base + (", during a storm" if "weather" in feat else "")
    if feat == "storm_index":
        return f"Storm intensity {abs(z):.1f} standard deviations {direction} normal"
    return f"Unusual earthquake count ({int(row['observed_value'])} in one hour)"

