from sqlalchemy.orm import Session
from app.core.db import SessionLocal
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
        # Central Pacific, east of the dateline (includes Hawaii). Kept within
        # -180..-150 so the polygon never wraps the antimeridian: a 160..-160
        # box in EPSG:4326 is read as 320 degrees wide and swallows the tropics.
        "name": "Pacific",
        "polygon": [
            (25.0, -180.0), (25.0, -150.0), (-10.0, -150.0), (-10.0, -180.0), (25.0, -180.0)
        ],
        "centroid": (8.0, -165.0)
    },
    # --- Extended strategic monitoring zones ---
    {
        "name": "Black Sea",
        "polygon": [
            (48.0, 27.0), (48.0, 42.0), (40.5, 42.0), (40.5, 27.0), (48.0, 27.0)
        ],
        "centroid": (44.0, 34.0)
    },
    {
        "name": "Red Sea",
        "polygon": [
            (30.0, 32.0), (30.0, 44.0), (12.0, 44.0), (12.0, 32.0), (30.0, 32.0)
        ],
        "centroid": (20.0, 38.5)
    },
    {
        "name": "Taiwan Strait",
        "polygon": [
            (27.5, 116.0), (27.5, 126.0), (20.0, 126.0), (20.0, 116.0), (27.5, 116.0)
        ],
        "centroid": (24.0, 120.0)
    },
    {
        "name": "Korean Peninsula",
        "polygon": [
            (43.0, 122.0), (43.0, 135.0), (33.0, 135.0), (33.0, 122.0), (43.0, 122.0)
        ],
        "centroid": (38.0, 127.5)
    },
    {
        "name": "Eastern Mediterranean",
        "polygon": [
            (37.0, 22.0), (37.0, 36.0), (30.5, 36.0), (30.5, 22.0), (37.0, 22.0)
        ],
        "centroid": (34.0, 30.0)
    },
    {
        "name": "Baltic Sea",
        "polygon": [
            (60.0, 16.0), (60.0, 30.0), (53.5, 30.0), (53.5, 16.0), (60.0, 16.0)
        ],
        "centroid": (57.0, 20.0)
    },
    {
        "name": "Horn of Africa",
        "polygon": [
            (18.0, 38.0), (18.0, 55.0), (5.0, 55.0), (5.0, 38.0), (18.0, 38.0)
        ],
        "centroid": (10.0, 46.0)
    },
    {
        "name": "Bay of Bengal",
        "polygon": [
            (22.0, 80.0), (22.0, 95.0), (5.0, 95.0), (5.0, 80.0), (22.0, 80.0)
        ],
        "centroid": (13.0, 88.0)
    },
    {
        "name": "Caribbean",
        "polygon": [
            (27.0, -92.0), (27.0, -58.0), (12.0, -58.0), (12.0, -92.0), (27.0, -92.0)
        ],
        "centroid": (18.0, -73.0)
    },
    {
        "name": "Gulf of Guinea",
        "polygon": [
            (15.0, -20.0), (15.0, 15.0), (-5.0, 15.0), (-5.0, -20.0), (15.0, -20.0)
        ],
        "centroid": (3.0, 5.0)
    },
]


def upsert_regions():
    db: Session = SessionLocal()
    try:
        inserted = 0
        updated = 0
        for r_data in REGIONS:
            # Tuples are (lat, lon); WKT/shapely want (lon, lat).
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
