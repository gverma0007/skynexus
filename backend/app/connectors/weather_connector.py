import requests
from datetime import date
from sqlalchemy.orm import Session
from app.models.aviation import Region
from app.core.config import settings

def fetch_weather(db: Session, region_id: str, start_date: date, end_date: date):
    """Fetch weather data for a given region."""
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise ValueError(f"Region {region_id} not found")
    
    # Extract centroid coordinates
    # Note: In a real implementation, we would use ST_AsText or similar to get coordinates
    # For now, we assume a placeholder for the API call
    lat, lon = 0.0, 0.0 
    
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&hourly=temperature_2m,precipitation,wind_speed_10m"
    
    # Placeholder for actual API call
    # response = requests.get(url)
    # return response.json()
    
    return {
        "hourly": {
            "time": [str(start_date)],
            "temperature_2m": [20.0],
            "precipitation": [0.0],
            "wind_speed_10m": [10.0]
        }
    }
