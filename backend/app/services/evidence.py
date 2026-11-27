"""Freeze supporting measurements without inventing geospatial precision."""
from datetime import datetime
from sqlalchemy import select,text,or_
from shapely.geometry import shape,Point
from app.models.research import Observation
from app.services.exposure import exposures


def collect_evidence(db,region_id,start,end,mode):
    import json
    region=db.execute(text('SELECT ST_AsGeoJSON(geom) FROM regions WHERE id=:id'),{'id':region_id}).scalar()
    polygon=shape(json.loads(region)) if region else None
    query=select(Observation).where(Observation.received_at<=end,Observation.observed_at>=start,
                                   or_(Observation.observed_at<=end,Observation.kind=='forecast'),
                                   or_(Observation.published_at==None,Observation.published_at<=end))
    query=query.where(Observation.kind=='synthetic') if mode=='demo' else query.where(Observation.kind!='synthetic')
    rows=db.scalars(query.order_by(Observation.received_at.desc()).limit(1000)).all()
    output=[]
    for row in rows:
        p=row.payload;coordinates=p.get('coordinates') or {}
        lat=p.get('lat',coordinates.get('latitude'));lon=p.get('lon',coordinates.get('longitude'))
        spatial=False
        if polygon is not None:
            if isinstance(lat,(int,float)) and isinstance(lon,(int,float)):spatial=polygon.intersects(Point(lon,lat))
            elif p.get('geometry'):spatial=polygon.intersects(shape(p['geometry']))
        if not spatial and p.get('scope')!='global':continue
        output.append({'id':row.id,'source':row.source,'kind':row.kind,'observed_at':row.observed_at.isoformat(),
                       'published_at':row.published_at.isoformat() if row.published_at else None,
                       'received_at':row.received_at.isoformat(),'relation':'intersects_region' if spatial else 'global_context_only',
                       'payload':p,'interpretation':'Measurement/context, not proof of an explanation'})
    return output
