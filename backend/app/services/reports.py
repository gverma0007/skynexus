"""What-Changed reports: the last N hours vs the N hours before."""

from __future__ import annotations

import statistics
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.aviation import WhatChangedReport
from app.services.ai_explainer import get_ai_explanation
from app.services.disruption import score_region
from app.services.flights import get_all_region_flight_deviations
from app.services.satellites import get_all_region_overhead
from app.services.series import compute_region_history, get_series


def _pct(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    if before <= 0:
        return 100.0 if after > 0 else 0.0
    return round((after - before) / before * 100.0, 1)


def _avg(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 1) if vals else None


def describe_patterns(metrics):
    """Descriptive comparisons of stored complete hours; no causal/predictive claim."""
    from datetime import datetime
    start=datetime.fromisoformat(metrics['windows']['after_start'])
    end=datetime.fromisoformat(metrics['windows']['after_end']).replace(minute=0,second=0,microsecond=0)
    points=[p for p in metrics['historical_data']['points'] if start<=datetime.fromisoformat(p['time'])<end]
    flags=[];run=longest=0;previous=None;reference=0;coincident=0
    for p in points:
        when=datetime.fromisoformat(p['time']);band=p.get('normal_range');value=p.get('aircraft')
        if value is not None and band:
            reference+=1
        outside=value is not None and band and (value<band[0] or value>band[1])
        if outside:
            run=run+1 if previous is not None and when-previous==timedelta(hours=1) else 1
            longest=max(longest,run)
            coincident+=int(p.get('storm') is not None and p['storm']>=40)
            flags.append({'time':p['time'],'direction':'below' if value<band[0] else 'above','aircraft':value,'reference_band':band,'storm':p.get('storm')})
        else:run=0
        previous=when
    observed=sum(p.get('aircraft') is not None for p in points)
    return {'method':'descriptive_reference_band_comparison','baseline_hours':metrics['historical_data']['baseline_hours'],
            'complete_hours':len(points),'observed_hours':observed,'missing_hours':len(points)-observed,
            'reference_band_hours':reference,'below_band_hours':sum(f['direction']=='below' for f in flags),
            'above_band_hours':sum(f['direction']=='above' for f in flags),'longest_run_outside_band_hours':longest,
            'weather_coincident_outside_band_hours':coincident,'flagged_hours':flags,
            'limitations':['The reference band is a descriptive hour-of-day mean plus/minus one standard deviation, not a calibrated anomaly threshold.',
                           'Reference data ends 24 hours before the assessment; it can overlap a longer comparison window. This is not heldout evaluation.',
                           'Weather coincidence and repeated deviations do not establish a cause.']}


def _sat_passes(db: Session, region_id: str, start, end) -> int:
    return db.execute(text(
        """
        SELECT COUNT(DISTINCT so.satellite_id)
        FROM satellite_observations so JOIN regions r ON r.id = :rid
        WHERE so.timestamp >= :a AND so.timestamp < :b
          AND so.source = :source
          AND so.position && r.geom
          AND ST_Contains(r.geom, ST_Force2D(so.position))
        """
    ), {"rid": region_id, "a": start, "b": end, "source": "demo_dataset" if __import__("app.core.config", fromlist=["get_settings"]).get_settings().DATA_MODE == "demo" else "celestrak"}).scalar() or 0


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
    av_week = _avg(window(rs.aircraft, cur - timedelta(days=7), cur))
    wx_after = _avg(window(rs.storm, a_h, cur + timedelta(hours=1)))
    wx_before = _avg(window(rs.storm, b_h, a_h))

    evs = [e for e in bundle.events if e["region_id"] == rs.region_id]
    ev_after = [e for e in evs if after_start <= e["event_date"] <= now]
    ev_before = [e for e in evs if before_start <= e["event_date"] < after_start]
    largest = max(ev_after, key=lambda e: e["magnitude"], default=None)

    sats_after = _sat_passes(db, rs.region_id, after_start, now)
    sats_before = _sat_passes(db, rs.region_id, before_start, after_start)

    sat_overhead = get_all_region_overhead(db)
    flight_devs = get_all_region_flight_deviations(db)
    sat_info = sat_overhead.get(str(region_id))
    dev_info = flight_devs.get(str(region_id))

    idx_now = score_region(rs, evs, end_idx, now, sat_info=sat_info, dev_info=dev_info)["composite"]
    idx_then = (score_region(rs, evs, end_idx - hours, after_start, sat_info=sat_info)["composite"]
                if end_idx - hours > 0 else None)

    hist = compute_region_history(bundle, str(region_id), hours=min(hours * 2, 168))
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
            "week_avg": av_week, "week_delta_pct": _pct(av_week, av_after),
        },
        "flight_deviations": {
            "label": "Flight corridor deviations",
            "active_routes": dev_info.get("count", 0) if dev_info else 0,
            "deviating_flights": dev_info.get("deviating_count", 0) if dev_info else 0,
            "significant_deviations": dev_info.get("significant_count", 0) if dev_info else 0,
            "max_deviation_km": dev_info.get("max_km", 0.0) if dev_info else 0.0,
            "avg_deviation_km": dev_info.get("avg_km", 0.0) if dev_info else 0.0,
            "deviation_score": dev_info.get("dev_score", 0.0) if dev_info else 0.0,
        },
        "events_metrics": {
            "label": "Natural hazard events", "unit": "incidents",
            "before": len(ev_before), "after": len(ev_after),
            "delta_pct": _pct(len(ev_before), len(ev_after)),
            "largest": (largest["description"] or "").replace(" earthquake — ", ", ") if largest else None,
            "list": [{"description": (e["description"] or "").replace(" earthquake — ", ", "), "magnitude": e["magnitude"],
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
        "historical_data": {
            "baseline_hours": hist.get("baseline_hours", 0) if hist else 0,
            "points": [
                {
                    "time": p["time"],
                    "aircraft": p["aircraft"],
                    "storm": p["storm"],
                    "events": p["events"],
                    "normal_range": p["normal_range"],
                }
                for p in (hist["points"] if hist else [])
            ],
        },
        "confidence_pct": confidence,
        "data_coverage_pct": confidence,
        "confidence_definition": "Legacy field measures observation coverage, not causal confidence",
        "evidence_support": "unvalidated_association",
        "limitations": ["Correlation does not establish causation", "Satellite positions are propagated predictions", "Unknown routes do not establish diversion"],
        "method_version": "research-3.0",
        "dataset_mode": __import__("app.core.config", fromlist=["get_settings"]).get_settings().DATA_MODE,
    }


async def generate_report(db: Session, region_id: str, hours: int, persist: bool = True, owner_session: str | None = None) -> dict | None:
    metrics = build_metrics(db, region_id, hours)
    if metrics is None:
        return None
    import hashlib, json
    from datetime import datetime
    from app.services.evidence import collect_evidence
    from app.services.exposure import regional_exposures
    after_start=datetime.fromisoformat(metrics['windows']['after_start'])
    after_end=datetime.fromisoformat(metrics['windows']['after_end'])
    metrics['source_evidence']=collect_evidence(db,region_id,after_start,after_end,metrics['dataset_mode'])
    metrics['exposures']=regional_exposures(db,region_id,metrics['dataset_mode'],after_end)
    metrics['alternative_explanations']=[{'explanation':'Environmental conditions','support':'Evaluate corridor/asset-specific observations; a region-centre reading alone is insufficient.'},{'explanation':'Feed coverage or collection change','support':'Review source freshness and missing measurements before interpreting a traffic drop.'},{'explanation':'Documented operational restrictions','support':'Requires an attributed restriction matching this place and time; proximity alone is insufficient.'}]
    metrics['pattern_analysis']=describe_patterns(metrics)
    metrics['dataset_hash']=hashlib.sha256(json.dumps(metrics,sort_keys=True,default=str).encode()).hexdigest()
    metrics['provenance']={'analysis_window':metrics['windows'],'baseline_hours':metrics['historical_data']['baseline_hours'],'inputs':['aircraft observations','weather observations','typed natural hazard events','propagated satellite positions'],'baseline_target_days':30,'validated_forecast':False}
    text_out, source = await get_ai_explanation(metrics)
    metrics["overall_assessment"] = text_out
    metrics["ai_source"] = source
    if persist:
        w = metrics["windows"]
        row = WhatChangedReport(
            region_id=metrics["region"]["id"], event_id=None, owner_session=owner_session,
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
