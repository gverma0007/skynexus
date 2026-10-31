from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock

import pytest

from app.core.cache import TTLCache
from app.core.config import normalize_db_url
from app.services.geo import point_to_wkt
from app.services.series import RegionSeries, SeriesBundle, compute_region_forecast, compute_region_history


def test_ttl_cache_basic_and_invalidation():
    cache: TTLCache[str] = TTLCache(ttl_seconds=1.0)
    assert cache.get() is None

    cache.set("value1")
    assert cache.get() == "value1"

    # Invalidate clears cache
    cache.invalidate()
    assert cache.get() is None

    # get_or_set
    calls = 0

    def builder():
        nonlocal calls
        calls += 1
        return "computed"

    val1 = cache.get_or_set(builder)
    assert val1 == "computed"
    assert calls == 1

    val2 = cache.get_or_set(builder)
    assert val2 == "computed"
    assert calls == 1  # Should not call again within TTL


def test_normalize_db_url():
    assert normalize_db_url("postgresql://user:pass@host:5432/db") == "postgresql+psycopg2://user:pass@host:5432/db"
    assert normalize_db_url("sqlite:///test.db") == "sqlite:///test.db"
    assert normalize_db_url("postgresql+psycopg2://already_ok") == "postgresql+psycopg2://already_ok"


def test_point_to_wkt():
    assert point_to_wkt(34.1234, -118.5432) == "POINT(34.1234 -118.5432)"


def test_compute_region_history_and_forecast():
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    hours = [now - timedelta(hours=h) for h in range(191, -1, -1)]
    aircraft = [50.0 + (i % 5) for i in range(len(hours))]
    storm = [10.0] * len(hours)
    events = [0] * len(hours)
    max_mag = [0.0] * len(hours)

    rs = RegionSeries("r1", "Test Region", 0.0, 0.0, hours, aircraft, storm, events, max_mag)
    bundle = SeriesBundle(built_at=time.monotonic(), now=now, hours=hours, regions={"r1": rs}, events=[])

    # Test history computation
    history = compute_region_history(bundle, "r1", hours=48)
    assert history is not None
    assert history["region_id"] == "r1"
    assert len(history["points"]) == 49
    assert history["baseline_hours"] > 0

    # Non-existent region returns None
    assert compute_region_history(bundle, "unknown") is None

    # Test forecast computation
    forecast = compute_region_forecast(bundle, "r1", horizon_hours=6)
    assert forecast is not None
    assert forecast["region_id"] == "r1"
    assert len(forecast["points"]) == 7
    assert len(forecast["history"]) == 12
    assert "trend_per_hour" in forecast

    # Non-existent region forecast returns None
    assert compute_region_forecast(bundle, "unknown") is None
