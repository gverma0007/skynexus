from datetime import datetime, timedelta, timezone

from app.ml.anomaly import score_region as anomaly_rows
from app.services.disruption import event_component, flight_component, weather_component
from app.services.series import RegionSeries

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
HOURS = [NOW - timedelta(hours=h) for h in range(191, -1, -1)]


def series(aircraft, storm=None, events=None):
    n = len(HOURS)
    return RegionSeries("r1", "Test", 0.0, 0.0, HOURS, list(aircraft),
                        list(storm or [10.0] * n), list(events or [0] * n), [0.0] * n)


def flat(v=50.0):
    return [v] * len(HOURS)


def test_normal_traffic_scores_zero():
    rs = series(flat())
    f = flight_component(rs, len(HOURS) - 1)
    assert f["score"] == 0 and f["warming_up"] is False


def test_surge_and_drop_both_score():
    up = flat(); up[-4:-1] = [90.0] * 3
    down = flat(); down[-4:-1] = [10.0] * 3
    fu = flight_component(series(up), len(HOURS) - 1)
    fd = flight_component(series(down), len(HOURS) - 1)
    assert fu["score"] > 50 and fu["direction"] == "up"
    assert fd["score"] > 50 and fd["direction"] == "down"
    assert fd["pct_change"] < -50


def test_missing_baseline_is_warming_up_not_anomalous():
    a = [None] * len(HOURS)
    a[-4:-1] = [40.0] * 3
    f = flight_component(series(a), len(HOURS) - 1)
    assert f["warming_up"] is True and f["score"] == 0


def test_ingest_gaps_are_ignored():
    a = flat()
    for i in range(0, 60):
        a[i] = None  # backend down for 2.5 days: not a traffic collapse
    f = flight_component(series(a), len(HOURS) - 1)
    assert f["score"] == 0


def test_event_points_decay_and_background():
    big = {"id": "e", "magnitude": 5.8, "event_date": NOW - timedelta(hours=2),
           "description": "M5.8 earthquake — x", "event_type": "Earthquake"}
    old = dict(big, event_date=NOW - timedelta(hours=23))
    assert event_component([big], NOW)["score"] > event_component([old], NOW)["score"]
    assert event_component([], NOW)["score"] == 0


def test_weather_uses_latest_reading():
    storm = [10.0] * len(HOURS)
    storm[-1] = 65.0
    w = weather_component(series(flat(), storm=storm), len(HOURS) - 1)
    assert w["score"] == 65.0


def test_anomaly_engine_flags_injected_spike():
    a = [50.0 + (i % 5) for i in range(len(HOURS))]
    a[-3] = 140.0
    rows = anomaly_rows(series(a))
    spike = [r for r in rows if r["observed_value"] == 140.0]
    assert spike and spike[0]["composite_score"] >= 60
    assert spike[0]["feature_name"] == "aircraft_per_hour"


def test_anomaly_engine_marks_storm_drop_weather_explained():
    a = flat()
    storm = [10.0] * len(HOURS)
    a[-3], storm[-3] = 5.0, 80.0
    rows = anomaly_rows(series(a, storm=storm))
    hit = [r for r in rows if r["observed_value"] in (5.0, 80.0)]
    assert hit
    assert all(r["severity_label"] in ("low", "normal") or "weather" in r["feature_name"]
               or r["feature_name"] == "storm_index" for r in hit)
