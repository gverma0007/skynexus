from fastapi import APIRouter

from app.api import (alerts, anomalies, events, flights, ingest, regions, reports, satellites,
                     search, stats, system)

router = APIRouter()

router.include_router(regions.router, tags=["regions"])
router.include_router(reports.router, tags=["reports"])
router.include_router(flights.router, prefix="/flights", tags=["flights"])
router.include_router(satellites.router, prefix="/satellites", tags=["satellites"])
router.include_router(events.router, prefix="/events", tags=["events"])
router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
router.include_router(stats.router, prefix="/stats", tags=["stats"])
router.include_router(search.router, prefix="/search", tags=["search"])
router.include_router(system.router, prefix="/system", tags=["system"])
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])


@router.get("/")
def root():
    return {"message": "SkyNexus API", "docs": "/docs"}
