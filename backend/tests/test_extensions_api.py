"""Integration checks for private artifacts and scientific evidence availability."""
import json,io,zipfile
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import text
try:
    from app.core.db import engine
    with engine.connect() as connection:HAS_DB=bool(connection.execute(text("SELECT to_regclass('research_artifacts')")).scalar())
except Exception:HAS_DB=False
pytestmark=pytest.mark.skipif(not HAS_DB,reason='needs migrated database')

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import base_settings
    from app.core.auth import password_hasher
    cfg=base_settings();old=cfg.DEMO_PASSWORD_HASH
    cfg.DEMO_PASSWORD_HASH=password_hasher.hash('extensions-test-only')
    with TestClient(app) as value:
        assert value.post('/api/auth/login',json={'email':cfg.DEMO_EMAIL,'password':'extensions-test-only'}).status_code==200
        yield value
    cfg.DEMO_PASSWORD_HASH=old


def test_case_catalogue_never_implies_undownloaded_data(client,tmp_path,monkeypatch):
    from app.core.config import base_settings
    monkeypatch.setattr(base_settings(),'ARTIFACT_DIR',str(tmp_path))
    monkeypatch.setattr(base_settings(),'ARCHIVE_STORAGE','local')
    rows=client.get('/api/cases').json()['cases']
    assert len(rows)==14
    history=next(r for r in rows if r['dataset_mode']=='historical')
    assert history['status']=='download_required'
    assert client.get('/api/cases/'+history['id']+'/data').status_code==404
    synthetic=client.get('/api/cases/synthetic-weather/data').json()
    assert synthetic['dataset_mode']=='synthetic' and len(synthetic['traffic'])==240


def test_benchmark_artifact_is_private_and_checksums_match(client):
    result=client.post('/api/experiments/benchmark',json={})
    assert result.status_code==201
    body=result.json();assert body['dataset_mode']=='synthetic'
    asset=body['artifacts'][0]
    response=client.get(asset['url']);assert response.status_code==200
    import hashlib
    assert hashlib.sha256(response.content).hexdigest()==asset['sha256']
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert 'labelled_inputs.json' in archive.namelist()
    from fastapi.testclient import TestClient
    from app.main import app
    stranger=TestClient(app)
    assert stranger.get(asset['url']).status_code==401
    from app.core.config import base_settings
    stranger.post('/api/auth/login',json={'email':base_settings().DEMO_EMAIL,'password':'extensions-test-only'})
    assert stranger.get(asset['url']).status_code==404


def test_exposure_keeps_forecast_and_observed_semantics(client):
    from app.core.db import SessionLocal
    from app.models.research import Asset,Observation
    from app.services.exposure import exposures
    with SessionLocal() as db:
        try:
            now=datetime.now(timezone.utc)
            db.add(Asset(id='test-exposure-asset',name='Synthetic test station',asset_type='station',geometry={'type':'Point','coordinates':[-71,42]},properties_json={},provenance_url='https://example.org/station',dataset_mode='synthetic',available_at=now-timedelta(hours=1)))
            db.add(Observation(source='test-raster',external_id='test-footprint',domain='environment',observed_at=now,kind='synthetic',payload={'geometry':{'type':'Polygon','coordinates':[[[-72,41],[-70,41],[-70,43],[-72,43],[-72,41]]]},'hazard_kind':'test','provenance_url':'https://example.org/product'}))
            db.flush()
            found=exposures(db,'demo',now+timedelta(seconds=1))
            assert any(r['asset_id']=='test-exposure-asset' for r in found)
            assert all(r['asset_id']!='test-exposure-asset' for r in exposures(db,'live',now+timedelta(seconds=1)))
        finally:db.rollback()


def test_insufficient_forecast_history_is_explicit(client):
    response=client.get('/api/signals/environment/forecast?source=unknown&entity=unknown&metric=unknown&horizon=6')
    assert response.status_code==200 and response.json()['status']=='insufficient_data'
    assert client.get('/api/signals/environment/forecast?source=x&entity=x&metric=x&horizon=25').status_code==422


def test_live_signals_exclude_simulation_and_preserve_canonical_metadata(client):
    from app.core.db import SessionLocal
    from app.models.research import Observation
    from sqlalchemy import delete
    now=datetime.now(timezone.utc)
    with SessionLocal() as db:
        for kind in ('synthetic','observed'):
            db.add(Observation(source='signal-isolation-test',external_id=kind,domain='test-isolation',observed_at=now,kind=kind,
                               payload={'source':'spoof','kind':'synthetic','title':kind}))
        db.commit()
    try:
        rows=client.get('/api/signals/test-isolation').json()['observations']
        assert len(rows)==1 and rows[0]['kind']=='observed' and rows[0]['source']=='signal-isolation-test'
    finally:
        with SessionLocal() as db:
            db.execute(delete(Observation).where(Observation.source=='signal-isolation-test'));db.commit()


def test_legacy_retention_archives_geometry_and_preserves_rows_if_storage_fails(monkeypatch):
    import gzip,uuid
    from app.services import retention
    from app.models.aviation import WeatherObservation,Region
    from app.core.db import SessionLocal
    from sqlalchemy import select,func
    cutoff=datetime.now(timezone.utc)-timedelta(days=365)
    with SessionLocal() as db:
        try:
            ident=uuid.uuid4()
            db.add(WeatherObservation(id=ident,region_id=db.scalar(select(Region.id).limit(1)),timestamp=cutoff-timedelta(days=1),
                position='SRID=4326;POINT(-71 42)',wind_speed_kt=5,precipitation_mm=1,storm_index=10,source='test-retention'))
            db.flush()
            def fail(*args):raise OSError('simulated unavailable storage')
            monkeypatch.setattr(retention,'write_bytes',fail)
            with pytest.raises(OSError):retention.archive_legacy(db,cutoff)
            assert db.scalar(select(func.count()).select_from(WeatherObservation).where(WeatherObservation.id==ident))==1
            saved=[];monkeypatch.setattr(retention,'write_bytes',lambda key,content:saved.append((key,content)))
            assert retention.archive_legacy(db,cutoff)==1
            assert db.scalar(select(func.count()).select_from(WeatherObservation).where(WeatherObservation.id==ident))==0
            row=json.loads(gzip.decompress(saved[0][1]).decode())
            assert row['position_geojson']['coordinates']==[-71,42] and row['source']=='test-retention'
        finally:db.rollback()
