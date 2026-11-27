"""Private content-addressed artifacts, with a local backend and optional S3/R2."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import uuid
import zipfile
from app.core.config import get_settings
from app.models.research import Artifact


class StorageLimitError(ValueError):
    pass


def client():
    import boto3
    cfg = get_settings()
    if not all((cfg.R2_ENDPOINT_URL, cfg.R2_ACCESS_KEY_ID, cfg.R2_SECRET_ACCESS_KEY, cfg.R2_BUCKET)):
        raise ValueError('R2 storage requires endpoint, access key ID, secret access key, and bucket')
    return boto3.client('s3', endpoint_url=cfg.R2_ENDPOINT_URL,
                        aws_access_key_id=cfg.R2_ACCESS_KEY_ID,
                        aws_secret_access_key=cfg.R2_SECRET_ACCESS_KEY, region_name='auto')


def write_bytes(key, content):
    cfg = get_settings()
    if Path(key).is_absolute() or '..' in Path(key).parts:
        raise ValueError('Invalid artifact key')
    if cfg.ARCHIVE_STORAGE == 'database':
        from sqlalchemy import text
        from app.core.db import engine
        if len(content) > cfg.ARCHIVE_MAX_OBJECT_BYTES:
            raise StorageLimitError('Export exceeds the demo object size limit')
        with engine.begin() as connection:
            # Serialize quota checks across concurrent requests and replicas.
            connection.execute(text('SELECT pg_advisory_xact_lock(729417006)'))
            if cfg.free_demo:
                connection.execute(text('''DELETE FROM artifact_objects o WHERE updated_at < now() - interval '8 hours'
                    AND NOT EXISTS (SELECT 1 FROM research_artifacts a JOIN research_sessions s ON s.token_hash=a.session_hash
                                    WHERE a.storage_key=o.storage_key AND s.expires_at > now())'''))
            used = connection.scalar(text('SELECT COALESCE(sum(size_bytes),0) FROM artifact_objects WHERE storage_key <> :key'), {'key': key})
            if used + len(content) > cfg.ARCHIVE_MAX_BYTES:
                raise StorageLimitError('Demo export storage is full; try a smaller export or contact the administrator')
            connection.execute(text('''INSERT INTO artifact_objects (storage_key,content,sha256,size_bytes)
                VALUES (:key,:content,:sha,:size) ON CONFLICT (storage_key) DO UPDATE SET
                content=excluded.content,sha256=excluded.sha256,size_bytes=excluded.size_bytes,updated_at=now()'''),
                {'key':key,'content':content,'sha':hashlib.sha256(content).hexdigest(),'size':len(content)})
        return
    if cfg.ARCHIVE_STORAGE == 'r2':
        client().put_object(Bucket=cfg.R2_BUCKET, Key=key, Body=content)
        return
    if cfg.ARCHIVE_STORAGE != 'local':
        raise ValueError('ARCHIVE_STORAGE must be local, database or r2')
    root = Path(cfg.ARTIFACT_DIR).resolve()
    destination = (root / key).resolve()
    if not destination.is_relative_to(root):
        raise ValueError('Invalid artifact key')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
        temporary = Path(output.name)
        os.chmod(temporary, 0o600)
        output.write(content)
    os.replace(temporary, destination)


def read_key(key):
    cfg = get_settings()
    if Path(key).is_absolute() or '..' in Path(key).parts:
        raise ValueError('Invalid artifact key')
    if cfg.ARCHIVE_STORAGE == 'database':
        from sqlalchemy import text
        from app.core.db import engine
        with engine.connect() as connection:
            stored = connection.execute(text('SELECT content,sha256 FROM artifact_objects WHERE storage_key=:key'), {'key':key}).first()
        if stored is None: raise FileNotFoundError(key)
        content = bytes(stored.content)
        if hashlib.sha256(content).hexdigest() != stored.sha256:
            raise ValueError('Artifact checksum mismatch')
        return content
    if cfg.ARCHIVE_STORAGE == 'r2':
        return client().get_object(Bucket=cfg.R2_BUCKET, Key=key)['Body'].read()
    else:
        root = Path(cfg.ARTIFACT_DIR).resolve()
        path = (root / key).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Invalid artifact key')
        return path.read_bytes()


def read_bytes(row):
    content = read_key(row.storage_key)
    if hashlib.sha256(content).hexdigest() != row.sha256:
        raise ValueError('Artifact checksum mismatch')
    return content


def save(db, owner, name, content, media_type):
    fingerprint = hashlib.sha256(content).hexdigest()
    if get_settings().free_demo:
        from sqlalchemy import select
        previous = db.scalar(select(Artifact).where(Artifact.session_hash == owner, Artifact.sha256 == fingerprint, Artifact.name == Path(name).name))
        if previous is not None: return previous
    artifact_id = str(uuid.uuid4())
    key = f'{owner}/{artifact_id}/{fingerprint}'
    write_bytes(key, content)
    row = Artifact(id=artifact_id, session_hash=owner, name=Path(name).name,
                   media_type=media_type, sha256=fingerprint, size_bytes=len(content), storage_key=key)
    db.add(row)
    db.flush()
    return row


def describe(row):
    return dict(id=row.id, name=row.name, sha256=row.sha256, size_bytes=row.size_bytes,
                url=f'/api/artifacts/{row.id}')


def bundle(files, metadata):
    """A self-contained ZIP whose manifest fingerprints every included input."""
    out = io.BytesIO()
    manifest = {'schema_version': 1, 'metadata': metadata, 'files': []}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive filename')
            entry=zipfile.ZipInfo(name);entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)
            manifest['files'].append({'name': name, 'size_bytes': len(content),
                                      'sha256': hashlib.sha256(content).hexdigest()})
        entry=zipfile.ZipInfo('manifest.json');entry.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(entry, json.dumps(manifest, sort_keys=True, indent=2))
    return out.getvalue()
