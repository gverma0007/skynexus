from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.aviation import WhatChangedReport
from app.services.reports import generate_report, report_to_dict

router = APIRouter()


def evidence_sections(data):
    """Bounded readable evidence; the JSON export retains the complete snapshot."""
    import json
    sections=[]
    pattern=data.get('pattern_analysis',{})
    if pattern:
        counts={k:v for k,v in pattern.items() if k not in ('flagged_hours','limitations')}
        sections.append(('Pattern analysis',json.dumps(counts,sort_keys=True)))
        sections.extend(('Pattern interpretation',limitation) for limitation in pattern.get('limitations',[]))
        for flag in pattern.get('flagged_hours',[])[:24]:
            sections.append(('Reference-band observation',f"{flag['time']}: {flag['aircraft']} aircraft/hour, {flag['direction']} {flag['reference_band']}; storm index {flag.get('storm')}."))
    evidence=data.get('source_evidence',[])
    sections.append(('Supporting source evidence',f'{len(evidence)} stored records matched the geographic/time rules. Global context is labelled separately. Up to 40 summaries follow; complete payloads are in the evidence JSON.'))
    for item in evidence[:40]:
        payload=item.get('payload',{})
        summary=payload.get('title') or payload.get('metric') or 'Attributed observation'
        value=f"; value {payload['value']} {payload.get('unit','')}" if payload.get('value') is not None else ''
        sections.append((f"{item['source']} / {item['kind']}",f"{summary}{value}; observed {item['observed_at']}; received {item['received_at']}; {item['relation']}; provenance {payload.get('provenance_url') or payload.get('url') or 'provider catalogue'}."))
    matches=data.get('exposures',[])
    sections.append(('Asset exposure',f'{len(matches)} geometric intersections. Exposure does not prove damage, closure or operational failure.'))
    for item in matches[:40]:
        sections.append(('Exposure candidate',f"{item['name']}: {item['hazard_kind']} from {item['hazard_source']}, {item['kind']}, valid/observed {item['observed_at']}; provenance {item.get('provenance_url')}"))
    for item in data.get('alternative_explanations',[]):
        sections.append((f"Alternative: {item['explanation']}",item['support']))
    sections.extend([('Input snapshot hash',data.get('dataset_hash','Legacy report: unavailable')),
                     ('Reproducibility',json.dumps(data.get('provenance',{}),sort_keys=True))])
    return sections


class ReportRequest(BaseModel):
    region_id: UUID
    hours: int = Field(24, ge=1, le=72)


@router.post("/reports", status_code=201)
async def create_report(req: ReportRequest, request: Request, db: Session = Depends(get_db)):
    """Generate a What-Changed report and save it."""
    report = await generate_report(db, str(req.region_id), req.hours, persist=True, owner_session=request.state.user["session_id"])
    if report is None:
        raise HTTPException(status_code=404, detail="Region not found")
    return report


