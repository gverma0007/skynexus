"""Archive bounded raw evidence before transactional retention deletes it."""
from datetime import datetime,timezone
import gzip,hashlib,json
from sqlalchemy import select,delete,text
from app.models.research import Observation
from app.services.artifacts import write_bytes


def archive_expired(db,cutoff,limit=5000):
    rows=db.scalars(select(Observation).where(Observation.received_at<cutoff).order_by(Observation.id).limit(limit).with_for_update(skip_locked=True)).all()
    if not rows:return 0
    records=[{'id':r.id,'source':r.source,'external_id':r.external_id,'domain':r.domain,'kind':r.kind,
              'observed_at':r.observed_at.isoformat(),'published_at':r.published_at.isoformat() if r.published_at else None,
              'received_at':r.received_at.isoformat(),'payload':r.payload} for r in rows]
    content=gzip.compress(('\n'.join(json.dumps(r,sort_keys=True) for r in records)+'\n').encode(),mtime=0)
    fingerprint=hashlib.sha256(content).hexdigest()
    key=f'raw/{rows[0].received_at.date()}/{rows[0].id}-{rows[-1].id}-{fingerprint}.jsonl.gz'
    # Failure leaves database rows intact; content-addressed retry is idempotent.
    write_bytes(key,content)
    db.execute(delete(Observation).where(Observation.id.in_([r.id for r in rows])))
    return len(rows)


def archive_legacy(db,cutoff,limit=5000):
    """Retain geometry and source fields before pruning live operational rows."""
    removed=0
    for table in ('flight_observations','satellite_observations','weather_observations'):
        records=db.execute(text(f"""SELECT to_jsonb(t)-'position' ||
            jsonb_build_object('position_geojson',ST_AsGeoJSON(t.position)::jsonb) AS record
            FROM {table} t WHERE t.timestamp<:cutoff AND t.source!='demo_dataset'
            ORDER BY t.timestamp,t.id LIMIT :limit FOR UPDATE SKIP LOCKED"""),{'cutoff':cutoff,'limit':limit}).scalars().all()
        if not records:continue
        content=gzip.compress(('\n'.join(json.dumps(r,sort_keys=True) for r in records)+'\n').encode(),mtime=0)
        fingerprint=hashlib.sha256(content).hexdigest()
        write_bytes(f'raw/legacy/{table}/{fingerprint}.jsonl.gz',content)
        result=db.execute(text(f'DELETE FROM {table} WHERE id=ANY(CAST(:ids AS uuid[]))'),{'ids':[r['id'] for r in records]})
        removed+=result.rowcount
    return removed
