"""Offline spatial-exposure fixture; all entities and hazards are explicitly synthetic."""
from datetime import datetime,timezone
from sqlalchemy import select
from app.core.db import SessionLocal
from app.models.research import Asset,Observation
from app.services.research import record


def seed():
    with SessionLocal() as db:
        for ident,name,point in [('synthetic-crossing','Synthetic transport crossing',[-71.1,42.2]),('synthetic-control','Synthetic control facility',[-70.2,42.8])]:
            if db.get(Asset,ident):continue
            db.add(Asset(id=ident,name=name,asset_type='synthetic_infrastructure',geometry={'type':'Point','coordinates':point},
                         properties_json={'synthetic':True,'method_version':'exposure-demo-v1'},provenance_url='urn:skynexus:synthetic-exposure:v1',
                         dataset_mode='synthetic',available_at=datetime(2000,1,1,tzinfo=timezone.utc)))
        if not db.scalar(select(Observation.id).where(Observation.source=='synthetic-geospatial',Observation.external_id=='footprint-v1')):
            record(db,'synthetic-geospatial','environment','footprint-v1',datetime.now(timezone.utc),
                   {'title':'Synthetic threshold footprint','geometry':{'type':'Polygon','coordinates':[[[-71.5,42],[-70.7,42],[-70.7,42.5],[-71.5,42.5],[-71.5,42]]]},
                    'hazard_kind':'synthetic_flood_exposure','provenance_url':'urn:skynexus:synthetic-exposure:v1',
                    'limitations':['Generated geometry; not a real hazard or verified asset closure.']},kind='synthetic')
        db.commit()

if __name__=='__main__':seed()
