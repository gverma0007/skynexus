import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.engine import Base, AnomalyScore, Event, EventCorrelation
from app.ml.correlation import persist_correlations
from datetime import datetime
from shapely.geometry import Point
from geoalchemy2.shape import from_shape

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_persist_correlations(db_session):
    # Create anomaly
    anomaly = AnomalyScore(
        id=1,
        timestamp=datetime(2026, 9, 29, 12, 0),
        position=from_shape(Point(0, 0))
    )
    db_session.add(anomaly)
    
    # Create event
    event = Event(
        id=1,
        event_date=datetime(2026, 9, 29, 13, 0),
        position=from_shape(Point(0.1, 0.1))
    )
    db_session.add(event)
    db_session.commit()
    
    persist_correlations(db_session, [anomaly])
    
    correlation = db_session.query(EventCorrelation).first()
    assert correlation is not None
    assert correlation.anomaly_id == 1
    assert correlation.event_id == 1
    assert correlation.confidence_score > 0
