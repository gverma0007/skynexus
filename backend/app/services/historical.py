"""Keyless, attributed historical study datasets. No synthetic backfills."""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
import csv,hashlib,io,json,math,zipfile
import httpx
from app.core.config import get_settings
from app.services import artifacts

UTC=timezone.utc
NAB_REV='ea702d75cc2258d9d7dd35ca8e5e2539d71f3140'
NAB=f'https://raw.githubusercontent.com/numenta/NAB/{NAB_REV}'
PORTWATCH='https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query'
EXTRA=[
 {'id':'nab-nyc-taxi','title':'NYC taxi passenger demand — independently labelled NAB benchmark','region':'New York City','domains':['transit'],'event_start':'2014-10-30T15:30:00Z','event_end':'2015-01-29T03:30:00Z','description':'Real taxi passenger counts and published NAB anomaly windows. Includes several events for chronological warning evaluation.','provenance_url':NAB+'/data/realKnownCause/nyc_taxi.csv','limitations':['NAB windows are buffered annotations, not exact operational incident onset times.']},
 {'id':'nab-machine-temperature','title':'Machine temperature — independently labelled NAB benchmark','region':'Equipment telemetry','domains':['infrastructure'],'event_start':'2013-12-10T06:25:00Z','event_end':'2014-02-09T14:05:00Z','description':'Real equipment telemetry with published anomaly windows; no external account required.','provenance_url':NAB+'/data/realKnownCause/machine_temperature_system_failure.csv','limitations':['Equipment telemetry is not a geographic infrastructure outage record.']},
]


def iso(t):return t.astimezone(UTC).isoformat()
def stamp(value):
    result=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)
def digest(content):return hashlib.sha256(content).hexdigest()
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def read_key(key):
    cfg=get_settings()
    if cfg.ARCHIVE_STORAGE=='r2':
        from botocore.exceptions import ClientError
        try:return artifacts.client().get_object(Bucket=cfg.R2_BUCKET,Key=key)['Body'].read()
        except ClientError as e:
            if e.response.get('Error',{}).get('Code') in ('NoSuchKey','NotFound','404'):raise FileNotFoundError(key) from None
            raise
    root=Path(cfg.ARTIFACT_DIR).resolve();path=(root/key).resolve()
    if not path.is_relative_to(root):raise ValueError('Invalid historical cache key')
    return path.read_bytes()


def fetch(url,name):
    """Cache exact public response bytes; a checksum mismatch never becomes data."""
    prefix='historical/raw/'+digest(url.encode())
    try:
        meta=json.loads(read_key(prefix+'.json'));content=read_key(prefix+'.bin')
        if digest(content)!=meta['sha256']:raise ValueError('Historical raw checksum mismatch')
        return content,meta
    except (FileNotFoundError,KeyError):pass
    # URLs are solely constructed by the fixed adapters below, never client input.
    with httpx.Client(timeout=httpx.Timeout(90,connect=20),follow_redirects=True,headers={'User-Agent':'SkyNexusAcademicHistorical/1.0'}) as client:
        with client.stream('GET',url) as response:
            response.raise_for_status();parts=[];size=0
            for part in response.iter_bytes():
                size+=len(part)
                if size>200_000_000:raise ValueError('Public archive exceeds the 200 MB download bound')
                parts.append(part)
            content=b''.join(parts)
    meta={'name':name,'url':url,'retrieved_at':iso(datetime.now(UTC)),'sha256':digest(content),'size_bytes':len(content),'archive_key':prefix+'.bin'}
    artifacts.write_bytes(prefix+'.bin',content);artifacts.write_bytes(prefix+'.json',encoded(meta))
    return content,meta


def read_case(case_id):
    if case_id not in {r['id'] for r in definitions()}:raise KeyError(case_id)
    data=json.loads(read_key(f'historical/cases/{case_id}.json'))
    snapshot={k:v for k,v in data.items() if k not in ('dataset_hash','evaluation')}
    if digest(encoded(snapshot))!=data['dataset_hash']:raise ValueError('Historical case checksum mismatch')
    return data


def definitions():
    originals=json.loads((Path(__file__).parents[1]/'data'/'cases.json').read_text())
    return originals+[dict(row,dataset_mode='historical',status='download_required') for row in EXTRA]


