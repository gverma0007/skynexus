from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.aviation import WhatChangedReport
from app.services.reports import generate_report, report_to_dict

router = APIRouter()


class ReportRequest(BaseModel):
    region_id: UUID
    hours: int = Field(24, ge=1, le=72)


@router.post("/reports", status_code=201)
async def create_report(req: ReportRequest, db: Session = Depends(get_db)):
    """Generate a What-Changed report and save it."""
    report = await generate_report(db, str(req.region_id), req.hours, persist=True)
    if report is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return report


@router.get("/reports")
def list_reports(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.execute(text(
        """
        SELECT w.id::text, w.region_id::text, r.name, w.window_hours, w.generated_at, w.ai_source,
               w.metrics_json -> 'disruption_index' ->> 'after'
        FROM what_changed_reports w LEFT JOIN regions r ON r.id = w.region_id
        ORDER BY w.generated_at DESC LIMIT :limit
        """
    ), {"limit": limit}).all()
    return [{"id": r[0], "region_id": r[1], "region_name": r[2], "window_hours": r[3],
             "generated_at": r[4].isoformat(), "ai_source": r[5],
             "index": float(r[6]) if r[6] is not None else None} for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: UUID, db: Session = Depends(get_db)):
    row = db.get(WhatChangedReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_dict(row)


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: UUID, db: Session = Depends(get_db)):
    row = db.get(WhatChangedReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    db.delete(row)
    db.commit()


@router.get("/what-changed/{region_id}")
async def what_changed(region_id: UUID, hours: int = Query(24, ge=1, le=72), db: Session = Depends(get_db)):
    """Same comparison as a report, without saving it."""
    report = await generate_report(db, str(region_id), hours, persist=False)
    if report is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return report
