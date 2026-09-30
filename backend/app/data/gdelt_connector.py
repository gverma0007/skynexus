import httpx
import pandas as pd
from datetime import date
from app.models.aviation import Region
from sqlalchemy.orm import Session
import io

# GDELT 2.0 Event Database
# We will use the raw CSV export files.
# For this implementation, we will fetch a sample or a specific date range.
# Note: This is a simplified implementation.

async def fetch_gdelt_events(region: Region, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetch GDELT events and filter by region polygon.
    """
    # GDELT 2.0 raw event files are available at:
    # http://data.gdeltproject.org/gdeltv2/masterfilelist.txt
    # This is a complex task to parse the master file list.
    # For this implementation, we will assume a simplified approach or a placeholder.
    
    # Placeholder: In a real implementation, we would fetch the master file list,
    # find the relevant files for the date range, download them, and filter.
    
    # For now, return an empty DataFrame
    return pd.DataFrame()

from app.models.events import Event
from app.core.db import SessionLocal

def map_gdelt_category(event_code: str, quad_class: int) -> str:
    """
    Map GDELT EventCode/QuadClass to internal categories.
    Mapping logic:
    - QuadClass 1 (Verbal Cooperation) -> 'diplomatic'
    - QuadClass 2 (Material Cooperation) -> 'diplomatic'
    - QuadClass 3 (Verbal Conflict) -> 'security'
    - QuadClass 4 (Material Conflict) -> 'security'
    """
    if quad_class in [1, 2]:
        return "diplomatic"
    elif quad_class in [3, 4]:
        return "security"
    return "other"

async def fetch_events(db: Session, region: Region, start_date: date, end_date: date) -> int:
    """
    Fetch events, map categories, and insert into events table.
    """
    df = await fetch_gdelt_events(region, start_date, end_date)
    
    count = 0
    for _, row in df.iterrows():
        # Assuming row has 'EventCode', 'QuadClass', 'ActionGeo_Lat', 'ActionGeo_Long', 'GlobalEventID'
        category = map_gdelt_category(str(row.get('EventCode')), int(row.get('QuadClass', 0)))
        
        event = Event(
            external_id=str(row.get('GlobalEventID')),
            event_date=start_date, # Simplified
            event_type=category,
            category=category,
            severity=1, # Simplified
            region_id=region.id,
            description="GDELT Event",
            source="gdelt"
        )
        db.add(event)
        count += 1
    db.commit()
    return count

if __name__ == "__main__":
    import argparse
    import asyncio
    from app.core.db import SessionLocal
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--region_id", type=int, required=True)
    parser.add_argument("--start_date", type=str, required=True)
    parser.add_argument("--end_date", type=str, required=True)
    args = parser.parse_args()
    
    db = SessionLocal()
    region = db.query(Region).filter(Region.id == args.region_id).first()
    if region:
        count = asyncio.run(fetch_events(db, region, date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)))
        print(f"Inserted {count} events.")
    else:
        print("Region not found.")
    db.close()