def catalogue():
    rows=[]
    for row in definitions():
        row=dict(row,status='download_required',download_supported=True)
        try:
            data=read_case(row['id']);row.update(status='available',description=data['description'],cadence_hours=data['cadence_hours'],samples=len(data['times']),limitations=data['limitations'],domains=sorted({c['domain'] for c in data['channels']}),event_start=data['event_start'],event_end=data['event_end'])
        except FileNotFoundError:pass
        except (ValueError,KeyError,json.JSONDecodeError):row.update(status='error',limitations=['Cached dataset failed verification; download it again.'])
        rows.append(row)
    return rows


def timeline(start,end,cadence):
    start,end=stamp(start),stamp(end)
    count=math.ceil((end-start).total_seconds()/(cadence*3600)-1e-10)
    return [start+timedelta(hours=cadence*i) for i in range(count)]


def channel(ident,label,unit,domain,values,url,**extra):
    return dict(id=ident,label=label,unit=unit,domain=domain,values=values,provenance_url=url,**extra)


def qc_number(text,field=0,quality=1,scale=10,sentinel=99999):
    bits=(text or '').split(',')
    if len(bits)<=max(field,quality) or bits[quality] not in ('0','1','4','5'):return None
    try:value=float(bits[field])
    except ValueError:return None
    return None if abs(value)==sentinel else value/scale


