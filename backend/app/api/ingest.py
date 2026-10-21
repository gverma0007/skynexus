from fastapi import APIRouter

from app.services import ingest

router = APIRouter()


@router.post("/live")
def trigger_ingest(steps: int = 6):
    """Start an ingest + analysis cycle in the background."""
    started = ingest.start_background(steps)
    return {"status": "started" if started else "already_running", "state": ingest.state}


@router.get("/status")
def ingest_status():
    return {"state": ingest.state}
