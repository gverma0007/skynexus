from sqlalchemy.orm import Session
from app.models.engine import AnomalyScore

def composite_score(z_score: float, isolation_forest_score: float) -> float:
    """
    Compute a composite anomaly score (0-100).
    Combines Z-score (normalized) and Isolation Forest score.
    """
    # Simple weighted combination
    # Z-score is typically centered at 0, IF score is -1 to 1
    # This is a placeholder for a more robust normalization
    
    # Normalize Z-score (rough mapping)
    z_norm = min(max(abs(z_score) / 3.0, 0.0), 1.0)
    
    # Normalize IF score (negative is anomaly)
    if_norm = 1.0 - min(max(isolation_forest_score, 0.0), 1.0)
    
    score = (z_norm * 0.5 + if_norm * 0.5) * 100.0
    return round(score, 2)

def test_composite_score():
    assert 0 <= composite_score(0.0, 0.5) <= 100
    print("Composite score test passed")

if __name__ == "__main__":
    test_composite_score()
