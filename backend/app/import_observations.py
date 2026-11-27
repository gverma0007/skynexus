"""Import attributed scientific/curated JSONL; never relabel imports as live feeds."""
import argparse,json
from datetime import datetime
from pathlib import Path
from app.core.db import SessionLocal
from app.services.research import record, source_result

def parse_record(row):
    required=('external_id','observed_at','payload')
    if any(key not in row for key in required):raise ValueError('Missing external_id, observed_at or payload')
    when=datetime.fromisoformat(row['observed_at'].replace('Z','+00:00'))
    if when.tzinfo is None:raise ValueError('Observation timestamp must include timezone')
    if not isinstance(row['payload'],dict):raise ValueError('payload must be an object')
    if not row['payload'].get('provenance_url'):raise ValueError('Imported evidence requires provenance_url')
    if row.get('published_at'):
        published=datetime.fromisoformat(row['published_at'].replace('Z','+00:00'))
        if published.tzinfo is None:raise ValueError('Publication timestamp must include timezone')
    kind=row.get('kind','observed')
    if kind=='forecast' and not row.get('published_at'):raise ValueError('Forecasts require published_at (issue time)')
    if kind not in ('observed','forecast','derived','synthetic','context'):raise ValueError('Invalid evidence kind')
    return row['external_id'],when,row['payload'],kind

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path);parser.add_argument('--source',required=True);parser.add_argument('--domain',required=True)
    args=parser.parse_args()
    # Validate the complete file before committing anything.
    records=[parse_record(json.loads(line)) for line in args.file.read_text().splitlines() if line.strip()]
    with SessionLocal() as db:
        count=0
        raw=[json.loads(line) for line in args.file.read_text().splitlines() if line.strip()]
        for parsed,row in zip(records,raw):
            published=datetime.fromisoformat(row['published_at'].replace('Z','+00:00')) if row.get('published_at') else None
            count+=record(db,args.source,args.domain,*parsed,published_at=published)
        source_result(db,args.source,count);db.commit()
    print(f'Imported {count} attributed observations')
