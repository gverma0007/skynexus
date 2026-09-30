import httpx
from datetime import date
from app.core.config import get_settings
from app.models.aviation import Region
from sqlalchemy.orm import Session

# Open-Meteo Archive API
import httpx
import os
import json
from datetime import date
from sqlalchemy.orm import Session
from app.models.aviation import Region
from app.models.weather import WeatherObservation

CACHE_DIR = "app/data/.cache"
os.makedirs(CACHE_DIR, exist_ok=True)

async def fetch_weather(db: Session, region_id: int, start_date: date, end_date: date) -> dict:
    """
    Look up the region's centroid from the regions table, call Open-Meteo Archive API,
    and return the parsed hourly data. Includes basic caching.
    """
    cache_file = os.path.join(CACHE_DIR, f"weather_{region_id}_{start_date}_{end_date}.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise ValueError(f"Region {region_id} not found")

    # Placeholder for actual geometry extraction
    lat, lon = 0.0, 0.0 
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": "wind_speed_10m,precipitation"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        with open(cache_file, "w") as f:
            json.dump(data, f)
            
        return data

def calculate_storm_index(wind_speed: float, precipitation: float) -> float:
    """
    Calculate a storm_index (0-100) from wind speed (km/h) and precipitation (mm).
    """
    wind_score = min(max(wind_speed - 20, 0) * 2, 50)
    precip_score = min(precipitation * 5, 50)
    return wind_score + precip_score

async def fetch_and_store_weather(db: Session, region_id: int, start_date: date, end_date: date):
    """
    Fetch weather data, calculate storm_index, and insert into weather_observations.
    """
    data = await fetch_weather(db, region_id, start_date, end_date)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    precipitations = hourly.get("precipitation", [])

    for i in range(len(times)):
        storm_index = calculate_storm_index(wind_speeds[i], precipitations[i])
        
        observation = WeatherObservation(
            region_id=region_id,
            timestamp=times[i],
            wind_speed_kt=wind_speeds[i] * 0.539957, # Convert km/h to kt
            precipitation_mm=precipitations[i],
            storm_index=storm_index,
            source="open-meteo"
        )
        db.add(observation)
    db.commit()

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
    asyncio.run(fetch_and_store_weather(db, args.region_id, date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)))
    db.close()

