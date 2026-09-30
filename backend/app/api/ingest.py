"""Endpoints for triggering and observing live data ingestion."""

import threading
import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import get_db, SessionLocal
from app.data import live_connectors

router = APIRouter()

_state: dict = {
    "running": False,
    "last_finished": None,
    "last_summary": None,
    "last_error": None,
    "duration_s": None,
}
_lock = threading.Lock()


def _run_cycle(steps: int) -> None:
    start = time.time()
    try:
        summary = live_connectors.run_live_ingestion(steps=steps)
        _state["last_summary"] = summary
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = str(exc)
    finally:
        _state["running"] = False
        _state["last_finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _state["duration_s"] = round(time.time() - start, 1)


@router.post("/live")
def trigger_live_ingestion(steps: int = 6):
    """Kick off a live ingestion cycle in the background."""
    with _lock:
        if _state["running"]:
            return {"status": "already_running", "state": _state}
        _state["running"] = True
    thread = threading.Thread(target=_run_cycle, args=(steps,), daemon=True)
    thread.start()
    return {"status": "started", "state": _state}


@router.get("/status")
def ingestion_status():
    """Last run summary + current table counts."""
    db = SessionLocal()
    try:
        counts = {
            "flight_observations": db.scalar(
                text("SELECT COUNT(*) FROM flight_observations")
            ),
            "satellite_observations": db.scalar(
                text("SELECT COUNT(*) FROM satellite_observations")
            ),
            "weather_observations": db.scalar(
                text("SELECT COUNT(*) FROM weather_observations")
            ),
            "events": db.scalar(text("SELECT COUNT(*) FROM events")),
        }
        newest = {
            "flights": str(
                db.scalar(text("SELECT MAX(timestamp) FROM flight_observations"))
            ),
            "satellites": str(
                db.scalar(text("SELECT MAX(timestamp) FROM satellite_observations"))
            ),
            "weather": str(
                db.scalar(text("SELECT MAX(timestamp) FROM weather_observations"))
            ),
            "events": str(db.scalar(text("SELECT MAX(event_date) FROM events"))),
        }
        source_rows = db.execute(
            text(
                """
                SELECT 'flights' AS domain, source, COUNT(*) AS n,
                       MAX(timestamp) AS latest
                FROM flight_observations GROUP BY source
                UNION ALL
                SELECT 'satellites', source, COUNT(*), MAX(timestamp)
                FROM satellite_observations GROUP BY source
                UNION ALL
                SELECT 'weather', source, COUNT(*), MAX(timestamp)
                FROM weather_observations GROUP BY source
                UNION ALL
                SELECT 'events', source, COUNT(*), MAX(event_date)
                FROM events GROUP BY source
                """
            )
        ).all()
        sources = [
            {
                "domain": r[0],
                "source": r[1],
                "count": r[2],
                "latest": str(r[3]),
            }
            for r in source_rows
        ]
    finally:
        db.close()
    return {"state": _state, "counts": counts, "newest": newest, "sources": sources}
