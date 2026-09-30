from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from app.core.db import get_db
from app.models.engine import AnomalyScore
from app.schemas.analysis import AnomalyScore as AnomalyScoreSchema

router = APIRouter()

@router.get("", response_model=List[AnomalyScoreSchema])
def get_anomalies(region_id: Optional[UUID] = None, db: Session = Depends(get_db)):
    query = db.query(AnomalyScore)
    if region_id:
        query = query.filter(AnomalyScore.region_id == region_id)
    anomalies = query.order_by(AnomalyScore.timestamp.desc()).limit(100).all()
    return anomalies
