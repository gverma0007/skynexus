"""Alerts: things worth a person's attention right now."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.alerts import get_active_alerts

router = APIRouter()


@router.get("")
def list_alerts(db: Session = Depends(get_db)):
    return get_active_alerts(db)
