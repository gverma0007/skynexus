import json
import statistics
from datetime import timedelta
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.disruption import compute_all_disruptions
from app.services.satellites import live_positions
from app.services.series import get_series

router = APIRouter()


def _disruption_or_404(db: Session, region_id: str) -> dict:
    for d in compute_all_disruptions(db):
        if d["region_id"] == region_id:
            return d
    raise HTTPException(status_code=404, detail="Region not found")


@router.get("/regions")
def list_regions(db: Session = Depends(get_db)):
    """Every monitored region with its current disruption score."""
    return compute_all_disruptions(db)


@router.get("/regions/outline")
def region_outlines(db: Session = Depends(get_db)):
    """Boundary rings as [lat, lon] pairs, for the globe."""
    rows = db.execute(text("SELECT id::text, name, ST_AsGeoJSON(geom) FROM regions")).all()
    return [
        {"id": rid, "name": name,
         "ring": [[float(lat), float(lon)] for lon, lat in json.loads(gj)["coordinates"][0]]}
        for rid, name, gj in rows
    ]


@router.get("/regions/{region_id}")
def region_detail(region_id: UUID, db: Session = Depends(get_db)):
    return _disruption_or_404(db, str(region_id))


@router.get("/regions/{region_id}/history")
def region_history(region_id: UUID, hours: int = Query(48, ge=6, le=168), db: Session = Depends(get_db)):
    """Hourly aircraft, storm and event counts with a 'normal range' band.

    The band for each hour is mean +/- 1 std of the same hour of day over the
    baseline days (data older than 24 h), so the chart shows what is usual.
    """
    bundle = get_series(db)
    rs = bundle.regions.get(str(region_id))
    if rs is None:
        raise HTTPException(status_code=404, detail="Region not found")
    end_idx = len(bundle.hours) - 1
    base_idx = [i for i in range(0, end_idx - 24) if rs.aircraft[i] is not None]
    by_hod: dict[int, list[float]] = {}
    for i in base_idx:
        by_hod.setdefault(rs.hours[i].hour, []).append(rs.aircraft[i])

    points = []
    for i in range(max(0, end_idx - hours), end_idx + 1):
        vals = by_hod.get(rs.hours[i].hour, [])
        band = None
        if len(vals) >= 3:
            m, sd = statistics.fmean(vals), statistics.pstdev(vals)
            band = [round(max(0.0, m - sd), 1), round(m + sd, 1)]
        points.append({
            "time": rs.hours[i].isoformat(),
            "aircraft": rs.aircraft[i],
            "partial": i == end_idx,
            "storm": None if rs.storm[i] is None else round(rs.storm[i], 1),
            "events": rs.events[i],
            "normal_range": band,
        })
    return {"region_id": rs.region_id, "region_name": rs.name, "points": points,
            "baseline_hours": len(base_idx)}


@router.get("/regions/{region_id}/overhead")
def region_overhead(region_id: UUID, db: Session = Depends(get_db)):
    """Satellites whose ground point is inside the region right now."""
    rid = str(region_id)
    sats = [s for s in live_positions(db) if s["region_id"] == rid]
    by_cat: dict[str, int] = {}
    for s in sats:
        by_cat[s["category_label"]] = by_cat.get(s["category_label"], 0) + 1
    sats.sort(key=lambda s: (s["category"] != "station", s["altitude_km"]))
    return {"region_id": rid, "count": len(sats), "by_category": by_cat, "satellites": sats[:50]}


@router.get("/regions/{region_id}/forecast")
def region_forecast(region_id: UUID, horizon_hours: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    """Linear trend on the last 12 complete hours of air traffic, with a
    +/- 1 residual-std band. Deliberately simple and explainable."""
    bundle = get_series(db)
    rs = bundle.regions.get(str(region_id))
    if rs is None:
        raise HTTPException(status_code=404, detail="Region not found")
    end_idx = len(bundle.hours) - 1
    pts = [(i, rs.aircraft[i]) for i in range(end_idx - 12, end_idx) if i >= 0 and rs.aircraft[i] is not None]
    if len(pts) < 3:
        return {"region_id": rs.region_id, "region_name": rs.name, "points": [], "history": [],
                "method": "insufficient data"}
    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    resid = float(np.std(y - (slope * x + intercept)))
    out = []
    for h in range(0, horizon_hours + 1):
        xi = end_idx + h
        v = max(0.0, slope * xi + intercept)
        out.append({"time": (rs.hours[end_idx] + timedelta(hours=h)).isoformat(),
                    "value": round(v, 1), "low": round(max(0.0, v - resid), 1), "high": round(v + resid, 1)})
    return {
        "region_id": rs.region_id, "region_name": rs.name,
        "history": [{"time": rs.hours[i].isoformat(), "value": v} for i, v in pts],
        "points": out, "trend_per_hour": round(float(slope), 2), "method": "linear trend, last 12 h",
    }
