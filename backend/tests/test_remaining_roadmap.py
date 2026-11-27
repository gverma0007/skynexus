"""Account-free scientific, forecast, transit and reproducibility verification."""
from datetime import datetime,timedelta,timezone
import io,json,zipfile
import numpy as np
import pytest
from app.services.forecasting import forecast
from app.services.benchmark import run
from app.services.artifacts import bundle
from app.services.exposure import parse_assets
from app.services.transit import mbta_delays,static_schedule
from app.backup import verify,connection_env


def test_recursive_forecast_evaluates_each_horizon():
    values=[50+10*np.sin(i*2*np.pi/24) for i in range(180)]
    times=[datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=i) for i in range(180)]
    result=forecast(values,times,3)
    assert len(result['points'])==3
    assert set(result['evaluation']['by_horizon'])=={'1','2','3'}
    assert result['evaluation']['by_horizon']['3']['seasonal_24_hours']['mae']<1e-10
    assert all(p['low']<=p['value']<=p['high'] for p in result['points'])
    times[-1]+=timedelta(hours=1)
    with pytest.raises(ValueError):forecast(values,times)


def test_labelled_benchmark_is_reproducible_and_explicitly_synthetic():
    first=run(42);second=run(42)
    assert first==second
    assert first['dataset_mode']=='synthetic'
    assert len(first['scenarios'])==6
    comparisons={r['method']:r for r in first['comparisons']}
    assert comparisons['quality_aware_fusion']['false_alerts']<comparisons['z_score']['false_alerts']
    assert all(r['precision'] is None or 0<=r['precision']<=1 for r in first['comparisons'])


def test_private_bundle_manifest_and_backup_integrity(tmp_path):
    content=bundle({'database.dump':b'test dump','artifacts/a.txt':b'evidence'},{'test':True})
    assert content==bundle({'database.dump':b'test dump','artifacts/a.txt':b'evidence'},{'test':True})
    target=tmp_path/'backup.zip';target.write_bytes(content)
    assert len(verify(target)['files'])==2
    with pytest.raises(ValueError):bundle({'../secret':b'x'},{})
    bad=tmp_path/'bad.zip'
    with zipfile.ZipFile(bad,'w') as archive:
        archive.writestr('database.dump',b'changed')
        archive.writestr('manifest.json',json.dumps({'files':[{'name':'database.dump','sha256':'wrong'}]}))
    with pytest.raises(ValueError):verify(bad)
    env=connection_env('postgresql://test:secret@db:5432/research')
    assert env['PGHOST']=='db' and env['PGDATABASE']=='research' and env['PGPASSWORD']=='secret'


def test_attributed_assets_validate_coordinates():
    asset={'type':'FeatureCollection','features':[{'type':'Feature','id':'test','geometry':{'type':'Point','coordinates':[-71,42]},'properties':{'name':'Study station','provenance_url':'https://example.org/station','dataset_mode':'synthetic'}}]}
    assert parse_assets(asset)[0]['dataset_mode']=='synthetic'
    asset['features'][0]['geometry']['coordinates']=[400,100]
    with pytest.raises(ValueError):parse_assets(asset)


def test_mbta_matches_only_same_schedule_field():
    document={'included':[{'id':'s','type':'schedule','attributes':{'arrival_time':'2026-01-01T10:00:00Z'}}],
              'data':[{'id':'p','type':'prediction','attributes':{'arrival_time':'2026-01-01T10:03:00Z'},'relationships':{'schedule':{'data':{'id':'s'}},'route':{'data':{'id':'Red'}}}}]}
    rows=mbta_delays(document,datetime(2026,1,1,tzinfo=timezone.utc))
    assert rows[0][2]['value']==180
    assert rows[0][2]['metric']=='predicted_arrival_delay_seconds'
    document['data'][0]['relationships']['schedule']['data']=None
    assert mbta_delays(document,datetime.now(timezone.utc))==[]


def test_gtfs_schedule_handles_after_midnight_and_exceptions(tmp_path):
    target=tmp_path/'gtfs.zip'
    with zipfile.ZipFile(target,'w') as archive:
        archive.writestr('agency.txt','agency_timezone\nAmerica/New_York\n')
        archive.writestr('calendar_dates.txt','service_id,date,exception_type\nweekday,20260101,1\n')
        archive.writestr('trips.txt','route_id,service_id,trip_id\nRed,weekday,trip1\n')
        archive.writestr('stop_times.txt','trip_id,arrival_time,departure_time,stop_id,stop_sequence\ntrip1,25:03:00,25:04:00,stop1,1\n')
    result=static_schedule(target,'20260101')
    assert result[('trip1',1)]['arrival_time'].day==2
    assert result[('trip1',1)]['arrival_time'].hour==1
    assert static_schedule(target,'20260102')=={}


