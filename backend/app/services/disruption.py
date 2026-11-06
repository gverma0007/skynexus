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

WEIGHTS = {"flights": 0.35, "events": 0.30, "weather": 0.20, "satellites": 0.15}
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
def flight_component(rs: RegionSeries, end_idx: int, dev_info: dict | None = None) -> dict:
    """end_idx is the index of the current (partial) hour; it is excluded."""
    recent_idx = [i for i in range(end_idx - RECENT_HOURS, end_idx)
                  if i >= 0 and rs.aircraft[i] is not None]
    base_idx = [i for i in range(0, max(0, end_idx - 24)) if rs.aircraft[i] is not None]
    # Fallback to all prior completed hours if 24h prior baseline is still building
    if len(base_idx) < MIN_BASELINE_HOURS:
        base_idx = [i for i in range(0, max(0, end_idx - RECENT_HOURS)) if rs.aircraft[i] is not None]
    coverage_days = round(len(base_idx) / 24.0, 1)
    dev_score = float(dev_info.get("dev_score", 0.0)) if dev_info else 0.0

    if not recent_idx:
        return {"score": round(dev_score, 1), "warming_up": True, "recent": None, "expected": None,
                "pct_change": None, "z": None, "direction": "flat",
                "baseline_days": coverage_days,
                "week_mean": None, "week_pct_change": None, "week_z": None,
                "route_deviations": dev_info or {}}

    recent = statistics.fmean(rs.aircraft[i] for i in recent_idx)
    if len(base_idx) < 3:
        return {"score": round(dev_score, 1), "warming_up": True, "recent": _r(recent), "expected": None,
                "pct_change": None, "z": None, "direction": "flat",
                "baseline_days": coverage_days,
                "week_mean": None, "week_pct_change": None, "week_z": None,
                "route_deviations": dev_info or {}}

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

    # 7-day weekly deviation (up to 168 hours lookback)
    week_idx = [i for i in range(max(0, end_idx - 168), end_idx - RECENT_HOURS) if rs.aircraft[i] is not None]
    if len(week_idx) >= 12:
        week_mean = statistics.fmean(rs.aircraft[i] for i in week_idx)
        week_std = max(statistics.pstdev(rs.aircraft[i] for i in week_idx), 0.1 * week_mean, 1.0)
        week_z = (recent - week_mean) / week_std
        week_pct = (recent - week_mean) / week_mean * 100.0 if week_mean > 0 else None
        # Effective z balances diurnal hour-of-day expectation and weekly structural trend
        z_eff = 0.65 * z + 0.35 * week_z
    else:
        week_mean, week_std, week_z, week_pct = None, None, None, None
        z_eff = z

    vol_score = clamp((abs(z_eff) - 1.0) / 3.0 * 100.0)
    # Increase disruption score when aircraft route deviations are elevated in this zone
    score = clamp(max(vol_score, dev_score * 0.75) + dev_score * 0.25)
    return {"score": round(score, 1), "warming_up": False, "recent": _r(recent),
            "expected": _r(expected), "pct_change": _r(pct), "z": _r(z, 2),
            "direction": "up" if z > 0.5 else "down" if z < -0.5 else "flat",
            "baseline_days": coverage_days,
            "week_mean": _r(week_mean),
            "week_pct_change": _r(week_pct),
            "week_z": _r(week_z, 2),
            "route_deviations": dev_info or {}}


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


def satellite_component(sat_info: dict | None) -> dict:
    """Satellite density & orbital profile score (0-100)."""
    if not sat_info or sat_info.get("count", 0) == 0:
        return {
            "score": 0.0,
            "count": 0,
            "density": 0.0,
            "by_orbit": {"leo": 0, "meo": 0, "geo": 0},
            "by_category": {},
            "leo_earthobs": 0,
            "gnss_nav": 0,
        }

    count = sat_info.get("count", 0)
    density = sat_info.get("density", 0.0)
    by_orbit = sat_info.get("by_orbit", {"leo": 0, "meo": 0, "geo": 0})
    leo_earthobs = sat_info.get("leo_earthobs", 0)
    gnss_nav = sat_info.get("gnss_nav", 0)

    # 1. Surveillance / Observation intensity (LEO Earth Observation passes)
    obs_score = min(60.0, leo_earthobs * 15.0)

    # 2. GNSS Navigation constellation adequacy (MEO GNSS health)
    nav_gap = 30.0 if (gnss_nav == 0 and count > 0) else (15.0 if gnss_nav == 1 else 0.0)

    # 3. Density anomaly relative to typical orbital distribution (~10 sats / 100 sq deg)
    density_dev = clamp((density - 10.0) / 15.0 * 30.0)

    score = clamp(obs_score + nav_gap + density_dev)
    return {
        "score": round(score, 1),
        "count": count,
        "density": round(density, 2),
        "by_orbit": by_orbit,
        "by_category": sat_info.get("by_category", {}),
        "leo_earthobs": leo_earthobs,
        "gnss_nav": gnss_nav,
    }


