"""Authenticated research surface and durable event delivery."""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from app.core.db import get_db, SessionLocal
from app.core.auth import session_for
from app.models.research import Observation, StreamEvent, Experiment, HourlyFeature
from app.services.research import sources

router=APIRouter()

@router.get('/sources')
def list_sources(db:Session=Depends(get_db)):
    return {'sources':sources(db),'server_time':datetime.now(timezone.utc).isoformat()}

@router.get('/signals/{domain}')
def signals(domain:str,as_of:datetime|None=None,db:Session=Depends(get_db),limit:int=Query(100,ge=1,le=1000)):
    from app.core.config import get_settings
    if get_settings().DATA_MODE=='demo':return {'domain':domain,'observations':[],'sources':[], 'status':'no_synthetic_normalized_data'}
    cutoff=as_of or datetime.now(timezone.utc)
    query=select(Observation).where(Observation.domain==domain,Observation.kind!='synthetic',
        Observation.received_at<=cutoff,or_(Observation.observed_at<=cutoff,Observation.kind=='forecast'),
        or_(Observation.published_at==None,Observation.published_at<=cutoff))
    rows=db.scalars(query.order_by(Observation.observed_at.desc()).limit(limit)).all()
    return {'domain':domain,'observations':[dict(r.payload,id=r.id,source=r.source,observed_at=r.observed_at.isoformat(),received_at=r.received_at.isoformat(),kind=r.kind) for r in rows], 'sources':[s for s in sources(db) if s['domain']==domain]}

@router.get('/incidents')
def incidents(db:Session=Depends(get_db)):
    # Legacy detector outputs remain observations, not validated geopolitical incidents.
    from app.services.anomalies import get_anomalies
    detections=get_anomalies(db,hours=48,limit=100)
    return {'incidents':[dict(**r,title=r['summary'],status='candidate',evidence_support='unvalidated_association') for r in detections], 'status':'candidate_detections','message':'Statistical detections are investigation candidates, not confirmed causes.'}

@router.get('/snapshot')
def snapshot(db:Session=Depends(get_db)):
    watermark=db.scalar(select(func.max(StreamEvent.id))) or 0
    return {'watermark':watermark,'as_of':datetime.now(timezone.utc).isoformat(),'sources':sources(db)}

@router.get('/experiments')
def experiments(request:Request,db:Session=Depends(get_db)):
    owner=request.state.user['session_id']
    rows=db.scalars(select(Experiment).where(Experiment.session_hash==owner).order_by(Experiment.created_at.desc())).all()
    return {'experiments':[r.result for r in rows]}

@router.get('/stream')
def stream(request:Request):
    try: cursor=int(request.headers.get('last-event-id') or request.query_params.get('cursor','0'))
    except ValueError: raise HTTPException(422,'Invalid stream cursor')
    async def events():
        nonlocal cursor
        yield 'retry: 3000\n\n'
        while not await request.is_disconnected():
            if not await asyncio.to_thread(session_for,request):
                yield 'event: session_expired\ndata: {}\n\n'
                return
            def read():
                try:
                    from redis import Redis
                    from app.core.config import get_settings
                    bus=Redis.from_url(get_settings().REDIS_URL,decode_responses=True,socket_connect_timeout=0.5,socket_timeout=0.5)
                    entries=bus.xrange('research_events',min=f'({cursor}-0',count=100)
                    if entries:
                        output=[]
                        for event_id,fields in entries:
                            payload=json.loads(fields['data'])
                            output.append((int(event_id.split('-')[0]),payload.pop('type'),payload.pop('source'),payload))
                        return output
                except Exception:
                    pass  # Durable database outbox is the recovery path.
                with SessionLocal() as db:
                    return [(r.id,r.event_type,r.source,r.payload) for r in db.scalars(select(StreamEvent).where(StreamEvent.id>cursor).order_by(StreamEvent.id).limit(100)).all()]
            batch=await asyncio.to_thread(read)
            if batch:
                cursor=batch[-1][0]
                yield f'id: {cursor}\nevent: update\ndata: {json.dumps({"watermark":cursor,"changes":[{"type":kind,"source":source,**payload} for _,kind,source,payload in batch]})}\n\n'
            else: yield ': heartbeat\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(events(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@router.post('/report-jobs',status_code=202)
def report_job(body:dict,request:Request):
    from uuid import UUID
    from redis import Redis
    from rq import Queue
    from app.core.config import get_settings
    try:
        region=str(UUID(body['region_id'])); hours=int(body.get('hours',24))
        if not 1<=hours<=72: raise ValueError()
    except (KeyError,ValueError,TypeError):raise HTTPException(422,'A valid region_id and hours between 1 and 72 are required')
    queue=Queue('research',connection=Redis.from_url(get_settings().REDIS_URL))
    job=queue.enqueue('app.jobs.report',region,hours,request.state.user['session_id'],get_settings().DATA_MODE,__import__('app.core.config',fromlist=['request_as_of']).request_as_of.get(),job_timeout=120,result_ttl=3600,meta={'owner':request.state.user['session_id']})
    return {'id':job.id,'status':'queued'}

