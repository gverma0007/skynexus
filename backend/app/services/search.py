"""Search service across regions and satellites."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.satellites import CATEGORY_LABELS


def search_entities(db: Session, q: str) -> dict:
    """Regions and satellites matching a name (or a NORAD number)."""
    like = f"%{q.strip()}%"
    regions = db.execute(text(
        "SELECT id::text, name FROM regions WHERE name ILIKE :q ORDER BY name LIMIT 8"
    ), {"q": like}).all()
    sats = db.execute(text(
        """
        SELECT norad_id, name, COALESCE(category, 'other') FROM satellites
        WHERE name ILIKE :q OR CAST(norad_id AS TEXT) = :exact
        ORDER BY (name ILIKE :prefix) DESC, name LIMIT 12
        """
    ), {"q": like, "exact": q.strip(), "prefix": f"{q.strip()}%"}).all()
    return {
        "regions": [{"id": r[0], "name": r[1]} for r in regions],
        "satellites": [
            {
                "norad_id": s[0],
                "name": s[1],
                "category": s[2],
                "category_label": CATEGORY_LABELS.get(s[2], "Other"),
            }
            for s in sats
        ],
    }

