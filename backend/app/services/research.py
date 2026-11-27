"""Provider catalogue and append-only normalized observations/outbox."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from app.models.research import Observation, SourceState, StreamEvent, HourlyFeature

CATALOG = [
 ('regional-aviation','aviation','Regional aircraft features','derived',300,None,'https://openskynetwork.github.io/opensky-api/rest.html'),
 ('regional-weather','environment','Regional weather features','derived',300,None,'https://open-meteo.com/'),
 ('opensky','aviation','OpenSky','poll',120,None,'https://openskynetwork.github.io/opensky-api/rest.html'),
 ('aisstream','maritime','AISStream','native_stream',0,'AISSTREAM_API_KEY','https://aisstream.io/documentation'),
 ('gfw','maritime','Global Fishing Watch','historical',86400,'GFW_API_TOKEN','https://globalfishingwatch.org/our-apis/'),
 ('open-meteo','environment','Open-Meteo','poll',900,None,'https://open-meteo.com/'),
 ('firms','environment','NASA FIRMS','poll',3600,'FIRMS_MAP_KEY','https://firms.modaps.eosdis.nasa.gov/api/area'),
 ('openaq','environment','OpenAQ','poll',900,'OPENAQ_API_KEY','https://docs.openaq.org/'),
 ('glofas','environment','Copernicus GloFAS','scientific_download',21600,'EWDS_API_TOKEN','https://ewds.climate.copernicus.eu/how-to-api'),
 ('usgs','environment','USGS earthquakes','poll',300,None,'https://earthquake.usgs.gov/earthquakes/feed/'),
 ('gdacs','environment','GDACS disasters','poll',900,None,'https://www.gdacs.org/'),
 ('mbta','transit','MBTA transit','poll',30,None,'https://www.mbta.com/developers/v3-api'),
 ('eia','infrastructure','EIA electricity','poll',3600,'EIA_API_KEY','https://www.eia.gov/opendata/'),
 ('cloudflare','infrastructure','Cloudflare Radar','poll',300,'CLOUDFLARE_API_TOKEN','https://developers.cloudflare.com/radar/'),
 ('ioda','infrastructure','IODA connectivity','poll',300,None,'https://api.ioda.inetintel.cc.gatech.edu/v2/docs'),
 ('gdelt','events','GDELT news context','poll',900,None,'https://www.gdeltproject.org/'),
 ('celestrak','space','CelesTrak orbital predictions','poll',7200,None,'https://celestrak.org/usage-policy.php'),
 ('noaa','space','NOAA space weather','poll',300,None,'https://www.swpc.noaa.gov/'),
 ('reference-assets','infrastructure','OurAirports study assets','poll',86400,None,'https://ourairports.com/data/'),
 ('earth-observation','environment','Earth observation imports','import',86400,None,'https://www.earthdata.nasa.gov/'),
]

def sources(db):
    from app.core.config import get_settings
    cfg = get_settings()
    output=[]
    for sid,domain,name,delivery,interval,key,url in CATALOG:
        state=db.get(SourceState,sid)
        if sid=="opensky" and not cfg.OPENSKY_CLIENT_ID: interval=max(interval,900)
        configured=state.configured if state and state.configured is not None else (not key or bool(getattr(cfg,key,'')))
        status=state.status if state else ('waiting' if configured else 'not_configured')
        if state and state.last_success and status=='ok' and (datetime.now(timezone.utc)-state.last_success).total_seconds()>max(interval*3,180): status='delayed'
        if sid in ('glofas','earth-observation') and not state: status='import_required'
        output.append(dict(id=sid,source=sid,name=name,domain=domain,delivery=delivery,interval_s=interval,status=status,configured=configured,last_success=state.last_success.isoformat() if state and state.last_success else None,last_error=state.error if state else None,records=state.records if state else 0,url=url,credential=key,limitations='Published with multi-day lag; historical context only.' if sid=='gfw' else None))
    return output

def record(db,source,domain,external_id,observed_at,payload,kind='observed',published_at=None):
    ident = db.execute(insert(Observation).values(source=source,domain=domain,external_id=str(external_id)[:200],observed_at=observed_at,published_at=published_at,payload=payload,kind=kind).on_conflict_do_nothing(constraint='uq_research_source_external').returning(Observation.id)).scalar()
    if ident:
        import math
        value=payload.get('value')
        if kind in ('observed','derived') and isinstance(value,(int,float)) and math.isfinite(value) and observed_at <= datetime.now(timezone.utc):
            feature=insert(HourlyFeature).values(source=source,domain=domain,entity=str(payload.get('entity_id',payload.get('scope','global')))[:200],metric=str(payload.get('metric','value'))[:100],unit=payload.get('unit'),timestamp=observed_at.replace(minute=0,second=0,microsecond=0),value_sum=value,sample_count=1)
            db.execute(feature.on_conflict_do_update(constraint='uq_hourly_feature',set_={'value_sum':HourlyFeature.value_sum+value,'sample_count':HourlyFeature.sample_count+1,'updated_at':func.now()}))
        db.add(StreamEvent(event_type='observation',source=source,payload={'domain':domain,'observation_id':ident}))
    return bool(ident)

def source_result(db,sid,count,error=None):
    state=db.get(SourceState,sid) or SourceState(id=sid,records=0)
    state.last_attempt=datetime.now(timezone.utc)
    state.status='error' if error else 'ok'
    state.error=error
    if not error:
        state.last_success=state.last_attempt
        state.records=(state.records or 0)+count
    db.add(state)
    db.add(StreamEvent(event_type='source',source=sid,payload={'status':state.status,'records':count}))
