"""Independent, supervised collectors. Run: python -m app.worker."""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy import text
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.research import CATALOG, record, source_result

log=logging.getLogger('collectors')
UTC=timezone.utc

def stamp(value):
    if isinstance(value,(int,float)):
        return datetime.fromtimestamp(value/1000 if value>1e11 else value,UTC)
    if value:
        parsed=datetime.fromisoformat(str(value).replace(' UTC','').strip().replace('Z','+00:00'))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


def store(sid,domain,items,kind='observed'):
    with SessionLocal() as db:
        count=0
        for external,when,payload in items:
            count+=record(db,sid,domain,external,when,payload,kind)
        source_result(db,sid,count)
        db.commit()
    return count

async def collect(sid):
    cfg=get_settings()
    async with httpx.AsyncClient(timeout=25,headers={'User-Agent':'SkyNexusResearch/3.0'},follow_redirects=False) as client:
        async def get(url,**kw):
            response=await client.get(url,**kw)
            response.raise_for_status()
            return response.json()
        if sid=='noaa':
            data=await get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json')
            return [(str(r['time_tag']),stamp(r['time_tag']),{'metric':'kp_index','value':float(r['Kp']),'unit':'Kp','scope':'global'}) for r in data] if data and isinstance(data[0],dict) else [(str(r[0]),stamp(r[0]),{'metric':'kp_index','value':float(r[1]),'unit':'Kp','scope':'global'}) for r in data[1:]]
        if sid=='mbta':
            from app.services.transit import mbta_delays
            headers={'x-api-key':cfg.MBTA_API_KEY} if cfg.MBTA_API_KEY else {}
            data=await get('https://api-v3.mbta.com/alerts',params={'page[limit]':100},headers=headers)
            out=[(r['id']+':'+str(r['attributes'].get('updated_at','')),stamp(r['attributes'].get('updated_at')),{'entity_id':r['id'],'title':r['attributes'].get('header'),'description':r['attributes'].get('description'),'severity':r['attributes'].get('severity'),'effect':r['attributes'].get('effect'),'scope':'MBTA service network'}) for r in data.get('data',[])]
            predictions=await get('https://api-v3.mbta.com/predictions',params={'filter[route]':'Red,Orange,Blue','include':'schedule','page[limit]':100},headers=headers)
            out.extend(mbta_delays(predictions,datetime.now(UTC)))
            return out
        if sid=='ioda':
            now=int(datetime.now(UTC).timestamp())
            data=await get('https://api.ioda.inetintel.cc.gatech.edu/v2/outages/events',params={'from':now-3600,'until':now,'limit':100})
            rows=data.get('data',[])
            if not isinstance(rows,list): rows=[]
            return [(hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest(),stamp(r.get('start')),{'title':'Connectivity event','details':r,'scope':'provider entity'}) for r in rows]
        if sid=='firms':
            import csv,io
            response=await client.get(f'https://firms.modaps.eosdis.nasa.gov/api/area/csv/{cfg.FIRMS_MAP_KEY}/VIIRS_NOAA20_NRT/-83,23,-69,44/1')
            response.raise_for_status()
            return [(hashlib.sha256(str(r).encode()).hexdigest(),stamp(r.get('acq_date')+'T'+r.get('acq_time','0000').zfill(4)[:2]+':'+r.get('acq_time','0000').zfill(4)[2:]+':00+00:00'),{'metric':'fire_radiative_power','value':float(r.get('frp') or 0),'unit':'MW','lat':float(r['latitude']),'lon':float(r['longitude']),'confidence':r.get('confidence')}) for r in csv.DictReader(io.StringIO(response.text))]
        if sid=='openaq':
            data=await get('https://api.openaq.org/v3/locations',params={'coordinates':'42.36,-71.06','radius':25000,'limit':100},headers={'X-API-Key':cfg.OPENAQ_API_KEY})
            out=[]
            for location in data.get('results',[])[:10]:
                latest=await get(f"https://api.openaq.org/v3/locations/{location['id']}/latest",headers={'X-API-Key':cfg.OPENAQ_API_KEY})
                sensors={s['id']:s.get('parameter',{}) for s in location.get('sensors',[])}
                for r in latest.get('results',[]):
                    parameter=sensors.get(r.get('sensorsId'),{})
                    when=stamp(r.get('datetime',{}).get('utc'))
                    out.append((f"{r.get('sensorsId')}:{when.isoformat()}",when,{'entity_id':str(location['id']),'metric':parameter.get('name','measurement'),'value':r['value'],'unit':parameter.get('units'),'coordinates':r.get('coordinates'),'title':location.get('name')}))
            return out
        if sid=='eia':
            data=await get('https://api.eia.gov/v2/electricity/rto/region-data/data/',params={'api_key':cfg.EIA_API_KEY,'frequency':'hourly','data[0]':'value','facets[respondent][]':'ISNE','sort[0][column]':'period','sort[0][direction]':'desc','length':100})
            return [(f"{r['period']}:{r.get('type')}",stamp(r['period']),{'metric':r.get('type-name',r.get('type')),'value':float(r['value']) if r.get('value') is not None else None,'unit':r.get('value-units'),'scope':'ISO New England balancing authority'}) for r in data.get('response',{}).get('data',[])]
        if sid=='cloudflare':
            data=await get('https://api.cloudflare.com/client/v4/radar/annotations/outages',params={'dateRange':'1d','limit':100},headers={'Authorization':'Bearer '+cfg.CLOUDFLARE_API_TOKEN})
            return [(str(r['id']),stamp(r.get('startDate')),{'title':r.get('description') or 'Internet outage','scope':r.get('scope'),'details':r}) for r in data.get('result',{}).get('annotations',[])]
        if sid=='gdelt':
            data=await get('https://api.gdeltproject.org/api/v2/doc/doc',params={'query':'(flood OR wildfire OR port closure)','mode':'artlist','format':'json','maxrecords':50,'timespan':'1h'})
            return [(hashlib.sha256(r['url'].encode()).hexdigest(),stamp(datetime.strptime(r['seendate'],'%Y%m%dT%H%M%SZ').replace(tzinfo=UTC).isoformat()),{'title':r.get('title'),'url':r['url'],'country':r.get('sourcecountry'),'evidence_type':'news_context_not_ground_truth'}) for r in data.get('articles',[])]
        if sid=='gdacs':
            import xml.etree.ElementTree as ET
            response=await client.get('https://www.gdacs.org/xml/rss.xml');response.raise_for_status()
            from email.utils import parsedate_to_datetime
            return [(r.findtext('guid') or r.findtext('link'),parsedate_to_datetime(r.findtext('pubDate')),{'title':r.findtext('title'),'description':r.findtext('description'),'url':r.findtext('link')}) for r in ET.fromstring(response.content).findall('./channel/item')]
        if sid=='gfw':
            end=datetime.now(UTC)-timedelta(hours=96);start=end-timedelta(days=1)
            data=await get('https://gateway.api.globalfishingwatch.org/v3/events',params={'datasets[0]':'public-global-port-visits-events:latest','start-date':start.date().isoformat(),'end-date':end.date().isoformat(),'limit':100,'offset':0},headers={'Authorization':'Bearer '+cfg.GFW_API_TOKEN})
            return [(str(r['id']),stamp(r.get('start')),{'title':'Apparent port visit','details':r,'publication_lag_note':'Historical dataset; not live vessel surveillance'}) for r in data.get('entries',[])]
        raise ValueError('Unsupported collector')

