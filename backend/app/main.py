import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api import base_router

app = FastAPI(title="SkyNexus API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(base_router, prefix="/api")

@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    print(f"SkyNexus starting in {settings.ENV} mode")
    if os.getenv("LIVE_INGEST", "1") == "1":
        threading.Thread(target=_ingest_loop, daemon=True).start()


def _ingest_loop() -> None:
    """Background live-ingestion loop: run now, then every 10 minutes."""
    from app.data import live_connectors

    interval_s = int(os.getenv("LIVE_INGEST_INTERVAL_S", "600"))
    while True:
        try:
            summary = live_connectors.run_live_ingestion()
            print(f"[live-ingest] {summary}")
        except Exception as exc:  # keep the loop alive no matter what
            print(f"[live-ingest] cycle failed: {exc}")
        time.sleep(interval_s)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}