def test_raster_threshold_and_difference_mask_nodata(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from app.services.scientific import footprint,process
    for name,values in [('before',[[10,10],[10,-9999]]),('after',[[5,10],[20,-9999]])]:
        with rasterio.open(tmp_path/f'{name}.tif','w',driver='GTiff',height=2,width=2,count=1,dtype='float32',crs='EPSG:4326',transform=from_origin(-72,43,1,1),nodata=-9999) as raster:raster.write(np.array(values,dtype='float32'),1)
    result=footprint(tmp_path/'after.tif',-25,'lte',tmp_path/'before.tif',True)
    assert result['valid_pixels']==3 and result['selected_pixels']==1
    assert result['coverage_pct']==75
    assert result['geometry']
    with pytest.raises(ValueError):process(tmp_path/'after.tif',source='glofas',observed_at='2026-01-01T00:00:00Z',provenance_url='https://example.org/data',threshold=1,kind='forecast')


def test_netcdf_requires_explicit_slice(tmp_path):
    import xarray as xr
    from app.services.scientific import grid_to_geotiff
    data=xr.Dataset({'discharge':(('time','latitude','longitude'),np.ones((2,2,2)))},coords={'time':[0,1],'latitude':[42,43],'longitude':[288,289]})
    path=tmp_path/'data.nc';data.to_netcdf(path,engine='scipy')
    with pytest.raises(ValueError):grid_to_geotiff(path,tmp_path/'slice.tif','discharge')
    metadata=grid_to_geotiff(path,tmp_path/'slice.tif','discharge',{'time':0})
    assert metadata['variable']=='discharge'


def test_scientific_change_requires_reference_and_dateline_grid_is_not_stretched(tmp_path):
    import xarray as xr
    from app.services.scientific import footprint,grid_to_geotiff
    with pytest.raises(ValueError,match='baseline'):
        footprint(tmp_path/'unused.tif',-25,percent=True)
    data=xr.Dataset({'value':(('latitude','longitude'),np.ones((2,2)))},coords={'latitude':[42,43],'longitude':[179,181]})
    path=tmp_path/'dateline.nc';data.to_netcdf(path,engine='scipy')
    with pytest.raises(ValueError,match='antimeridian'):
        grid_to_geotiff(path,tmp_path/'slice.tif','value')


def test_labelled_validation_excludes_cross_split_future_targets():
    from app.services.validation import evaluate_labelled
    rows=[]
    for i in range(360):
        label=40<=i%60<50
        rows.append({'time':(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat(),'value':50 if label else 100+np.sin(i),'quality':True,'label':label})
    result=evaluate_labelled({'dataset_mode':'synthetic','provenance_url':'https://example.org/simulation','labels_provenance_url':'https://example.org/labels','series':rows})
    assert result['split']=={'training':180,'calibration':90,'test':90}
    assert result['advance_warning']['status']=='heldout_evaluated'
    assert 0<=result['advance_warning']['brier_score']<=1
    assert all(datetime.fromisoformat(p['time'])>=datetime.fromisoformat(rows[270]['time']) for p in result['advance_warning']['predictions'])


def test_gtfs_realtime_respects_cancellations_and_skipped_stops(tmp_path):
    from google.transit import gtfs_realtime_pb2 as pb
    from app.services.transit import match_gtfs
    path=tmp_path/'static.zip'
    with zipfile.ZipFile(path,'w') as archive:
        archive.writestr('agency.txt','agency_timezone\nUTC\n')
        archive.writestr('calendar_dates.txt','service_id,date,exception_type\ns,20260101,1\n')
        archive.writestr('trips.txt','route_id,service_id,trip_id\nr,s,t\n')
        archive.writestr('stop_times.txt','trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt,10:00:00,10:01:00,stop,1\n')
    feed=pb.FeedMessage();feed.header.gtfs_realtime_version='2.0';feed.header.timestamp=1767261600
    item=feed.entity.add();item.id='prediction';item.trip_update.trip.trip_id='t';item.trip_update.trip.start_date='20260101'
    stop=item.trip_update.stop_time_update.add();stop.stop_id='stop';stop.arrival.delay=180
    assert match_gtfs(feed.SerializeToString(),path,'20260101')[0][2]['value']==180
    stop.schedule_relationship=pb.TripUpdate.StopTimeUpdate.SKIPPED
    assert match_gtfs(feed.SerializeToString(),path,'20260101')==[]
    stop.schedule_relationship=pb.TripUpdate.StopTimeUpdate.SCHEDULED
    item.trip_update.trip.schedule_relationship=pb.TripDescriptor.CANCELED
    assert match_gtfs(feed.SerializeToString(),path,'20260101')==[]


def test_grib_slice_uses_the_same_local_processing_path(tmp_path):
    import eccodes
    from app.services.scientific import grid_to_geotiff
    message=eccodes.codes_grib_new_from_samples('regular_ll_sfc_grib2')
    try:
        for key,value in [('Ni',2),('Nj',2),('latitudeOfFirstGridPointInDegrees',43),('latitudeOfLastGridPointInDegrees',42),('longitudeOfFirstGridPointInDegrees',288),('longitudeOfLastGridPointInDegrees',289),('iDirectionIncrementInDegrees',1),('jDirectionIncrementInDegrees',1)]:eccodes.codes_set(message,key,value)
        name=eccodes.codes_get(message,'shortName')
        eccodes.codes_set_values(message,np.array([1,2,3,4]))
        source=tmp_path/'input.grib'
        with source.open('wb') as output:eccodes.codes_write(message,output)
    finally:eccodes.codes_release(message)
    assert grid_to_geotiff(source,tmp_path/'output.tif',name)['variable']==name


def test_optional_s3_path_roundtrips_without_network(monkeypatch):
    from types import SimpleNamespace
    import hashlib
    from app.services import artifacts
    from app.core.config import base_settings
    class Storage:
        def __init__(self):self.objects={}
        def put_object(self,Bucket,Key,Body):self.objects[(Bucket,Key)]=Body
        def get_object(self,Bucket,Key):return {'Body':io.BytesIO(self.objects[(Bucket,Key)])}
    cfg=base_settings();fake=Storage()
    monkeypatch.setattr(cfg,'ARCHIVE_STORAGE','r2');monkeypatch.setattr(cfg,'R2_BUCKET','test-bucket')
    monkeypatch.setattr(artifacts,'client',lambda:fake)
    artifacts.write_bytes('private/file',b'fixture')
    row=SimpleNamespace(storage_key='private/file',sha256=hashlib.sha256(b'fixture').hexdigest())
    assert artifacts.read_bytes(row)==b'fixture'
    fake.objects[('test-bucket','private/file')]=b'corrupt'
    with pytest.raises(ValueError):artifacts.read_bytes(row)


@pytest.mark.parametrize('mode,enabled',[('live',0),('demo',1)])
def test_offline_collector_never_starts_external_acquisition(monkeypatch,mode,enabled):
    import asyncio
    from types import SimpleNamespace
    from app import worker
    calls=[];states=[]
    class DB:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,*args):return None
        def add(self,row):states.append(row)
        def commit(self):pass
    async def local():calls.append('local')
    async def external(*args):raise AssertionError('External acquisition attempted in offline mode')
    monkeypatch.setattr(worker,'get_settings',lambda:SimpleNamespace(LIVE_INGEST=enabled,DATA_MODE=mode))
    monkeypatch.setattr(worker,'SessionLocal',DB)
    monkeypatch.setattr(worker,'CATALOG',[('mbta','transit','MBTA','poll',30,None,'https://example.org')])
    for name in ('analysis','publish','maintenance'):monkeypatch.setattr(worker,name,local)
    for name in ('ais','reference_assets','loop'):monkeypatch.setattr(worker,name,external)
    asyncio.run(worker.main())
    assert calls==['local']*3 and states[0].status=='disabled'


def test_report_patterns_do_not_count_missing_or_partial_hours_as_activity():
    from app.services.reports import describe_patterns
    result=describe_patterns({'windows':{'after_start':'2026-01-01T00:00:00+00:00','after_end':'2026-01-01T05:30:00+00:00'},
        'historical_data':{'baseline_hours':96,'points':[
            {'time':f'2026-01-01T0{i}:00:00+00:00','aircraft':v,'normal_range':[80,120],'storm':50}
            for i,v in enumerate([50,50,None,150,100,0])]}})
    assert result['complete_hours']==5 and result['observed_hours']==4 and result['missing_hours']==1
    assert result['below_band_hours']==2 and result['above_band_hours']==1
    assert result['longest_run_outside_band_hours']==2 and result['weather_coincident_outside_band_hours']==3


def test_feature_projection_keeps_partially_expired_hours_frozen():
    from app.services.features import projection_start
    end=datetime(2026,11,27,5,tzinfo=timezone.utc)
    assert projection_start(end,3)>end-timedelta(days=3)
    assert projection_start(end,90)==end-timedelta(days=30)
