"""Integration tests against a running database (skipped when unavailable).

Run inside the stack: docker compose exec backend python -m pytest -q
"""
import pytest
from sqlalchemy import text

try:
    from app.core.db import engine

    with engine.connect() as c:
        HAS_DATA = (c.execute(text("SELECT COUNT(*) FROM regions")).scalar() or 0) > 0
except Exception:  # pragma: no cover
    HAS_DATA = False

pytestmark = pytest.mark.skipif(not HAS_DATA, reason="needs a seeded database")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    from app.core.config import base_settings
    from app.core.auth import password_hasher
    cfg=base_settings()
    original=cfg.DEMO_PASSWORD_HASH
    cfg.DEMO_PASSWORD_HASH=password_hasher.hash('test-only-password')
    with TestClient(app) as test_client:
        assert test_client.post('/api/auth/login',json={'email':cfg.DEMO_EMAIL,'password':'test-only-password'}).status_code==200
        yield test_client
    cfg.DEMO_PASSWORD_HASH=original


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_regions_have_scores(client):
    regions = client.get("/api/regions").json()
    assert len(regions) >= 15
    for r in regions:
        assert 0 <= r["composite_index"] <= 100
        assert r["status"] in ("Calm", "Watch", "Elevated", "Critical")


def test_pacific_does_not_cover_gulf_of_guinea(client):
    outline = {o["name"]: o["ring"] for o in client.get("/api/regions/outline").json()}
    lons = [p[1] for p in outline["Pacific"]]
    assert max(lons) - min(lons) <= 40


def test_region_endpoints(client):
    rid = client.get("/api/regions").json()[0]["region_id"]
    for path in ("", "/history", "/overhead", "/forecast", "/analysis"):
        assert client.get(f"/api/regions/{rid}{path}").status_code == 200


def test_report_round_trip(client):
    rid = client.get("/api/regions").json()[0]["region_id"]
    created = client.post("/api/reports", json={"region_id": rid, "hours": 6})
    assert created.status_code == 201
    body = created.json()
    assert body["overall_assessment"].endswith("Correlation does not establish causation.")
    assert client.get(f"/api/reports/{body['id']}").status_code == 200
    assert client.delete(f"/api/reports/{body['id']}").status_code == 204


def test_misc_endpoints(client):
    for path in ("/api/stats", "/api/flights/live", "/api/flights/deviations", "/api/satellites/live", "/api/events",
                 "/api/anomalies", "/api/alerts", "/api/system/health", "/api/system/mode", "/api/search?q=a"):
        assert client.get(path).status_code == 200, path


def test_flight_route_deviation(client):
    flights = client.get("/api/flights/live").json()
    if flights:
        icao = flights[0]["icao24"]
        res = client.get(f"/api/flights/{icao}/route")
        assert res.status_code == 200
        body = res.json()
        assert body["icao24"] == icao
        if body["route"]:
            assert "waypoints" in body["route"]
            assert body["deviation"]["status"] in ("on_route", "minor_deviation", "significant_deviation")


def test_system_mode_toggle(client):
    res = client.get("/api/system/mode")
    assert res.status_code == 200
    orig_mode = res.json()["data_mode"]

    # A viewer must not change collection or another viewer's dataset.
    assert client.post("/api/system/mode", json={"mode": "demo"}).status_code == 403
    assert client.get("/api/system/mode").json()["data_mode"] == orig_mode


def test_authentication_and_session_isolation(client):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import base_settings
    stranger=TestClient(app)
    assert stranger.get('/api/regions').status_code==401
    assert stranger.get('/api/sources').status_code==401
    assert stranger.post('/api/auth/login',json={'email':'wrong@example.org','password':'wrong'}).status_code==401
    assert stranger.post('/api/auth/login',json={'email':base_settings().DEMO_EMAIL,'password':'test-only-password'}).status_code==200
    region=client.get('/api/regions').json()[0]['region_id']
    report=client.post('/api/reports',json={'region_id':region,'hours':6}).json()
    assert stranger.get('/api/reports/'+report['id']).status_code==404
    assert report['id'] not in {r['id'] for r in stranger.get('/api/reports').json()}
    assert report['id'] in {r['id'] for r in client.get('/api/reports').json()}
    assert client.get('/api/reports/'+report['id']+'/export?format=pdf').headers['content-type']=='application/pdf'
    markdown=client.get('/api/reports/'+report['id']+'/export?format=markdown').text
    assert 'Supporting source evidence' in markdown and 'Pattern analysis' in markdown and 'Alternative:' in markdown
    assert stranger.post('/api/auth/logout').status_code==200
    assert stranger.get('/api/auth/me').status_code==401


def test_research_api_source_truth(client):
    sources=client.get('/api/sources').json()['sources']
    ais=next(s for s in sources if s['id']=='aisstream')
    assert ais['delivery']=='native_stream'
    assert 'configured' in ais
    assert client.get('/api/snapshot').status_code==200
    assert client.get('/api/signals/environment').status_code==200
    assert client.get('/api/regions?as_of=invalid').status_code==422
    assert client.post('/api/ingest/live').status_code==403

def test_observation_outbox_and_hourly_feature_are_idempotent(client):
    from datetime import datetime,timezone
    from sqlalchemy import select
    from app.core.db import SessionLocal
    from app.services.research import record
    from app.models.research import Observation,HourlyFeature
    with SessionLocal() as db:
        try:
            now=datetime.now(timezone.utc)
            payload={'metric':'test-metric','entity_id':'test-entity','value':4.5,'unit':'test'}
            assert record(db,'test-source','research','test-once',now,payload)
            assert not record(db,'test-source','research','test-once',now,payload)
            feature=db.scalar(select(HourlyFeature).where(HourlyFeature.source=='test-source'))
            assert feature.sample_count==1
            assert feature.value_sum==4.5
        finally:db.rollback()


def test_viewer_dataset_does_not_relabel_live_normalized_signals(client):
    assert client.get('/api/signals/space?data_mode=demo').json()['observations']==[]
    assert client.get('/api/signals/space/analysis?data_mode=demo').json()['series']==[]
    assert client.get('/api/flights/live?as_of=1970-01-01T00:00:00Z').json()==[]
    assert client.get('/api/events?as_of=1970-01-01T00:00:00Z').json()==[]

def test_satellite_series_excludes_other_dataset(client):
    from datetime import datetime,timezone
    from app.core.db import SessionLocal
    from app.core.config import request_mode
    from app.models.aviation import Satellite,SatelliteObservation
    from app.services.series import get_series
    with SessionLocal() as db:
        try:
            when=datetime(2000,1,3,tzinfo=timezone.utc)
            sat=Satellite(norad_id=100000001,name='Isolated synthetic fixture',category='other')
            db.add(sat);db.flush()
            db.add(SatelliteObservation(satellite_id=sat.id,timestamp=when,position='POINTZ(-71 42 400)',altitude_km=400,source='demo_dataset'))
            db.flush()
            token=request_mode.set('live')
            try:
                live=get_series(db,now=when)
                assert all(not any(v for v in rs.satellites if v is not None) for rs in live.regions.values())
            finally:request_mode.reset(token)
            token=request_mode.set('demo')
            try:
                demo=get_series(db,now=when)
                assert any(any(v for v in rs.satellites if v is not None) for rs in demo.regions.values())
            finally:request_mode.reset(token)
        finally:db.rollback()
