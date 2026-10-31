from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.stats import get_system_stats

router = APIRouter()


@router.get("")
def stats(db: Session = Depends(get_db)):
    """Headline numbers for the top strip."""
    return get_system_stats(db)