@router.get('/report-jobs/{job_id}')
def report_status(job_id:str,request:Request):
    from redis import Redis
    from rq.job import Job
    from rq.exceptions import NoSuchJobError
    from app.core.config import get_settings
    try:job=Job.fetch(job_id,connection=Redis.from_url(get_settings().REDIS_URL))
    except NoSuchJobError:raise HTTPException(404,'Job not found')
    if job.meta.get('owner')!=request.state.user['session_id']:raise HTTPException(404,'Job not found')
    status=job.get_status(refresh=True)
    return {'id':job.id,'status':status,'result':job.result if job.is_finished else None,'error':'Report generation failed' if job.is_failed else None}

@router.post('/experiments',status_code=201)
def run_experiment(body:dict,request:Request,db:Session=Depends(get_db)):
    import uuid
    import hashlib
    from app.services.experiments import evaluate
    source=body.get('source');metric=body.get('metric');entity=body.get('entity')
    if not source or not metric:raise HTTPException(422,'Select a source and numeric metric')
    from app.core.config import get_settings, request_as_of
    if get_settings().DATA_MODE=='demo':raise HTTPException(422,'Use the separate synthetic benchmark for simulated data')
    cutoff=request_as_of.get() or datetime.now(timezone.utc)
    query=select(HourlyFeature).where(HourlyFeature.source==source,HourlyFeature.metric==metric,HourlyFeature.timestamp<cutoff.replace(minute=0,second=0,microsecond=0),HourlyFeature.updated_at<=cutoff)
    if entity:query=query.where(HourlyFeature.entity==str(entity))
    records=db.scalars(query.order_by(HourlyFeature.timestamp).limit(10000)).all()
    if len({r.entity for r in records})>1 and not entity:raise HTTPException(422,'Select an entity; unrelated series cannot be averaged')
    buckets={r.timestamp:[r.value_sum/r.sample_count] for r in records}
    keys=sorted(buckets)
    if keys and any((b-a).total_seconds()!=3600 for a,b in zip(keys,keys[1:])):
        raise HTTPException(422,'Hourly series has gaps; choose a complete study interval before evaluation')
    values=[sum(buckets[k])/len(buckets[k]) for k in keys]
    try:result=evaluate(values)
    except ValueError as exc:raise HTTPException(422,str(exc))
    result.update(id=str(uuid.uuid4()),source=source,metric=metric,entity=entity,dataset_mode='live',dataset_hash=hashlib.sha256(json.dumps(values).encode()).hexdigest(),created_at=datetime.now(timezone.utc).isoformat())
    db.add(Experiment(id=result['id'],session_hash=request.state.user['session_id'],result=result));db.commit()
    return result

@router.get('/signals/{domain}/analysis')
def signal_analysis(domain:str,db:Session=Depends(get_db)):
    import statistics
    from app.core.config import get_settings
    if get_settings().DATA_MODE=='demo':return {'domain':domain,'series':[],'status':'no_synthetic_normalized_data'}
    cutoff=__import__("app.core.config",fromlist=["request_as_of"]).request_as_of.get() or datetime.now(timezone.utc)
    rows=db.scalars(select(HourlyFeature).where(HourlyFeature.domain==domain,HourlyFeature.timestamp<=cutoff,HourlyFeature.updated_at<=cutoff).order_by(HourlyFeature.timestamp).limit(20000)).all()
    groups={}
    for row in rows:
        key=(row.source,row.entity,row.metric,row.unit)
        groups.setdefault(key,[]).append(row)
    output=[]
    for (source,entity,metric,unit),items in groups.items():
        span=(items[-1].timestamp-items[0].timestamp).total_seconds()/86400
        history=[dict(time=r.timestamp.isoformat(),value=r.value_sum/r.sample_count) for r in items]
        values=[p['value'] for p in history]
        baseline=values[:-1]
        coverage=len(items)/max(1,span*24+1)
        sufficient=span>=14 and coverage>=.8
        mean=statistics.fmean(baseline) if baseline else None
        sd=max(statistics.pstdev(baseline),abs(mean)*.05,1e-6) if len(baseline)>1 else None
        output.append(dict(source=source,entity=entity,metric=metric,unit=unit,points=history[-168:],baseline_days=round(span,1),coverage_pct=round(min(100,coverage*100),1),status='provisional' if not sufficient else 'ready',latest=values[-1],expected=mean,z_score=(values[-1]-mean)/sd if sufficient and sd else None,forecast_status='Run a chronological experiment before interpreting forecasts as validated'))
    return {'domain':domain,'series':output,'method':'Hourly observed numeric series; causal confidence is not inferred'}