async def legacy(sid):
    from app.data import live_connectors as live
    funcs={'opensky':live.fetch_live_flights,'open-meteo':live.fetch_live_weather,'usgs':live.fetch_live_events,'celestrak':live.fetch_satellite_positions}
    def run():
        with SessionLocal() as db:
            count=funcs[sid](db)
            source_result(db,sid,count)
            db.commit()
    await asyncio.to_thread(run)

async def loop(sid,domain,interval,key):
    if key and not getattr(get_settings(),key,''): return
    while True:
        try:
            if sid in ('opensky','open-meteo','usgs','celestrak'): await legacy(sid)
            else: store(sid,domain,await collect(sid), 'context' if sid=='gdelt' else 'derived' if sid=='mbta' else 'observed')
        except Exception as exc:
            log.warning('%s failed: %s',sid,type(exc).__name__)
            with SessionLocal() as db:
                # Do not persist request URLs or exception text containing API credentials.
                source_result(db,sid,0,type(exc).__name__)
                db.commit()
            await asyncio.sleep(max(interval,900))
            continue
        await asyncio.sleep(interval)

async def ais():
    import websockets
    cfg=get_settings()
    if not cfg.AISSTREAM_API_KEY:return
    while True:
        try:
            async with websockets.connect('wss://stream.aisstream.io/v0/stream',compression='deflate',max_size=2**20) as socket:
                await socket.send(json.dumps({'APIKey':cfg.AISSTREAM_API_KEY,'BoundingBoxes':[[[23,-83],[27,-78]],[[41,-72.5],[43.5,-69.5]],[[12,32],[30,44]]],'FilterMessageTypes':['PositionReport']}))
                batch=[]
                async for raw in socket:
                    msg=json.loads(raw)
                    if msg.get('MessageType')!='PositionReport':continue
                    meta=msg.get('MetaData',{});r=msg.get('Message',{}).get('PositionReport',{})
                    lat,lon=r.get('Latitude'),r.get('Longitude')
                    if lat is None or lon is None or not -90<=lat<=90 or not -180<=lon<=180:continue
                    when=stamp(meta.get('time_utc'))
                    batch.append((f"{meta.get('MMSI')}:{when.isoformat()}",when,{'entity_id':str(meta.get('MMSI')),'title':meta.get('ShipName','Vessel'),'lat':lat,'lon':lon,'speed_knots':r.get('Sog') if isinstance(r.get('Sog'),(int,float)) and r['Sog']<102.3 else None,'heading_deg':r.get('Cog') if isinstance(r.get('Cog'),(int,float)) and r['Cog']<360 else None}))
                    if batch:
                        await asyncio.to_thread(store,'aisstream','maritime',batch)
                        batch=[]
        except Exception as exc:
            with SessionLocal() as db:
                source_result(db,'aisstream',0,type(exc).__name__);db.commit()
            await asyncio.sleep(15)

