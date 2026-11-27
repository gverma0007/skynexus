"""Keyless, attributed study-area airports from OurAirports' public CSV."""
import csv,io
from datetime import datetime,timezone
import httpx
from app.models.research import Asset
from app.core.db import SessionLocal
from app.services.research import source_result
URL='https://davidmegginson.github.io/ourairports-data/airports.csv'
BOUNDS=[(-72.5,41,-69.5,43.5),(-83,23,-78,27),(32,12,44,30)]


def parse_airports(content):
    output=[]
    for row in csv.DictReader(io.StringIO(content)):
        if row.get('type') not in ('large_airport','medium_airport'):continue
        lat,lon=float(row['latitude_deg']),float(row['longitude_deg'])
        if not any(w<=lon<=e and s<=lat<=n for w,s,e,n in BOUNDS):continue
        output.append(dict(id='airport-'+row['ident'],name=row['name'],asset_type='airport',
                           geometry={'type':'Point','coordinates':[lon,lat]},
                           properties_json={'icao':row['ident'],'iata':row.get('iata_code'),'reference_geometry_only':True},
                           provenance_url=URL,dataset_mode='live',available_at=datetime.now(timezone.utc)))
    return output[:200]


def fetch():
    with httpx.Client(timeout=30,follow_redirects=True) as client:
        response=client.get(URL);response.raise_for_status()
    records=parse_airports(response.text)
    with SessionLocal() as db:
        for record in records:db.merge(Asset(**record))
        source_result(db,'reference-assets',len(records));db.commit()
    return len(records)

if __name__=='__main__':print(f'Imported {fetch()} attributed airport reference assets')
