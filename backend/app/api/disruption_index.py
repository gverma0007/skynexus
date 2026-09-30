from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.disruption import compute_all_disruptions

router = APIRouter()


@router.get("")
def get_disruption_index(db: Session = Depends(get_db)):
    """Live per-region disruption index."""
    return compute_all_disruptions(db)
