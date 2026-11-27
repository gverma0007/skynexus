"""Sleeping-demo persistence, immutable release data and resource boundaries."""
import hashlib
import json
import uuid
from pathlib import Path
import pytest
from sqlalchemy import text
from app.core.config import base_settings
from app.core.db import engine
from app.services import artifacts


def test_release_manifest_is_complete_and_rejects_tampering(tmp_path):
    from app.prepare_hosted_data import verify
    manifest = verify()
    assert len(manifest['cases']) == 8
    (tmp_path/'manifest.json').write_text(json.dumps({'method_version':manifest['method_version'], 'cases':manifest['cases'],
        'files':[{'key':'case.json','size_bytes':4,'sha256':hashlib.sha256(b'good').hexdigest()}]}))
    (tmp_path/'case.json').write_bytes(b'evil')
    with pytest.raises(ValueError, match='integrity'):verify(tmp_path)


@pytest.fixture
def database_storage(monkeypatch,tmp_path):
    try:
        with engine.connect() as connection:
            if not connection.scalar(text("SELECT to_regclass('artifact_objects')")):pytest.skip('needs migrated database')
    except Exception:pytest.skip('needs migrated database')
    cfg = base_settings()
    monkeypatch.setattr(cfg,'ARCHIVE_STORAGE','database')
    monkeypatch.setattr(cfg,'ARTIFACT_DIR',str(tmp_path))
    yield cfg


def test_database_objects_survive_local_file_loss_and_enforce_quota(database_storage,monkeypatch):
    key='hosting-test/'+str(uuid.uuid4())
    try:
        with engine.connect() as connection:used=connection.scalar(text('SELECT coalesce(sum(size_bytes),0) FROM artifact_objects'))
        monkeypatch.setattr(database_storage,'ARCHIVE_MAX_BYTES',used+5)
        artifacts.write_bytes(key,b'first')
        assert artifacts.read_key(key)==b'first'
        artifacts.write_bytes(key,b'new')
        assert artifacts.read_key(key)==b'new'
        with pytest.raises(artifacts.StorageLimitError):artifacts.write_bytes(key,b'toolong')
        assert artifacts.read_key(key)==b'new'
        with engine.begin() as connection:connection.execute(text('UPDATE artifact_objects SET sha256=:sha WHERE storage_key=:key'),{'sha':'0'*64,'key':key})
        with pytest.raises(ValueError,match='checksum'):artifacts.read_key(key)
    finally:
        with engine.begin() as connection:connection.execute(text('DELETE FROM artifact_objects WHERE storage_key=:key'),{'key':key})


def test_free_demo_uses_cached_cases_private_exports_and_no_queue(database_storage,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import attempts
    from app.services import historical_evaluation
    monkeypatch.setattr(database_storage,'HOSTING_PROFILE','free_demo')
    monkeypatch.setattr(database_storage,'DEMO_DIRECT_LOGIN',True)
    monkeypatch.setattr(historical_evaluation,'evaluate',lambda *_:pytest.fail('Hosted replay must not refit models'))
    attempts.clear()
    with TestClient(app) as client:
        assert client.get('/api/ready').status_code==200
        assert client.get('/api/auth/options').json()['capabilities']['continuous_collection'] is False
        assert client.post('/api/auth/demo').status_code==200
        rows=client.get('/api/cases').json()['cases']
        real=[row for row in rows if row['dataset_mode']=='historical']
        assert len(real)==8 and all(row['status']=='available' for row in real)
        assert client.post('/api/report-jobs',json={}).status_code==409
        assert client.post('/api/experiments',json={}).status_code==409
        assert client.post('/api/cases/suez-2021/download').status_code==409
        assert client.get('/api/stream').status_code==409
        data=client.get('/api/cases/suez-2021/data').json()
        assert data['evaluation']['dataset_hash']==data['dataset_hash']
        response=client.post('/api/cases/suez-2021/evaluate',json={})
        assert response.status_code==201
        asset=response.json()['artifacts'][0]
        assert hashlib.sha256(client.get(asset['url']).content).hexdigest()==asset['sha256']
        again=client.post('/api/cases/suez-2021/evaluate',json={}).json()
        assert again['artifacts'][0]['id']==asset['id']
        cookies=dict(client.cookies)
        with TestClient(app) as stranger:
            assert stranger.get(asset['url']).status_code==401
            stranger.post('/api/auth/demo')
            assert stranger.get(asset['url']).status_code==404
    with TestClient(app) as restarted:
        restarted.cookies.update(cookies)
        assert hashlib.sha256(restarted.get(asset['url']).content).hexdigest()==asset['sha256']
