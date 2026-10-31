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
    sql = """
        SELECT a.id::text, a.region_id::text, r.name, a.timestamp, a.feature_name, a.observed_value,
               a.z_score, a.isolation_forest_score, a.composite_score, a.severity_label
        FROM anomaly_scores a JOIN regions r ON r.id = a.region_id
        WHERE a.timestamp >= now() - make_interval(hours => :hours) {region}
        ORDER BY a.timestamp DESC, a.composite_score DESC LIMIT :limit
    """.format(region="AND a.region_id = :rid" if region_id else "")
    params: dict = {"hours": hours, "limit": limit}
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

