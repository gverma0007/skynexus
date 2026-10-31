from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.search import search_entities

router = APIRouter()


@router.get("")
def search(q: str = Query(..., min_length=1, max_length=80), db: Session = Depends(get_db)):
    """Regions and satellites matching a name (or a NORAD number)."""
    return search_entities(db, q)