def noaa(station,start,end,cadence=1):
    url=f'https://noaa-global-hourly-pds.s3.amazonaws.com/{stamp(start).year}/{station}.csv'
    raw,meta=fetch(url,'NOAA ISD station observations')
    times=timeline(start,end,cadence);slots={t:i for i,t in enumerate(times)}
    values={key:defaultdict(list) for key in ('wind','pressure','rain')}
    station_name=None
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        when=stamp(row['DATE']);bucket=when.replace(hour=when.hour//cadence*cadence,minute=0,second=0,microsecond=0)
        if bucket not in slots:continue
        station_name=row['NAME']
        candidates={'wind':qc_number(row.get('WND'),3,4,10,9999),'pressure':qc_number(row.get('SLP'))}
        rain=[]
        for key in ('AA1','AA2','AA3'):
            bits=row.get(key,'').split(',')
            if len(bits)==4 and bits[0].isdigit() and int(bits[0])==cadence:
                value=qc_number(row[key],1,3,10,9999)
                if value is not None:rain.append(value)
        candidates['rain']=max(rain) if rain else None
        for key,value in candidates.items():
            if value is not None:values[key][slots[bucket]].append(value)
    aggregate=lambda key:[round(sum(values[key][i])/len(values[key][i]),4) if values[key][i] else None for i in range(len(times))]
    channels=[channel('wind','Station wind speed','m/s','environment',aggregate('wind'),url),channel('pressure','Station sea-level pressure','hPa','environment',aggregate('pressure'),url)]
    if any(values['rain'].values()):channels.insert(0,channel('rain',f'Reported {cadence}-hour precipitation','mm','environment',aggregate('rain'),url))
    return times,channels,[meta],station_name


def portwatch():
    params={'where':"portid='chokepoint1' AND year=2021",'outFields':'date,portid,portname,n_total,capacity','orderByFields':'date ASC','returnGeometry':'false','resultRecordCount':10000,'f':'json'}
    url=str(httpx.URL(PORTWATCH,params=params));raw,meta=fetch(url,'IMF PortWatch Suez daily transit calls')
    doc=json.loads(raw)
    if doc.get('error') or doc.get('exceededTransferLimit'):raise ValueError('Incomplete PortWatch response')
    rows={stamp(r['attributes']['date']):r['attributes'] for r in doc.get('features',[])}
    times=timeline('2021-01-01','2021-04-16',24)
    return times,[channel('transits','Suez vessel transits','vessels/day','maritime',[rows.get(t,{}).get('n_total') for t in times],url),channel('capacity','Estimated transit capacity','provider capacity units/day','maritime',[rows.get(t,{}).get('capacity') for t in times],url)],[meta]


def epa():
    url='https://aqs.epa.gov/aqsweb/airdata/hourly_88502_2023.zip';raw,meta=fetch(url,'EPA AQS hourly PM2.5 parameter 88502 (non-reference methods)')
    times=timeline('2023-04-01','2023-06-20',1);slots={t:i for i,t in enumerate(times)};sensors=defaultdict(lambda:defaultdict(list))
    # Select one sensor by PRE-EVENT coverage, then freeze membership throughout.
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        member=next(n for n in archive.namelist() if n.endswith('.csv'))
        import pandas as pd
        columns=['State Code','County Code','Site Num','POC','Date GMT','Time GMT','Sample Measurement','Units of Measure','Qualifier']
        for chunk in pd.read_csv(archive.open(member),usecols=columns,dtype=str,chunksize=150000):
            chunk=chunk[(chunk['State Code'].str.zfill(2)=='36')&chunk['County Code'].str.zfill(3).isin(['005','047','061','081','085'])]
            for row in chunk.to_dict('records'):
                when=stamp(row['Date GMT']+'T'+row['Time GMT'])
                if when not in slots:continue
                try:value=float(row['Sample Measurement'])
                except (ValueError,TypeError):continue
                sensor=(row['County Code'].zfill(3),row['Site Num'].zfill(4),row['POC'])
                if math.isfinite(value) and value>=0:sensors[sensor][slots[when]].append(value)
    candidates=[(sum(times[i]<stamp('2023-06-01') for i in rows),sensor) for sensor,rows in sensors.items()]
    if not candidates:raise ValueError('No valid NYC PM2.5 monitor data was returned')
    count,sensor=sorted(candidates,key=lambda item:(-item[0],item[1]))[0];samples=sensors[sensor]
    values=[sum(samples[i])/len(samples[i]) if samples[i] else None for i in range(len(times))]
    if count<100:raise ValueError('Insufficient pre-event EPA monitor coverage')
    return times,[channel('pm25','NYC fixed-monitor PM2.5','micrograms/m³','environment',values,url,entity=f'AQS 36-{sensor[0]}-{sensor[1]} / POC {sensor[2]}',selection='Highest pre-June coverage; fixed monitor and POC throughout')],[meta]


def bts():
    from zoneinfo import ZoneInfo
    url='https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2023_1.zip'
    raw,meta=fetch(url,'BTS January 2023 on-time flight performance')
    local_zone=ZoneInfo('America/New_York')
    times=timeline(iso(datetime(2023,1,1,tzinfo=local_zone)),iso(datetime(2023,2,1,tzinfo=local_zone)),1);slots={t:i for i,t in enumerate(times)};delays=defaultdict(list);scheduled=defaultdict(int);cancelled=defaultdict(int)
    airports={'JFK','LGA','EWR','BOS'}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        member=next(n for n in archive.namelist() if n.endswith('.csv'))
        import pandas as pd
        columns=['FlightDate','Origin','CRSDepTime','DepDelay','Cancelled']
        for chunk in pd.read_csv(archive.open(member),usecols=columns,dtype=str,chunksize=100000):
            for row in chunk[chunk.Origin.isin(airports)].to_dict('records'):
                clock=int(float(row['CRSDepTime']));date=stamp(row['FlightDate'][:10]).date()
                local=datetime.combine(date,datetime.min.time(),ZoneInfo('America/New_York'))+timedelta(hours=clock//100,minutes=clock%100)
                when=local.astimezone(UTC).replace(minute=0,second=0,microsecond=0)
                if when not in slots:continue
                i=slots[when];scheduled[i]+=1;cancelled[i]+=int(float(row['Cancelled'])==1)
                try:delay=float(row['DepDelay'])
                except (ValueError,TypeError):continue
                if math.isfinite(delay):delays[i].append(delay)
    return times,[channel('departure_delay','Mean departure delay by scheduled departure hour','minutes','aviation',[sum(delays[i])/len(delays[i]) if delays[i] else None for i in range(len(times))],url),channel('cancelled_fraction','Cancelled share of scheduled flights','fraction','aviation',[cancelled[i]/scheduled[i] if scheduled[i] else None for i in range(len(times))],url),channel('scheduled_flights','Scheduled departures — JFK/LGA/EWR/BOS','flights/hour','aviation',[scheduled[i] for i in range(len(times))],url)],[meta]


def tonga():
    start,end='2021-11-15','2022-02-01'
    params={'format':'geojson','starttime':start,'endtime':end,'minlatitude':-23,'maxlatitude':-18,'minlongitude':-178,'maxlongitude':-172,'minmagnitude':4,'limit':20000,'orderby':'time-asc'}
    url=str(httpx.URL('https://earthquake.usgs.gov/fdsnws/event/1/query',params=params));raw,meta=fetch(url,'USGS reviewed regional seismic event catalogue')
    doc=json.loads(raw)
    if doc.get('metadata',{}).get('count',0)>=20000:raise ValueError('USGS query reached its result bound')
    times=timeline(start,end,6);slots={t:i for i,t in enumerate(times)};quake=defaultdict(int);volcano=defaultdict(int)
    for item in doc.get('features',[]):
        p=item['properties'];t=datetime.fromtimestamp(p['time']/1000,UTC);t=t.replace(hour=t.hour//6*6,minute=0,second=0,microsecond=0)
        if t not in slots:continue
        if p['type']=='earthquake':quake[slots[t]]+=1
        elif 'volcanic' in p['type']:volcano[slots[t]]+=1
    return times,[channel('earthquakes','Regional catalogued earthquakes M≥4','events/6h','environment',[quake[i] for i in range(len(times))],url),channel('volcanic_events','Catalogued volcanic events M≥4','events/6h','environment',[volcano[i] for i in range(len(times))],url)],[meta]


def nab(case_id):
    filename='nyc_taxi.csv' if case_id=='nab-nyc-taxi' else 'machine_temperature_system_failure.csv'
    path='realKnownCause/'+filename;url=NAB+'/data/'+path
    raw,meta=fetch(url,'Numenta Anomaly Benchmark real observations')
    labelraw,labelmeta=fetch(NAB+'/labels/combined_windows.json','NAB published anomaly windows')
    license_bytes,license_meta=fetch(NAB+'/LICENSE.txt','NAB license notice')
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))));observed=[stamp(r['timestamp']) for r in rows];measurements=[float(r['value']) for r in rows]
    # Keep native spacing, including the five-minute equipment telemetry.
    from collections import Counter
    seconds=Counter((b-a).total_seconds() for a,b in zip(observed,observed[1:]) if b>a).most_common(1)[0][0]
    first,last=min(observed),max(observed)
    if seconds<=0 or any((t-first).total_seconds()%seconds for t in observed):raise ValueError('NAB timestamps do not align to the native sample grid')
    cadence=seconds/3600
    times=timeline(iso(first),iso(last+timedelta(seconds=seconds)),cadence)
    counts=Counter(observed);indexed=dict(zip(observed,measurements))
    # Do not guess ordering, average, or select one value across a clock fold.
    values=[indexed.get(t) if counts[t]<=1 else None for t in times]
    windows=[(stamp(a),stamp(b)) for a,b in json.loads(labelraw)[path]]
    labels=[any(a<=t<=b for a,b in windows) for t in times]
    label='Taxi passengers per half hour' if case_id=='nab-nyc-taxi' else 'Equipment temperature'
    unit='passengers/30min' if case_id=='nab-nyc-taxi' else 'provider temperature units'
    return times,[channel('value',label,unit,'transit' if case_id=='nab-nyc-taxi' else 'infrastructure',values,url,
                         source_sample_count=len(rows),ambiguous_timestamps=sum(v>1 for v in counts.values()),excluded_ambiguous_readings=sum(v for v in counts.values() if v>1))],[meta,labelmeta,license_meta],labels,cadence