# ---------------------------------------------------------------- combine --
def score_region(rs: RegionSeries, events: list[dict], end_idx: int, at: datetime,
                 sat_info: dict | None = None, dev_info: dict | None = None) -> dict:
    f = flight_component(rs, end_idx, dev_info=dev_info)
    e = event_component(events, at)
    w = weather_component(rs, end_idx)
    s = satellite_component(sat_info)
    composite = (f["score"] * WEIGHTS["flights"] + e["score"] * WEIGHTS["events"]
                 + w["score"] * WEIGHTS["weather"] + s["score"] * WEIGHTS["satellites"])
    return {"composite": round(composite, 1), "flights": f, "events": e, "weather": w, "satellites": s}


def explain(name: str, s: dict) -> list[str]:
    f, e, w = s["flights"], s["events"], s["weather"]
    sat = s.get("satellites", {})
    lines: list[str] = []
    if f["warming_up"]:
        lines.append(f"Air traffic baseline is still building ({f['baseline_days']} of 1+ days collected).")
    elif f["pct_change"] is not None and abs(f["pct_change"]) >= 10 and f["score"] > 0:
        word = "above" if f["pct_change"] > 0 else "below"
        lines.append(f"Air traffic is {abs(f['pct_change']):.0f}% {word} its normal for this time of day.")
    else:
        lines.append("Air traffic is within its normal range for this time of day.")

    # Flight route deviation context
    devs = f.get("route_deviations", {})
    if devs.get("significant_count", 0) > 0:
        lines.append(f"High flight route deviations detected ({devs['significant_count']} aircraft diverting up to {devs['max_km']:.0f} km off planned corridor).")
    elif devs.get("minor_count", 0) > 0:
        lines.append(f"Minor route diversions detected ({devs['minor_count']} aircraft off nominal route).")

    # Weekly flight deviation context
    if f.get("week_pct_change") is not None and abs(f["week_pct_change"]) >= 12 and not f["warming_up"]:
        w_dir = "above" if f["week_pct_change"] > 0 else "below"
        lines.append(f"Air traffic is {abs(f['week_pct_change']):.0f}% {w_dir} its 7-day weekly average.")

    if e["largest"]:
        lines.append(f"{e['count_24h']} earthquake{'s' if e['count_24h'] != 1 else ''} in 24 h; "
                     f"largest {e['largest']['label']}.")
    if w["storm_now"] is not None and w["storm_now"] >= 40:
        lines.append(f"Storm intensity is high ({w['storm_now']:.0f}/100).")
    if f.get("direction") == "down" and (w["storm_now"] or 0) >= 40:
        lines.append("Bad weather may explain the drop in air traffic.")

    # Satellite density and orbital context
    if sat.get("count", 0) > 0:
        by_orb = sat.get("by_orbit", {})
        orbits = []
        if by_orb.get("leo", 0) > 0:
            orbits.append(f"{by_orb['leo']} LEO")
        if by_orb.get("meo", 0) > 0:
            orbits.append(f"{by_orb['meo']} MEO")
        orbit_str = f" ({', '.join(orbits)})" if orbits else ""
        if sat.get("leo_earthobs", 0) >= 3:
            lines.append(f"Elevated LEO Earth-observation surveillance density ({sat['leo_earthobs']} passes overhead).")
        elif sat.get("score", 0) >= 30:
            lines.append(f"Satellite coverage density is elevated ({sat['count']} overhead{orbit_str}).")
        elif by_orb.get("meo", 0) >= 2:
            lines.append(f"Satellite coverage active: {sat['count']} overhead{orbit_str} with nominal navigation geometry.")
    return lines


def compute_all_disruptions(db: Session, bundle: SeriesBundle | None = None) -> list[dict]:
    from app.services.satellites import get_all_region_overhead
    from app.services.flights import get_all_region_flight_deviations
    bundle = bundle or get_series(db)
    end_idx = len(bundle.hours) - 1
    by_region: dict[str, list[dict]] = {}
    for ev in bundle.events:
        by_region.setdefault(ev["region_id"], []).append(ev)

    sat_overhead = get_all_region_overhead(db)
    flight_devs = get_all_region_flight_deviations(db)

    out = []
    for rid, rs in bundle.regions.items():
        evs = by_region.get(rid, [])
        sat_info = sat_overhead.get(rid)
        dev_info = flight_devs.get(rid)
        now_s = score_region(rs, evs, end_idx, bundle.now, sat_info=sat_info, dev_info=dev_info)
        prev_s = (score_region(rs, evs, end_idx - 24, bundle.now - timedelta(hours=24), sat_info=sat_info)
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
            "satellite_score": now_s["satellites"]["score"],
            "components": {"flights": now_s["flights"], "events": now_s["events"],
                           "weather": now_s["weather"], "satellites": now_s["satellites"]},
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
