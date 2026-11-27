"""Research invariants: causal evaluation and truthful source availability."""
import numpy as np
import pytest
from app.services.experiments import evaluate
from app.core.auth import digest
from app.worker import stamp

def test_evaluation_requires_history():
    with pytest.raises(ValueError):evaluate([1.0]*10)

def test_evaluation_does_not_invent_ground_truth():
    result=evaluate([50+10*np.sin(i*2*np.pi/24) for i in range(240)])
    assert result['ground_truth_metrics'] is None
    assert result['split']=={'training':168,'test':72}
    assert result['forecast_metrics']['seasonal_24_observations']['mae']<0.001
    assert 0<=result['interval_observed_coverage']<=1

def test_session_digest_is_irreversible_identifier():
    assert len(digest('test-token'))==64
    assert digest('test-token')!=digest('other-token')

def test_source_times_remain_timezone_aware():
    assert stamp('2026-11-27T10:00:00Z').utcoffset().total_seconds()==0
    assert stamp(1700000000000).year==2023

def test_modern_orbital_elements_support_six_digit_catalogue_ids():
    import json,math
    from datetime import datetime,timezone
    from app.services.orbits import satrec,propagate,orbit_params
    data={'OBJECT_NAME':'Research fixture','OBJECT_ID':'2026-001A','EPOCH':'2026-11-27T00:00:00.000000','MEAN_MOTION':'15.0','ECCENTRICITY':'0.0001','INCLINATION':'53.0','RA_OF_ASC_NODE':'20.0','ARG_OF_PERICENTER':'30.0','MEAN_ANOMALY':'40.0','EPHEMERIS_TYPE':'0','CLASSIFICATION_TYPE':'U','NORAD_CAT_ID':'100001','ELEMENT_SET_NO':'999','REV_AT_EPOCH':'1','BSTAR':'0','MEAN_MOTION_DOT':'0','MEAN_MOTION_DDOT':'0'}
    encoded=json.dumps(data)
    assert satrec(encoded,'OMM').satnum==100001
    assert all(math.isfinite(x) for x in propagate(encoded,'OMM',datetime(2026,11,27,tzinfo=timezone.utc)))
    assert orbit_params(encoded,'OMM')['element_format']=='OMM'


def test_negative_timezone_offset_preserves_the_instant():
    assert stamp('2026-11-27T10:00:00-05:00').hour==15
    with pytest.raises(ValueError):stamp('not-a-timestamp')