def download(case_id,refresh=False):
    definition=next((r for r in definitions() if r['id']==case_id),None)
    if not definition:raise ValueError('Unknown historical study')
    if not refresh:
        try:return read_case(case_id)
        except (FileNotFoundError,ValueError):pass
    notes=[];independent=case_id.startswith('nab-')
    if independent:times,channels,provenance,labels,cadence=nab(case_id)
    elif case_id=='suez-2021':times,channels,provenance=portwatch();cadence=24
    elif case_id=='canada-smoke-2023':
        times,channels,provenance=epa();cadence=1
        notes+=['EPA parameter 88502 uses non-reference/equivalent PM2.5 methods; it is research data, not a regulatory compliance assessment.','One fixed NYC monitor/POC is selected using only pre-June coverage. It does not represent all northeastern US locations. Finite nonnegative measurements are retained; raw qualifier flags remain in the source archive.']
    elif case_id=='faa-notam-2023':
        times,channels,provenance=bts();cadence=1
        definition=dict(definition,event_start='2023-01-11T11:30:00Z',event_end='2023-01-11T14:00:00Z')
        notes+=['Four Eastern-time airports only; not a census of US air traffic.','Actual BTS delay/cancellation outcomes were published later and grouped by scheduled departure time. They are retrospective outcomes, not live-available predictors.']
    elif case_id=='tonga-2022':
        times,channels,provenance=tonga();cadence=6
        notes+=['Regional seismic catalogue context only; connectivity and cable-outage telemetry are not supplied. Regional earthquakes are not all caused by the eruption.','A zero means no matching catalogued event in this successful query, not proof that no seismic activity occurred.']
    else:
        station='72210612835' if case_id=='ian-2022' else '41749099999';cadence=1 if case_id=='ian-2022' else 3
        start,end=('2022-07-01','2022-10-16') if case_id=='ian-2022' else ('2022-07-01','2022-10-16')
        times,channels,provenance,name=noaa(station,start,end,cadence)
        notes += [f'Single NOAA station: {name} ({station}). It does not measure regional infrastructure damage or flood extent.','Only accepted ISD quality flags are used; missing readings remain null. Precipitation is a reported accumulation, not an inferred flood boundary.']
    if not independent:
        start,end=stamp(definition['event_start']),stamp(definition['event_end'])
        if case_id=='faa-notam-2023':start,end=stamp('2023-01-11T11:30:00Z'),stamp('2023-01-11T14:00:00Z')
        labels=[t<end and t+timedelta(hours=cadence)>start for t in times]
        notes += ['Documented event-window labels are a coarse association target, not independent hour-level operational anomaly ground truth.','A single incident with normal-only pre-event training cannot validate a fitted advance-warning classifier.']
    else:notes+=['Provider timestamps lack timezone metadata; the UTC-formatted replay axis is nominal, not a verified wall-clock timezone.','Absent native-cadence timestamps are represented as null slots; no measurement is interpolated or fabricated.','Published NAB windows include tolerance around anomalies; lead time is relative to annotated window onset, not confirmed physical failure onset.','This evaluator reports its own metrics, not the official NAB score.']
    if independent and channels[0].get('ambiguous_timestamps'):
        notes.append(f"The source contains a clock reversal: {channels[0]['ambiguous_timestamps']} duplicate timestamps ({channels[0]['excluded_ambiguous_readings']} ambiguous readings) are excluded as null. No ordering or replacement value is inferred; original source bytes remain archived.")
    for c in channels:
        c['coverage_pct']=round(100*sum(v is not None for v in c['values'])/len(times),2)
    if any(len(c['values'])!=len(times) for c in channels) or not any(c['coverage_pct']>10 for c in channels):raise ValueError('Historical dataset has insufficient coverage')
    data={'id':case_id,'dataset_mode':'historical','kind':'real_archive','times':[iso(t) for t in times],
          'cadence_hours':cadence,'channels':channels,'labels':labels,
          'label_kind':'independent_annotations' if independent else 'event_window_proxy',
          'label_definition':'Published NAB anomaly windows from combined_windows.json' if independent else ('Overlap with the documented FAA 11:30–14:00 UTC ground stop. Event-window association only.' if case_id=='faa-notam-2023' else 'Overlap with the documented event interval. Event-window association only.'),
          'event_start':definition['event_start'],'event_end':definition['event_end'],
          'description':definition['title']+' — real archived '+', '.join(c['label'] for c in channels)+'.',
          'provenance':provenance+[{'name':'Case documentation / label provenance','url':definition['provenance_url']}],
          'limitations':notes+['Archives may include later revisions. Observation time is not proof of original publication availability; retrospective results do not establish live prediction accuracy.'],
          'method_version':'keyless-history-v1','downloaded_at':iso(datetime.now(UTC)),
          'label_provenance_url':NAB+'/labels/combined_windows.json' if independent else definition['provenance_url']}
    data['dataset_hash']=digest(encoded(data));artifacts.write_bytes(f'historical/cases/{case_id}.json',encoded(data))
    return data
