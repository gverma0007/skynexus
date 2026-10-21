"""What-Changed reports: the last N hours vs the N hours before."""

from __future__ import annotations

import statistics
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.aviation import WhatChangedReport
from app.services.ai_explainer import get_ai_explanation
from app.services.disruption import score_region
from app.services.series import get_series


def _pct(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    if before <= 0:
        return 100.0 if after > 0 else 0.0
    return round((after - before) / before * 100.0, 1)


def _avg(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 1) if vals else None


def _sat_passes(db: Session, region_id: str, start, end) -> int:
    return db.execute(text(
        """
        SELECT COUNT(DISTINCT so.satellite_id)
        FROM satellite_observations so JOIN regions r ON r.id = :rid
        WHERE so.timestamp >= :a AND so.timestamp < :b
          AND so.position && r.geom
          AND ST_Contains(r.geom, ST_Force2D(so.position))
        """
    ), {"rid": region_id, "a": start, "b": end}).scalar() or 0


def build_metrics(db: Session, region_id: str, hours: int) -> dict | None:
    hours = max(1, min(int(hours), 72))
    bundle = get_series(db)
    rs = bundle.regions.get(str(region_id))
    if rs is None:
        return None
    end_idx = len(bundle.hours) - 1
    now = bundle.now
    after_start, before_start = now - timedelta(hours=hours), now - timedelta(hours=2 * hours)

    def window(series, a, b):
        return [v for h, v in zip(bundle.hours, series) if a <= h < b]

    # Complete hour buckets only: the current hour is still filling up.
    cur = bundle.hours[-1]
    a_h = cur - timedelta(hours=hours)
    b_h = cur - timedelta(hours=2 * hours)
    av_after = _avg(window(rs.aircraft, a_h, cur))
    av_before = _avg(window(rs.aircraft, b_h, a_h))
    wx_after = _avg(window(rs.storm, a_h, cur + timedelta(hours=1)))
    wx_before = _avg(window(rs.storm, b_h, a_h))

    evs = [e for e in bundle.events if e["region_id"] == rs.region_id]
    ev_after = [e for e in evs if after_start <= e["event_date"] <= now]
    ev_before = [e for e in evs if before_start <= e["event_date"] < after_start]
    largest = max(ev_after, key=lambda e: e["magnitude"], default=None)

    sats_after = _sat_passes(db, rs.region_id, after_start, now)
    sats_before = _sat_passes(db, rs.region_id, before_start, after_start)

    idx_now = score_region(rs, evs, end_idx, now)["composite"]
    idx_then = (score_region(rs, evs, end_idx - hours, after_start)["composite"]
                if end_idx - hours > 0 else None)

    covered = [v for v in window(rs.aircraft, b_h, cur) if v is not None]
    confidence = round(min(100.0, len(covered) / (2 * hours) * 100.0), 0)

    return {
        "region": {"id": rs.region_id, "name": rs.name},
        "window_hours": hours,
        "windows": {
            "before_start": before_start.isoformat(), "before_end": after_start.isoformat(),
            "after_start": after_start.isoformat(), "after_end": now.isoformat(),
        },
        "disruption_index": {"before": idx_then, "after": idx_now,
                             "delta": None if idx_then is None else round(idx_now - idx_then, 1)},
        "aviation_metrics": {
            "label": "Air traffic", "unit": "aircraft per hour",
            "before": av_before, "after": av_after, "delta_pct": _pct(av_before, av_after),
        },
        "events_metrics": {
            "label": "Earthquakes", "unit": "events",
            "before": len(ev_before), "after": len(ev_after),
            "delta_pct": _pct(len(ev_before), len(ev_after)),
            "largest": (largest["description"] or "").replace(" earthquake — ", ", ") if largest else None,
            "list": [{"description": e["description"], "magnitude": e["magnitude"],
                      "event_date": e["event_date"].isoformat()}
                     for e in sorted(ev_after, key=lambda e: -e["magnitude"])[:5]],
        },
        "weather_metrics": {
            "label": "Storm intensity", "unit": "0-100",
            "before": wx_before, "after": wx_after, "delta_pct": _pct(wx_before, wx_after),
        },
        "satellite_metrics": {
            "label": "Satellite passes", "unit": "distinct satellites",
            "before": sats_before, "after": sats_after, "delta_pct": _pct(sats_before, sats_after),
        },
        "confidence_pct": confidence,
    }


async def generate_report(db: Session, region_id: str, hours: int, persist: bool = True) -> dict | None:
    metrics = build_metrics(db, region_id, hours)
    if metrics is None:
        return None
    text_out, source = await get_ai_explanation(metrics)
    metrics["overall_assessment"] = text_out
    metrics["ai_source"] = source
    if persist:
        w = metrics["windows"]
        row = WhatChangedReport(
            region_id=metrics["region"]["id"], event_id=None,
            before_start=w["before_start"], before_end=w["before_end"],
            after_start=w["after_start"], after_end=w["after_end"],
            metrics_json=metrics, ai_explanation=text_out,
            confidence_pct=metrics["confidence_pct"], window_hours=metrics["window_hours"],
            ai_source=source,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        metrics["id"] = str(row.id)
        metrics["generated_at"] = row.generated_at.isoformat()
    return metrics


def report_to_dict(row: WhatChangedReport, region_name: str | None = None) -> dict:
    data = dict(row.metrics_json or {})
    data["id"] = str(row.id)
    data["generated_at"] = row.generated_at.isoformat() if row.generated_at else None
    data.setdefault("overall_assessment", row.ai_explanation)
    data.setdefault("ai_source", row.ai_source)
    if region_name:
        data.setdefault("region", {"id": str(row.region_id), "name": region_name})
    return data
