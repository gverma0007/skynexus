"""Regional Disruption Index (0-100).

One score per region from three signals, each compared with that region's
own recent normal:

- Air traffic (40%): distinct aircraft per hour over the last 3 complete
  hours vs the same hours of day across the prior 7 days. Both surges and
  drops count (a drop is what an airspace closure looks like). Scored from
  the z-score: |z| <= 1 is normal (0), |z| = 4 or more is 100.
- Earthquakes / events (35%): magnitude-weighted points for the last 24 h,
  decaying with a 12 h time constant, minus half the region's usual daily
  background so quake-prone zones are not permanently flagged.
- Storm intensity (25%): latest storm index (0-100) at the region centre.

Bands (env-tunable): Calm < 20 <= Watch < 40 <= Elevated < 70 <= Critical.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.series import RegionSeries, SeriesBundle, get_series

WEIGHTS = {"flights": 0.40, "events": 0.35, "weather": 0.25}
RECENT_HOURS = 3
MIN_BASELINE_HOURS = 12

STATUS = {"normal": "Calm", "low": "Watch", "medium": "Elevated", "high": "Critical"}


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def severity_label(score: float) -> str:
    s = get_settings()
    if score >= s.severity_high:
        return "high"
    if score >= s.severity_medium:
        return "medium"
    if score >= s.severity_low:
        return "low"
    return "normal"


# ------------------------------------------------------------- components --
def flight_component(rs: RegionSeries, end_idx: int) -> dict:
    """end_idx is the index of the current (partial) hour; it is excluded."""
    recent_idx = [i for i in range(end_idx - RECENT_HOURS, end_idx)
                  if i >= 0 and rs.aircraft[i] is not None]
    base_idx = [i for i in range(0, max(0, end_idx - 24)) if rs.aircraft[i] is not None]
    coverage_days = round(len(base_idx) / 24.0, 1)
    if not recent_idx or len(base_idx) < MIN_BASELINE_HOURS:
        recent = statistics.fmean(rs.aircraft[i] for i in recent_idx) if recent_idx else None
        return {"score": 0.0, "warming_up": True, "recent": _r(recent), "expected": None,
                "pct_change": None, "z": None, "direction": "flat",
                "baseline_days": coverage_days}

    all_base = [rs.aircraft[i] for i in base_idx]
    expected_parts, std_parts = [], []
    for i in recent_idx:
        hod = rs.hours[i].hour
        same = [rs.aircraft[j] for j in base_idx if rs.hours[j].hour == hod]
        pool = same if len(same) >= 3 else all_base
        expected_parts.append(statistics.fmean(pool))
        std_parts.append(statistics.pstdev(pool) if len(pool) > 1 else 0.0)
    recent = statistics.fmean(rs.aircraft[i] for i in recent_idx)
    expected = statistics.fmean(expected_parts)
    std = max(statistics.fmean(std_parts), 0.1 * expected, 1.0)
    z = (recent - expected) / std
    pct = (recent - expected) / expected * 100.0 if expected > 0 else None
    score = clamp((abs(z) - 1.0) / 3.0 * 100.0)
    return {"score": round(score, 1), "warming_up": False, "recent": _r(recent),
            "expected": _r(expected), "pct_change": _r(pct), "z": _r(z, 2),
            "direction": "up" if z > 0.5 else "down" if z < -0.5 else "flat",
            "baseline_days": coverage_days}


def event_points(mag: float) -> float:
    if mag >= 6.0:
        return 70.0
    if mag >= 5.5:
        return 55.0
    if mag >= 5.0:
        return 40.0
    if mag >= 4.5:
        return 25.0
    if mag >= 4.0:
        return 15.0
    return 5.0


def event_component(events: list[dict], at: datetime) -> dict:
    """events: this region's events (any age within the 8-day window)."""
    window = [e for e in events if at - timedelta(hours=24) <= e["event_date"] <= at]
    points = sum(event_points(e["magnitude"]) *
                 math.exp(-((at - e["event_date"]).total_seconds() / 3600.0) / 12.0)
                 for e in window)
    older = [e for e in events if at - timedelta(days=8) <= e["event_date"] < at - timedelta(hours=24)]
    background = sum(event_points(e["magnitude"]) for e in older) / 7.0 * 0.5
    score = clamp(points - 0.5 * background)
    largest = max(window, key=lambda e: e["magnitude"], default=None)
    return {
        "score": round(score, 1),
        "count_24h": len(window),
        "max_magnitude": largest["magnitude"] if largest else None,
        "largest": _event_brief(largest, at) if largest else None,
    }


