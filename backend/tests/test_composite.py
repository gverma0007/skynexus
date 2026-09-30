import pytest
from app.ml.composite import composite_score

def test_composite_score():
    # Normal case
    score, severity = composite_score(0.5, 10.0)
    assert severity == "normal"
    
    # Medium case
    score, severity = composite_score(2.5, 50.0)
    assert severity == "low"
    
    # High case
    score, severity = composite_score(4.0, 90.0)
    assert severity == "high"
