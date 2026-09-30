from sqlalchemy.orm import Session
from app.core.db import SessionLocal, engine
from app.models.aviation import Region
from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

REGIONS = [
    {
        "name": "Middle East",
        "polygon": [
            (30.0, 35.0), (30.0, 60.0), (20.0, 60.0), (20.0, 35.0), (30.0, 35.0)
        ],
        "centroid": (25.0, 47.5)
    },
    {
        "name": "Eastern Europe",
        "polygon": [
            (55.0, 20.0), (55.0, 45.0), (45.0, 45.0), (45.0, 20.0), (55.0, 20.0)
        ],
        "centroid": (50.0, 32.5)
    },
    {
        "name": "South China Sea",
        "polygon": [
            (20.0, 105.0), (20.0, 120.0), (5.0, 120.0), (5.0, 105.0), (20.0, 105.0)
        ],
        "centroid": (12.5, 112.5)
    },
    {
        "name": "North Atlantic",
        "polygon": [
            (60.0, -40.0), (60.0, -10.0), (30.0, -10.0), (30.0, -40.0), (60.0, -40.0)
        ],
        "centroid": (45.0, -25.0)
    },
    {
        "name": "Pacific",
        "polygon": [
            (10.0, 160.0), (10.0, -160.0), (-10.0, -160.0), (-10.0, 160.0), (10.0, 160.0)
        ],
        "centroid": (0.0, 180.0)
    }
]


def upsert_regions():
    db: Session = SessionLocal()
    try:
        inserted = 0
        updated = 0
        for r_data in REGIONS:
            # Create polygon and point geometries
            poly = Polygon(r_data["polygon"])
            # GeoAlchemy2 expects (lon, lat) for WKT/WKB, but our tuples are (lat, lon)
            # Let's swap them for shapely
            poly_swapped = Polygon([(lon, lat) for lat, lon in r_data["polygon"]])
            
            # Centroid is (lat, lon) -> (lon, lat)
            centroid_pt = f"POINT({r_data['centroid'][1]} {r_data['centroid'][0]})"
            
            region = db.query(Region).filter(Region.name == r_data["name"]).first()
            if region:
                region.geom = from_shape(poly_swapped, srid=4326)
                region.centroid = centroid_pt
                updated += 1
            else:
                region = Region(
                    name=r_data["name"],
                    geom=from_shape(poly_swapped, srid=4326),
                    centroid=centroid_pt
                )
                db.add(region)
                inserted += 1
        db.commit()
        print(f"Regions processed: {inserted} inserted, {updated} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    upsert_regions()
