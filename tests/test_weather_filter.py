import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.engine import Base, AnomalyScore, WeatherObservation
from app.ml.correlation import filter_weather_explained_anomalies
from datetime import datetime

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_filter_weather_explained_anomalies(db_session):
    # Create anomaly
    anomaly = AnomalyScore(
        id=1,
        region_id=1,
        timestamp=datetime(2026, 9, 29, 12, 0)
    )
    db_session.add(anomaly)
    
    # Create weather observation (stormy)
    weather = WeatherObservation(
        region_id=1,
        timestamp=datetime(2026, 9, 29, 12, 0),
        storm_index=80
    )
    db_session.add(weather)
    db_session.commit()
    
    filtered = filter_weather_explained_anomalies(db_session, [anomaly])
    assert len(filtered) == 0
    
    # Create weather observation (calm)
    weather2 = WeatherObservation(
        region_id=2,
        timestamp=datetime(2026, 9, 29, 12, 0),
        storm_index=10
    )
    db_session.add(weather2)
    db_session.commit()
    
    anomaly2 = AnomalyScore(
        id=2,
        region_id=2,
        timestamp=datetime(2026, 9, 29, 12, 0)
    )
    db_session.add(anomaly2)
    db_session.commit()
    
    filtered = filter_weather_explained_anomalies(db_session, [anomaly, anomaly2])
    assert len(filtered) == 1
    assert filtered[0].id == 2
