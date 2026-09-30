from fastapi import APIRouter
from app.api.regions import router as regions_router
from app.api.flights import router as flights_router
from app.api.satellites import router as satellites_router
from app.api.anomalies import router as anomalies_router
from app.api.events import router as events_router
from app.api.disruption_index import router as disruption_index_router
from app.api.stats import router as stats_router
from app.api.what_changed import router as what_changed_router
from app.api.clock import router as clock_router
from app.api.ingest import router as ingest_router
from app.api.pressure_zones import router as pressure_zones_router

router = APIRouter()

router.include_router(regions_router, tags=["regions"])
router.include_router(flights_router, prefix="/flights", tags=["flights"])
router.include_router(satellites_router, prefix="/satellites", tags=["satellites"])
router.include_router(anomalies_router, prefix="/anomalies", tags=["anomalies"])
router.include_router(events_router, prefix="/events", tags=["events"])
router.include_router(disruption_index_router, prefix="/disruption-index", tags=["disruption-index"])
router.include_router(stats_router, prefix="/stats", tags=["stats"])
router.include_router(what_changed_router, prefix="/what-changed", tags=["what-changed"])
router.include_router(clock_router, prefix="/clock", tags=["clock"])
router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
router.include_router(pressure_zones_router, prefix="/pressure-zones", tags=["pressure-zones"])

@router.get("/")
async def root():
    return {"message": "SkyNexus API"}