def weather_component(rs: RegionSeries, end_idx: int) -> dict:
    now_val = None
    for i in range(end_idx, max(-1, end_idx - 7), -1):
        if rs.storm[i] is not None:
            now_val = rs.storm[i]
            break
    week = [v for v in rs.storm[: max(0, end_idx - 24)] if v is not None]
    return {"score": round(clamp(now_val or 0.0), 1), "storm_now": _r(now_val),
            "storm_week_avg": _r(statistics.fmean(week)) if week else None}


# ---------------------------------------------------------------- combine --
def score_region(rs: RegionSeries, events: list[dict], end_idx: int, at: datetime) -> dict:
    f = flight_component(rs, end_idx)
    e = event_component(events, at)
    w = weather_component(rs, end_idx)
    composite = (f["score"] * WEIGHTS["flights"] + e["score"] * WEIGHTS["events"]
                 + w["score"] * WEIGHTS["weather"])
    return {"composite": round(composite, 1), "flights": f, "events": e, "weather": w}


def explain(name: str, s: dict) -> list[str]:
    f, e, w = s["flights"], s["events"], s["weather"]
    lines: list[str] = []
    if f["warming_up"]:
        lines.append(f"Air traffic baseline is still building ({f['baseline_days']} of 1+ days collected).")
    elif f["pct_change"] is not None and abs(f["pct_change"]) >= 10 and f["score"] > 0:
        word = "above" if f["pct_change"] > 0 else "below"
        lines.append(f"Air traffic is {abs(f['pct_change']):.0f}% {word} its normal for this time of day.")
    else:
        lines.append("Air traffic is within its normal range for this time of day.")
    if e["largest"]:
        lines.append(f"{e['count_24h']} earthquake{'s' if e['count_24h'] != 1 else ''} in 24 h; "
                     f"largest {e['largest']['label']}.")
    if w["storm_now"] is not None and w["storm_now"] >= 40:
        lines.append(f"Storm intensity is high ({w['storm_now']:.0f}/100).")
    if f.get("direction") == "down" and (w["storm_now"] or 0) >= 40:
        lines.append("Bad weather may explain the drop in air traffic.")
    return lines


def compute_all_disruptions(db: Session, bundle: SeriesBundle | None = None) -> list[dict]:
    bundle = bundle or get_series(db)
    end_idx = len(bundle.hours) - 1
    by_region: dict[str, list[dict]] = {}
    for ev in bundle.events:
        by_region.setdefault(ev["region_id"], []).append(ev)

    out = []
    for rid, rs in bundle.regions.items():
        evs = by_region.get(rid, [])
        now_s = score_region(rs, evs, end_idx, bundle.now)
        prev_s = (score_region(rs, evs, end_idx - 24, bundle.now - timedelta(hours=24))
                  if end_idx >= 48 else None)
        composite = now_s["composite"]
        sev = severity_label(composite)
        out.append({
            "region_id": rid,
            "region_name": rs.name,
            "lat": rs.lat,
            "lon": rs.lon,
            "composite_index": composite,
            "previous_index": prev_s["composite"] if prev_s else None,
            "change_24h": round(composite - prev_s["composite"], 1) if prev_s else None,
            "severity_label": sev,
            "status": STATUS[sev],
            "flight_anomaly_score": now_s["flights"]["score"],
            "event_relevance_score": now_s["events"]["score"],
            "weather_score": now_s["weather"]["score"],
            "components": {"flights": now_s["flights"], "events": now_s["events"],
                           "weather": now_s["weather"]},
            "explanation": explain(rs.name, now_s),
            "sparkline": _sparkline(rs, evs, end_idx),
        })
    out.sort(key=lambda d: d["composite_index"], reverse=True)
    return out


def _sparkline(rs: RegionSeries, evs: list[dict], end_idx: int) -> list[float | None]:  # noqa: ARG001
    """Aircraft per hour for the last 24 complete hours (None = no data)."""
    return [rs.aircraft[i] for i in range(max(0, end_idx - 24), end_idx)]


def _event_brief(e: dict, at: datetime) -> dict:
    age_h = (at - e["event_date"]).total_seconds() / 3600.0
    return {"id": e["id"], "magnitude": e["magnitude"], "description": e["description"],
            "event_date": e["event_date"].isoformat(), "hours_ago": round(max(age_h, 0), 1),
            "label": (e["description"] or e["event_type"]).replace(" earthquake — ", ", ")}


def _r(v: float | None, nd: int = 1) -> float | None:
    return None if v is None else round(float(v), nd)
