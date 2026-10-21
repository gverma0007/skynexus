from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.ml.anomaly import describe

router = APIRouter()


@router.get("")
def list_anomalies(region_id: UUID | None = None, hours: int = Query(48, ge=1, le=192),
                   limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    """Notable hours flagged by the z-score + Isolation Forest engine."""
    sql = """
        SELECT a.id::text, a.region_id::text, r.name, a.timestamp, a.feature_name, a.observed_value,
               a.z_score, a.isolation_forest_score, a.composite_score, a.severity_label
        FROM anomaly_scores a JOIN regions r ON r.id = a.region_id
        WHERE a.timestamp >= now() - make_interval(hours => :hours) {region}
        ORDER BY a.timestamp DESC, a.composite_score DESC LIMIT :limit
    """.format(region="AND a.region_id = :rid" if region_id else "")
    params = {"hours": hours, "limit": limit}
    if region_id:
        params["rid"] = str(region_id)
    out = []
    for r in db.execute(text(sql), params).all():
        row = {"id": r[0], "region_id": r[1], "region_name": r[2], "timestamp": r[3].isoformat(),
               "feature_name": r[4], "observed_value": r[5], "z_score": r[6],
               "isolation_forest_score": r[7], "composite_score": r[8], "severity_label": r[9]}
        row["summary"] = describe(row)
        out.append(row)
    return out
