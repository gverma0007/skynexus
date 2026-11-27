"""Bounded analysis worker jobs, isolated from API and ingestion."""
import asyncio
from app.core.db import SessionLocal

def refresh():
    from app.services.ingest import refresh_analysis
    return refresh_analysis()

def report(region_id,hours,owner,mode="live",as_of=None):
    from app.services.reports import generate_report
    from app.core.config import request_mode,request_as_of
    mode_token=request_mode.set(mode);time_token=request_as_of.set(as_of)
    try:
        with SessionLocal() as db:
            return asyncio.run(generate_report(db,region_id,hours,owner_session=owner))
    finally:
        request_mode.reset(mode_token);request_as_of.reset(time_token)
