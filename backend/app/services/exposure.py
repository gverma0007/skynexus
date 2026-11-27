"""Attributed spatial intersections; exposure does not establish damage or causation."""
from datetime import datetime, timezone
from shapely.geometry import shape, mapping
from sqlalchemy import select
from app.models.research import Asset, Observation


def parse_assets(document):
    if document.get('type')!='FeatureCollection':
        raise ValueError('Assets must be a GeoJSON FeatureCollection')
    output=[]
    for item in document.get('features',[]):
        properties=item.get('properties',{})
        ident=str(item.get('id',properties.get('id','')))
        if not ident or len(ident)>80 or not properties.get('name') or not properties.get('provenance_url'):
            raise ValueError('Every asset needs id, name and provenance_url')
        geometry=shape(item['geometry'])
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError('Asset geometry must be valid and nonempty')
        west,south,east,north=geometry.bounds
        if not (-180<=west<=east<=180 and -90<=south<=north<=90):
            raise ValueError('Asset coordinates must be WGS84 longitude/latitude')
        mode=properties.get('dataset_mode','live')
        if mode not in ('live','synthetic'):raise ValueError('Asset dataset_mode must be live or synthetic')
        available=datetime.fromisoformat(properties.get('available_at',datetime.now(timezone.utc).isoformat()).replace('Z','+00:00'))
        if available.tzinfo is None:raise ValueError('Asset available_at requires timezone')
        output.append(dict(id=ident,name=properties['name'],asset_type=properties.get('asset_type','infrastructure'),
                           geometry=mapping(geometry),properties_json=properties,provenance_url=properties['provenance_url'],
                           dataset_mode=mode,available_at=available))
    return output


def exposures(db, mode='live', as_of=None):
    now=as_of or datetime.now(timezone.utc)
    assets=db.scalars(select(Asset).where(Asset.dataset_mode=='synthetic' if mode=='demo' else Asset.dataset_mode=='live',Asset.available_at<=now)).all()
    query=select(Observation).where(Observation.received_at<=now)
    query=query.where(Observation.kind=='synthetic') if mode=='demo' else query.where(Observation.kind!='synthetic')
    rows=db.scalars(query.order_by(Observation.received_at.desc()).limit(2000)).all()
    output=[]
    for observation in rows:
        p=observation.payload
        if not p.get('geometry') or not p.get('hazard_kind'):continue
        if observation.published_at and observation.published_at>now:continue
        if observation.kind!='forecast' and observation.observed_at>now:continue
        footprint=shape(p['geometry'])
        for asset in assets:
            if not shape(asset.geometry).intersects(footprint):continue
            output.append(dict(asset_id=asset.id,name=asset.name,asset_type=asset.asset_type,hazard_source=observation.source,
                               hazard_kind=p['hazard_kind'],relation='intersects',observed_at=observation.observed_at.isoformat(),
                               received_at=observation.received_at.isoformat(),kind=observation.kind,
                               provenance_url=p.get('provenance_url'),dataset_mode=mode,
                               limitations=['Spatial intersection indicates exposure, not damage, closure or causation.']))
    return output


def regional_exposures(db,region_id,mode='live',as_of=None):
    import json
    from sqlalchemy import text
    region=db.execute(text('SELECT ST_AsGeoJSON(geom) FROM regions WHERE id=:id'),{'id':region_id}).scalar()
    if not region:return []
    polygon=shape(json.loads(region))
    assets={a.id:a for a in db.scalars(select(Asset)).all()}
    return [row for row in exposures(db,mode,as_of) if row['asset_id'] in assets and polygon.intersects(shape(assets[row['asset_id']].geometry))]
