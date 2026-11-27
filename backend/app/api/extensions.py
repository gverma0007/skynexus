"""Local-first forecasting, scientific exposure, archives and reproducible validation."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import uuid
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.config import get_settings,request_as_of
from app.models.research import Artifact,Asset,HourlyFeature,Experiment
from app.services import artifacts

router=APIRouter()

@router.get('/signals/{domain}/forecast')
def domain_forecast(domain:str,source:str,metric:str,entity:str,horizon:int=Query(6,ge=1,le=24),db:Session=Depends(get_db)):
    from app.services.forecasting import forecast
    now=request_as_of.get() or datetime.now(timezone.utc)
    base={'domain':domain,'source':source,'entity':entity,'metric':metric,'unit':None,'history':[],'points':[],'evaluation':None,'limitations':[]}
    if get_settings().DATA_MODE=='demo':return dict(base,status='insufficient_data',limitations=['Select a live/imported numeric series; synthetic benchmarks are separate.'])
    rows=db.scalars(select(HourlyFeature).where(HourlyFeature.domain==domain,HourlyFeature.source==source,HourlyFeature.entity==entity,HourlyFeature.metric==metric,HourlyFeature.timestamp<now.replace(minute=0,second=0,microsecond=0),HourlyFeature.updated_at<=now).order_by(HourlyFeature.timestamp.desc()).limit(720)).all()[::-1]
    base['history']=[{'time':r.timestamp.isoformat(),'value':r.value_sum/r.sample_count} for r in rows]
    if rows:base['unit']=rows[-1].unit
    if rows and (now-rows[-1].timestamp).total_seconds()>10800:
        return dict(base,status='insufficient_data',limitations=['Latest hourly observation is stale; use a historical as_of window for retrospective analysis.'])
    try:result=forecast([r.value_sum/r.sample_count for r in rows],[r.timestamp for r in rows],horizon)
    except ValueError as exc:return dict(base,status='insufficient_data',limitations=[str(exc)])
    return dict(base,**result,status='ready')

@router.get('/cases')
def cases():
    from app.services.historical import catalogue
    historical=catalogue()
    simulated=[dict(id='synthetic-'+name,title=name.replace('_',' ').title(),dataset_mode='synthetic',status='available',event_start='2026-01-08T12:00:00Z',event_end='2026-01-09T18:00:00Z',domains=['aviation','environment','transit'],region='Synthetic study region',description='Seeded simulation with explicit labels; not historical validation.',provenance_url=None,limitations=['Generated research fixture; no real-world accuracy is implied.']) for name in ('normal','weather','restriction','outage','compound','recovery')]
    return {'cases':historical+simulated}

@router.get('/cases/{case_id}/data')
def case_data(case_id:str):
    from app.services.historical import read_case,read_key
    from app.services.historical_evaluation import METHOD_VERSION
    from app.services.benchmark import dataset
    match=next((row for row in dataset() if 'synthetic-'+row['id']==case_id),None)
    if match is not None:return match
    try:data=read_case(case_id)
    except (FileNotFoundError,KeyError):raise HTTPException(404,'Download this public historical study before replaying it')
    except ValueError:raise HTTPException(409,'Historical dataset integrity check failed')
    try:
        evaluation=json.loads(read_key(f'historical/evaluations/{case_id}.json'))
        if isinstance(evaluation,dict) and evaluation.get('dataset_hash')==data['dataset_hash'] and evaluation.get('method_version')==METHOD_VERSION:data['evaluation']=evaluation
    except (FileNotFoundError,json.JSONDecodeError):pass
    return data


@router.post('/cases/{case_id}/download')
def download_case(case_id:str):
    from app.services.historical import download
    import httpx
    try:
        data=download(case_id)
        return {'case_id':case_id,'status':'available','samples':len(data['times']),'dataset_hash':data['dataset_hash']}
    except ValueError as e:raise HTTPException(422,str(e))
    except httpx.HTTPError:raise HTTPException(502,'Public archive unavailable; no substitute or synthetic data was created')


@router.post('/cases/{case_id}/evaluate',status_code=201)
def evaluate_case(case_id:str,request:Request,db:Session=Depends(get_db)):
    from app.services.historical import read_case,read_key,encoded
    from app.services.historical_evaluation import evaluate,METHOD_VERSION,report_markdown
    try:data=read_case(case_id)
    except (FileNotFoundError,KeyError):raise HTTPException(404,'Download this historical study first')
    except ValueError:raise HTTPException(409,'Historical dataset integrity check failed')
    try:
        result=json.loads(read_key(f'historical/evaluations/{case_id}.json'))
    except (FileNotFoundError,json.JSONDecodeError):result=None
    if not isinstance(result,dict) or result.get('dataset_hash')!=data['dataset_hash'] or result.get('method_version')!=METHOD_VERSION:
        try:result=evaluate(data)
        except ValueError as e:raise HTTPException(422,str(e))
    artifacts.write_bytes(f'historical/evaluations/{case_id}.json',encoded(result))
    files={'observations-and-labels.json':encoded(data),'evaluation.json':encoded(result),'report.md':report_markdown(data,result)}
    for source in data['provenance']:
        if source.get('name')=='NAB license notice':files['NAB-LICENSE.txt']=read_key(source['archive_key'])
    row=artifacts.save(db,request.state.user['session_id'],f'{case_id}-historical-evaluation.zip',artifacts.bundle(files,{'dataset_mode':'historical','case_id':case_id,'dataset_hash':data['dataset_hash'],'method_version':result['method_version']}),'application/zip')
    db.commit()
    return dict(result,id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),artifacts=[artifacts.describe(row)])

@router.post('/experiments/benchmark',status_code=201)
def benchmark(request:Request,db:Session=Depends(get_db)):
    from app.services.benchmark import run
    result=run(42)
    result.update(id=str(uuid.uuid4()),created_at=datetime.now(timezone.utc).isoformat(),source='synthetic-benchmark',metric='labelled_operational_disruption')
    from app.services.benchmark import dataset
    contents={'result.json':json.dumps(result,sort_keys=True,indent=2).encode(),
              'labelled_inputs.json':json.dumps(dataset(42),sort_keys=True).encode()}
    row=artifacts.save(db,request.state.user['session_id'],'synthetic-benchmark.zip',artifacts.bundle(contents,{'dataset_mode':'synthetic','seed':42}),'application/zip')
    result['artifacts']=[artifacts.describe(row)]
    db.add(Experiment(id=result['id'],session_hash=request.state.user['session_id'],result=result));db.commit()
    return result

@router.get('/assets')
def assets(db:Session=Depends(get_db)):
    mode='synthetic' if get_settings().DATA_MODE=='demo' else 'live'
    now=request_as_of.get() or datetime.now(timezone.utc)
    rows=db.scalars(select(Asset).where(Asset.dataset_mode==mode,Asset.available_at<=now)).all()
    return {'assets':[dict(id=r.id,name=r.name,asset_type=r.asset_type,geometry=r.geometry,provenance_url=r.provenance_url,dataset_mode=r.dataset_mode,properties=r.properties_json) for r in rows]}

@router.get('/exposures')
def exposure(db:Session=Depends(get_db)):
    from app.services.exposure import exposures
    return {'exposures':exposures(db,get_settings().DATA_MODE,request_as_of.get()),'method':'Attributed geometric intersection; not verified operational failure'}

@router.get('/artifacts')
def list_artifacts(request:Request,db:Session=Depends(get_db)):
    rows=db.scalars(select(Artifact).where(Artifact.session_hash==request.state.user['session_id']).order_by(Artifact.created_at.desc()).limit(100)).all()
    return {'artifacts':[artifacts.describe(row) for row in rows]}

@router.get('/artifacts/{artifact_id}')
def artifact(artifact_id:uuid.UUID,request:Request,db:Session=Depends(get_db)):
    row=db.get(Artifact,str(artifact_id))
    if not row or row.session_hash!=request.state.user['session_id']:raise HTTPException(404,'Artifact not found')
    try:content=artifacts.read_bytes(row)
    except FileNotFoundError:raise HTTPException(404,'Artifact storage is unavailable')
    except ValueError:raise HTTPException(409,'Artifact integrity check failed')
    filename=row.name.replace('"','').replace('\r','').replace('\n','')
    return Response(content,media_type=row.media_type,headers={'Content-Disposition':f'attachment; filename="{filename}"','ETag':row.sha256,'Cache-Control':'private, no-store'})

@router.post('/reports/{report_id}/archive',status_code=201)
def archive_report(report_id:uuid.UUID,request:Request,db:Session=Depends(get_db)):
    from app.models.aviation import WhatChangedReport
    from app.api.reports import export_report
    row=db.get(WhatChangedReport,report_id)
    if not row or row.owner_session!=request.state.user['session_id']:raise HTTPException(404,'Report not found')
    files={f'report.{extension}':export_report(report_id,request,format,db).body for format,extension in [('json','json'),('markdown','md'),('csv','csv'),('pdf','pdf')]}
    content=artifacts.bundle(files,{'report_id':str(report_id),'dataset_mode':row.metrics_json.get('dataset_mode','legacy'),'dataset_hash':row.metrics_json.get('dataset_hash'),'method_version':row.metrics_json.get('method_version')})
    artifact=artifacts.save(db,request.state.user['session_id'],f'report-{report_id}.zip',content,'application/zip');db.commit()
    return {'artifacts':[artifacts.describe(artifact)]}

@router.get('/configuration')
def configuration():
    from app.check_config import status
    return {'scope':'current_service_environment','capabilities':status(),'local_features_need_provider_keys':False,'storage_backend':get_settings().ARCHIVE_STORAGE}
