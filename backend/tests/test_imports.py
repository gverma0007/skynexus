from app.import_observations import parse_record
import pytest

def test_import_requires_attribution_and_timezone():
    with pytest.raises(ValueError):parse_record({'external_id':'a','observed_at':'2026-11-27T00:00:00','payload':{}})
    with pytest.raises(ValueError):parse_record({'external_id':'a','observed_at':'2026-11-27T00:00:00Z','payload':{}})
    item=parse_record({'external_id':'a','observed_at':'2026-11-27T00:00:00Z','payload':{'provenance_url':'https://example.org/data'},'kind':'forecast','published_at':'2025-12-31T00:00:00Z'})
    assert item[-1]=='forecast'
