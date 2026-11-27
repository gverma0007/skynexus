"""Import attributed WGS84 infrastructure GeoJSON locally."""
import argparse,json
from pathlib import Path
from app.services.exposure import parse_assets
from app.models.research import Asset
from app.core.db import SessionLocal
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path)
    args=parser.parse_args()
    records=parse_assets(json.loads(args.file.read_text()))
    with SessionLocal() as db:
        for row in records:db.merge(Asset(**row))
        db.commit()
    print(f'Imported {len(records)} attributed assets')
