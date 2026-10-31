from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.flights import get_live_flights

router = APIRouter()


@router.get("/live")
def live_flights(limit: int = Query(3000, le=10000), db: Session = Depends(get_db)):
    """Latest position of every aircraft seen in the most recent window
    of data (one row per aircraft)."""
    return get_live_flights(db, limit=limit)
