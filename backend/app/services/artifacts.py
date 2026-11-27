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
    if cfg.ARCHIVE_STORAGE == 'r2':
        client().put_object(Bucket=cfg.R2_BUCKET, Key=key, Body=content)
        return
    if cfg.ARCHIVE_STORAGE != 'local':
        raise ValueError('ARCHIVE_STORAGE must be local or r2')
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


def read_bytes(row):
    cfg = get_settings()
    if cfg.ARCHIVE_STORAGE == 'r2':
        content = client().get_object(Bucket=cfg.R2_BUCKET, Key=row.storage_key)['Body'].read()
    else:
        root = Path(cfg.ARTIFACT_DIR).resolve()
        path = (root / row.storage_key).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Invalid artifact key')
        content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != row.sha256:
        raise ValueError('Artifact checksum mismatch')
    return content


def save(db, owner, name, content, media_type):
    fingerprint = hashlib.sha256(content).hexdigest()
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
