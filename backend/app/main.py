import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import base_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("skynexus")


def _ingest_loop(interval_s: int) -> None:
    import gc
    from app.services import ingest

    while True:
        summary = ingest.run_cycle()
        logger.info("[ingest] %s", summary)
        gc.collect()
        time.sleep(interval_s)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info("SkyNexus starting: env=%s data_mode=%s live_ingest=%s",
                settings.ENV, settings.DATA_MODE, settings.LIVE_INGEST)
    if settings.DATA_MODE == "live" and settings.LIVE_INGEST:
        threading.Thread(target=_ingest_loop, args=(settings.LIVE_INGEST_INTERVAL_S,), daemon=True).start()
    else:
        from app.services import ingest

        threading.Thread(target=ingest.run_cycle, daemon=True).start()  # analysis only
    yield


app = FastAPI(title="SkyNexus API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(base_router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