@router.get("/reports")
def list_reports(request: Request, limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.execute(text(
        """
        SELECT w.id::text, w.region_id::text, r.name, w.window_hours, w.generated_at, w.ai_source,
               w.metrics_json -> 'disruption_index' ->> 'after'
        FROM what_changed_reports w LEFT JOIN regions r ON r.id = w.region_id
        WHERE w.owner_session = :owner
        ORDER BY w.generated_at DESC LIMIT :limit
        """
    ), {"limit": limit, "owner": request.state.user["session_id"]}).all()
    return [{"id": r[0], "region_id": r[1], "region_name": r[2], "window_hours": r[3],
             "generated_at": r[4].isoformat(), "ai_source": r[5],
             "index": float(r[6]) if r[6] is not None else None} for r in rows]


@router.get("/reports/{report_id}")
def get_report(report_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = db.get(WhatChangedReport, report_id)
    if row is None or row.owner_session != request.state.user["session_id"]:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_to_dict(row)


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = db.get(WhatChangedReport, report_id)
    if row is None or row.owner_session != request.state.user["session_id"]:
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


@router.get("/reports/{report_id}/export")
def export_report(report_id: UUID, request: Request, format: str = Query("json", pattern="^(json|markdown|pdf|csv)$"), db: Session = Depends(get_db)):
    import io, json, csv
    from fastapi.responses import Response
    row=db.get(WhatChangedReport, report_id)
    if row is None or row.owner_session != request.state.user['session_id']:
        raise HTTPException(404, 'Report not found')
    data=report_to_dict(row)
    headers={'Content-Disposition':f'attachment; filename="skynexus-{report_id}.{dict(markdown="md").get(format,format)}"'}
    if format=='json': return Response(json.dumps(data,indent=2),media_type='application/json',headers=headers)
    lines=['SkyNexus investigation',f"Region: {data.get('region',{}).get('name')}",f"Dataset: {data.get('dataset_mode','legacy')}",f"Method: {data.get('method_version','legacy')}",f"Observation coverage: {data.get('data_coverage_pct',row.confidence_pct)}% (not causal confidence)",data.get('overall_assessment',''),'Limitations: '+ '; '.join(data.get('limitations',[])),json.dumps(data.get('windows',{}))]
    if format=='markdown':
        changes=['| Measure | Before | After | Change % |','| --- | ---: | ---: | ---: |']
        for key,value in data.items():
            if isinstance(value,dict) and 'before' in value:changes.append(f"| {value.get('label',key)} | {value.get('before')} | {value.get('after')} | {value.get('delta_pct','n/a')} |")
        sections=[f'## {title}\n\n{content}' for title,content in evidence_sections(data)]
        return Response('\n\n'.join(lines+['\n'.join(changes)]+sections),media_type='text/markdown',headers=headers)
    if format=='csv':
        out=io.StringIO();writer=csv.writer(out);writer.writerow(['metric','before','after','delta_pct'])
        for key,value in data.items():
            if isinstance(value,dict) and 'before' in value:writer.writerow([key,value.get('before'),value.get('after'),value.get('delta_pct')])
        return Response(out.getvalue(),media_type='text/csv',headers=headers)
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.lineplots import LinePlot
    from xml.sax.saxutils import escape
    out=io.BytesIO(); styles=getSampleStyleSheet()
    story=[Paragraph('SkyNexus investigation',styles['Title']),Spacer(1,16)]
    for line in lines[1:]:story.extend([Paragraph(escape(str(line)),styles['BodyText']),Spacer(1,10)])
    table=[['Measure','Before','After','Change %']]
    for key,value in data.items():
        if isinstance(value,dict) and 'before' in value:
            table.append([value.get('label',key.replace('_',' ')),str(value.get('before')),str(value.get('after')),str(value.get('delta_pct','n/a'))])
    t=Table(table,repeatRows=1,colWidths=[210,75,75,75]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e5efeb')),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),9),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story.extend([Spacer(1,16),Paragraph('Observed changes',styles['Heading2']),t])
    points=[(i,p['aircraft']) for i,p in enumerate(data.get('historical_data',{}).get('points',[])) if p.get('aircraft') is not None]
    if len(points)>=2:
        drawing=Drawing(440,160);plot=LinePlot();plot.x=40;plot.y=25;plot.width=380;plot.height=120;plot.data=[points];plot.lines[0].strokeColor=colors.HexColor('#277a6a');drawing.add(plot);story.extend([Spacer(1,14),Paragraph('Aircraft per hour (stored analysis window)',styles['Heading2']),drawing])
    for title,content in [('Evidence support',data.get('evidence_support','Unvalidated'))]+evidence_sections(data)+[('Interpretation','No validated advance-warning accuracy is claimed. Observation coverage is not explanation confidence. Missing or contradictory evidence must be investigated.')]:
        story.extend([Spacer(1,12),Paragraph(title,styles['Heading2']),Paragraph(escape(str(content)),styles['BodyText'])])
    SimpleDocTemplate(out).build(story)
    return Response(out.getvalue(),media_type='application/pdf',headers=headers)
