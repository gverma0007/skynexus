import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.engine import Base, AnomalyScore, Baseline
from app.ml.composite import update_composite_scores

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.models.engine import Base, AnomalyScore, Baseline

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    
    # Mock Base.metadata.create_all to skip spatial tables
    from sqlalchemy import MetaData
    
    # Create a new metadata that only includes the tables we need
    metadata = MetaData()
    from app.models.engine import Baseline, AnomalyScore
    Baseline.__table__.create(engine)
    AnomalyScore.__table__.create(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_update_composite_scores(db_session):
    # Create some anomalies
    anomaly1 = AnomalyScore(
        entity_type="flight",
        entity_id=1,
        region_id=uuid.uuid4(),
        timestamp=datetime(2026, 9, 1),
        feature_name="speed",
        observed_value=100.0,
        z_score=1.0
    )
    anomaly2 = AnomalyScore(
        entity_type="flight",
        entity_id=1,
        region_id=uuid.uuid4(),
        timestamp=datetime(2026, 9, 2),
        feature_name="speed",
        observed_value=100.0,
        z_score=2.0
    )
    db_session.add(anomaly1)
    db_session.add(anomaly2)
    db_session.commit()
    
    count = update_composite_scores(db_session, datetime(2026, 9, 1), datetime(2026, 9, 3))
    
    assert count == 2
    assert anomaly1.composite_score is not None
    assert anomaly2.composite_score is not None
