from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.anomalies import get_anomalies

router = APIRouter()


@router.get("")
def list_anomalies(
    region_id: UUID | None = None,
    hours: int = Query(48, ge=1, le=192),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Notable hours flagged by the z-score + Isolation Forest engine."""
    return get_anomalies(db, region_id=region_id, hours=hours, limit=limit)
