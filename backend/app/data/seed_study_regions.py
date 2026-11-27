"""Explicit study footprints; provider coverage is independently reported."""
from sqlalchemy import text
from app.core.db import SessionLocal

REGIONS=[('Boston / New England',-72.5,41,-69.5,43.5),('South Florida / Florida Straits',-83,23,-78,27),('Red Sea',32,12,44,30)]
if __name__=='__main__':
    with SessionLocal() as db:
        for name,west,south,east,north in REGIONS:
            db.execute(text('INSERT INTO regions (id,name,geom,centroid) VALUES (gen_random_uuid(),:name,ST_MakeEnvelope(:w,:s,:e,:n,4326),ST_SetSRID(ST_MakePoint((:w+:e)/2.0,(:s+:n)/2.0),4326)) ON CONFLICT (name) DO NOTHING'),dict(name=name,w=west,s=south,e=east,n=north))
        db.commit()
