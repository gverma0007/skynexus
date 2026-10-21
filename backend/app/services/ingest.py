"""One ingest cycle, shared by the background loop and the API button."""

from __future__ import annotations

import logging
import threading
import time

from app.core.config import get_settings
from app.core.db import SessionLocal

logger = logging.getLogger("ingest")

state: dict = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_summary": None,
    "last_error": None,
    "duration_s": None,
    "cycles": 0,
}
_lock = threading.Lock()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def refresh_analysis() -> int:
    """Rebuild caches and rerun the anomaly engine."""
    from app.ml.anomaly import run_anomaly_detection
    from app.services import geo, satellites, series

    series.invalidate()
    satellites.invalidate()
    geo.invalidate()
    db = SessionLocal()
    try:
        return run_anomaly_detection(db)
    finally:
        db.close()


def run_cycle(steps: int = 6) -> dict | None:
    """Run connectors (live mode) then analysis. Returns None if already running."""
    with _lock:
        if state["running"]:
            return None
        state["running"] = True
        state["last_started"] = _now_iso()
    start = time.time()
    summary: dict = {}
    try:
        if get_settings().DATA_MODE == "live":
            from app.data import live_connectors

            summary = live_connectors.run_live_ingestion(steps=steps)
        summary["anomalies_flagged"] = refresh_analysis()
        state["last_summary"] = summary
        state["last_error"] = None
    except Exception as exc:  # the loop must survive any failure
        logger.exception("ingest cycle failed")
        state["last_error"] = str(exc)
    finally:
        state["running"] = False
        state["cycles"] += 1
        state["last_finished"] = _now_iso()
        state["duration_s"] = round(time.time() - start, 1)
    return summary


def start_background(steps: int = 6) -> bool:
    if state["running"]:
        return False
    threading.Thread(target=run_cycle, args=(steps,), daemon=True).start()
    return True
