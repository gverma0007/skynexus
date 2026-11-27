"""Anomalies query service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ml.anomaly import describe


def get_anomalies(
    db: Session,
    region_id: UUID | None = None,
    hours: int = 48,
    limit: int = 100,
) -> list[dict]:
    """Notable hours flagged by the z-score + Isolation Forest engine."""
    from app.core.config import get_settings, request_as_of
    if get_settings().DATA_MODE=='demo':
        import hashlib
        from app.services.series import get_series
        from app.ml.anomaly import score_region, STORE_THRESHOLD
        bundle=get_series(db)
        output=[]
        for rs in bundle.regions.values():
            if region_id and str(region_id)!=rs.region_id:continue
            for row in score_region(rs):
                if row['composite_score']<STORE_THRESHOLD:continue
                row.update(id=hashlib.sha256((rs.region_id+str(row['timestamp'])+row['feature_name']).encode()).hexdigest()[:24],region_name=rs.name,dataset_mode='demo')
                row['timestamp']=row['timestamp'].isoformat()
                row['summary']=describe(row)
                output.append(row)
        return sorted(output,key=lambda r:r['timestamp'],reverse=True)[:limit]
    sql = """
        SELECT a.id::text, a.region_id::text, r.name, a.timestamp, a.feature_name, a.observed_value,
               a.z_score, a.isolation_forest_score, a.composite_score, a.severity_label
        FROM anomaly_scores a JOIN regions r ON r.id = a.region_id
        WHERE a.timestamp <= COALESCE(CAST(:asof AS timestamptz),now()) AND a.computed_at <= COALESCE(CAST(:asof AS timestamptz),now()) AND a.timestamp >= COALESCE(CAST(:asof AS timestamptz),now()) - make_interval(hours => :hours) {region}
        ORDER BY a.timestamp DESC, a.composite_score DESC LIMIT :limit
    """.format(region="AND a.region_id = :rid" if region_id else "")
    params: dict = {"hours": hours, "limit": limit, "asof": request_as_of.get()}
    if region_id:
        params["rid"] = str(region_id)

    out = []
    for r in db.execute(text(sql), params).all():
        row = {
            "id": r[0],
            "region_id": r[1],
            "region_name": r[2],
            "timestamp": r[3].isoformat(),
            "feature_name": r[4],
            "observed_value": r[5],
            "z_score": r[6],
            "isolation_forest_score": r[7],
            "composite_score": r[8],
            "severity_label": r[9],
        }
        row["summary"] = describe(row)
        out.append(row)
    return out