async def analysis():
    from app.services.ingest import refresh_analysis
    while True:
        try:
            await asyncio.to_thread(refresh_analysis)
            await asyncio.to_thread(__import__("app.services.features",fromlist=["project"]).project)
        except Exception: log.exception('Analysis refresh failed')
        await asyncio.sleep(300)

async def publish():
    from redis import Redis
    from sqlalchemy import select
    from app.models.research import StreamEvent
    bus=Redis.from_url(get_settings().REDIS_URL,decode_responses=True)
    def flush():
        cursor=int(bus.get('outbox_cursor') or 0)
        with SessionLocal() as db:
            rows=db.scalars(select(StreamEvent).where(StreamEvent.id>cursor).order_by(StreamEvent.id).limit(500)).all()
            for row in rows:
                data=json.dumps({'type':row.event_type,'source':row.source,**row.payload})
                # Deterministic IDs make retry after a publisher crash idempotent.
                try:bus.xadd('research_events',{'data':data},id=f'{row.id}-0',maxlen=100000,approximate=True)
                except __import__('redis').exceptions.ResponseError as exc:
                    if 'equal or smaller' not in str(exc):raise
                bus.set('outbox_cursor',row.id)
    while True:
        try:await asyncio.to_thread(flush)
        except Exception:log.warning('Event bus unavailable; durable database events remain available')
        await asyncio.sleep(1)


async def maintenance():
    from app.models.research import Observation, HourlyFeature, StreamEvent, SessionRecord
    from sqlalchemy import delete
    while True:
        def prune():
            now=datetime.now(UTC)
            with SessionLocal() as db:
                from app.services.retention import archive_expired,archive_legacy
                archive_expired(db,now-timedelta(days=7))
                archive_legacy(db,now-timedelta(days=get_settings().RETENTION_DAYS))
                db.execute(delete(HourlyFeature).where(HourlyFeature.timestamp<now-timedelta(days=180)))
                db.execute(delete(StreamEvent).where(StreamEvent.created_at<now-timedelta(days=1)))
                db.execute(delete(SessionRecord).where(SessionRecord.expires_at<now))
                db.commit()
        try:await asyncio.to_thread(prune)
        except Exception:log.exception('Retention maintenance failed')
        await asyncio.sleep(300)


async def reference_assets():
    from app.data.reference_assets import fetch
    while True:
        try:await asyncio.to_thread(fetch)
        except Exception as exc:
            with SessionLocal() as db:
                source_result(db,'reference-assets',0,type(exc).__name__);db.commit()
        await asyncio.sleep(86400)


async def main():
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from app.models.research import SourceState
    enabled={'opensky','open-meteo','usgs','celestrak','noaa','mbta','ioda','gdacs','gdelt','firms','openaq','eia','cloudflare','gfw'}
    cfg=get_settings()
    acquisition=bool(cfg.LIVE_INGEST) and cfg.DATA_MODE!='demo'
    with SessionLocal() as db:
        for sid,_,_,_,_,key,_ in CATALOG:
            state=db.get(SourceState,sid) or SourceState(id=sid,status='waiting',records=0)
            state.configured=not key or bool(getattr(get_settings(),key,''))
            if not state.configured:state.status='not_configured'
            elif not acquisition and sid in enabled|{'aisstream','reference-assets'}:state.status='disabled'
            elif acquisition and state.status=='disabled':state.status='waiting'
            elif state.status=='not_configured':state.status='waiting'
            db.add(state)
        db.commit()
    tasks=[analysis(),publish(),maintenance()]
    if acquisition:
        tasks.extend([ais(),reference_assets(),*[loop(sid,domain,max(interval,900) if sid=="opensky" and not cfg.OPENSKY_CLIENT_ID else interval,key) for sid,domain,_,_,interval,key,_ in CATALOG if sid in enabled]])
    await asyncio.gather(*tasks)

if __name__=='__main__':asyncio.run(main())
