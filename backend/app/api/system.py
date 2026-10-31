"""Data-source health for the System page."""

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.services.system import get_system_health, switch_data_mode

router = APIRouter()


@router.get("/health")
def system_health(db: Session = Depends(get_db)):
    return get_system_health(db)


@router.get("/mode")
def get_mode():
    return {"data_mode": get_settings().DATA_MODE}


@router.post("/mode")
def set_mode(payload: dict = Body(...), db: Session = Depends(get_db)):
    mode = payload.get("mode")
    if mode not in ("live", "demo"):
        raise HTTPException(status_code=400, detail="mode must be 'live' or 'demo'")
    return switch_data_mode(db, mode)

