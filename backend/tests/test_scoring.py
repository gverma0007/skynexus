from datetime import datetime, timedelta, timezone

from app.ml.anomaly import score_region as anomaly_rows
from app.services.disruption import event_component, flight_component, satellite_component, weather_component
from app.services.series import RegionSeries

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
HOURS = [NOW - timedelta(hours=h) for h in range(191, -1, -1)]


def series(aircraft=None, storm=None, events=None, satellites=None, flight_deviations=None):
    n = len(HOURS)
    a = list(aircraft if aircraft is not None else [50.0] * n)
    s = list(storm if storm is not None else [10.0] * n)
    e = list(events if events is not None else [0] * n)
    sat = list(satellites if satellites is not None else [10.0] * n)
    dev = list(flight_deviations if flight_deviations is not None else [0.0] * n)
    return RegionSeries("r1", "Test", 0.0, 0.0, HOURS, a, s, e, [0.0] * n,
                        satellites=sat, flight_deviations=dev)


def flat(v=50.0):
    return [v] * len(HOURS)


def test_normal_traffic_scores_zero():
    rs = series(flat())
    f = flight_component(rs, len(HOURS) - 1)
    assert f["score"] == 0 and f["warming_up"] is False


def test_traffic_volume_change_does_not_score_anomaly_without_route_deviation():
    up = flat(); up[-4:-1] = [90.0] * 3
    down = flat(); down[-4:-1] = [10.0] * 3
    fu = flight_component(series(up), len(HOURS) - 1)
    fd = flight_component(series(down), len(HOURS) - 1)
    # Direction and pct_change are tracked for statistics
    assert fu["direction"] == "up"
    assert fd["direction"] == "down"
    assert fd["pct_change"] < -50
    # But anomaly score is 0 without route deviation
    assert fu["score"] == 0
    assert fd["score"] == 0


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
           "description": "Security alert — x", "event_type": "Conflict Incident"}
    old = dict(big, event_date=NOW - timedelta(hours=23))
    assert event_component([big], NOW)["score"] > event_component([old], NOW)["score"]
    assert event_component([], NOW)["score"] == 0


def test_weather_uses_latest_reading():
    storm = [10.0] * len(HOURS)
    storm[-1] = 65.0
    w = weather_component(series(flat(), storm=storm), len(HOURS) - 1)
    assert w["score"] == 65.0


def test_anomaly_engine_flags_satellite_and_route_deviation_spikes():
    # 1. Aeroplane density changes alone do NOT trigger anomaly
    a = [50.0 + (i % 5) for i in range(len(HOURS))]
    a[-3] = 140.0
    rows_air = anomaly_rows(series(a))
    assert not any(r["observed_value"] == 140.0 for r in rows_air)

    # 2. Seismic earthquake logic is completely excluded from anomaly feature naming
    ev = [0] * len(HOURS)
    ev[-3] = 25  # 25 incidents in an hour
    rows_ev = anomaly_rows(series(events=ev))
    assert not any("event" in r["feature_name"] or "earthquake" in r["feature_name"] for r in rows_ev)

    # 3. Satellite density spike triggers satellite_density anomaly
    sats = [10.0] * len(HOURS)
    sats[-3] = 45.0
    rows_sat = anomaly_rows(series(satellites=sats))
    spike_sat = [r for r in rows_sat if r["observed_value"] == 45.0]
    assert spike_sat and spike_sat[0]["composite_score"] >= 50
    assert spike_sat[0]["feature_name"] in ("satellite_density", "orbital_reconnaissance_surge")

    # 4. Flight route deviation spike triggers flight_route_deviation anomaly
    devs = [15.0] * len(HOURS)
    devs[-3] = 320.0
    rows_dev = anomaly_rows(series(flight_deviations=devs))
    spike_dev = [r for r in rows_dev if r["observed_value"] == 320.0]
    assert spike_dev and spike_dev[0]["composite_score"] >= 50
    assert spike_dev[0]["feature_name"] in ("flight_route_deviation", "airspace_conflict_evasion")


def test_anomaly_engine_marks_storm_deviation_weather_explained():
    devs = [15.0] * len(HOURS)
    storm = [10.0] * len(HOURS)
    devs[-3], storm[-3] = 120.0, 80.0
    rows = anomaly_rows(series(flight_deviations=devs, storm=storm))
    hit = [r for r in rows if r["observed_value"] in (120.0, 80.0)]
    assert hit
    assert any("weather" in r["feature_name"] or r["severity_label"] in ("low", "normal") for r in hit)


def test_anomaly_engine_detects_war_conflict_early_warning():
    # Coincident satellite surveillance surge + flight route avoidance in clear weather
    sats = [10.0] * len(HOURS); sats[-3] = 40.0
    devs = [15.0] * len(HOURS); devs[-3] = 310.0
    storm = [5.0] * len(HOURS)
    rows = anomaly_rows(series(satellites=sats, flight_deviations=devs, storm=storm))
    war_hit = [r for r in rows if "war_conflict" in r["feature_name"]]
    assert war_hit, f"Expected war_conflict_early_warning, got: {[r['feature_name'] for r in rows]}"
    assert war_hit[0]["severity_label"] in ("high", "medium")
    # Verified war & conflict risk is directly included in composite score
    assert war_hit[0]["composite_score"] >= 60.0


def test_weekly_flight_deviation_metrics():
    a = flat(100.0)
    a[-4:-1] = [50.0] * 3  # 50% drop
    f = flight_component(series(a), len(HOURS) - 1)
    assert f["week_mean"] == 100.0
    assert f["week_pct_change"] < -40.0
    # Flight anomaly score remains 0 without route deviations
    assert f["score"] == 0.0


def test_satellite_component_density_and_orbits():
    empty = satellite_component(None)
    assert empty["score"] == 0.0 and empty["count"] == 0

    # Normal constellation with healthy GNSS navigation
    normal_sat = {
        "count": 6, "density": 8.5,
        "by_orbit": {"leo": 4, "meo": 2, "geo": 0},
        "by_category": {"Earth observation": 1, "Navigation": 2, "Communications": 3},
        "leo_earthobs": 1, "gnss_nav": 2,
    }
    s_norm = satellite_component(normal_sat)
    assert s_norm["score"] <= 30.0
    assert s_norm["gnss_nav"] == 2

    # High surveillance LEO activity
    surge_sat = {
        "count": 12, "density": 25.0,
        "by_orbit": {"leo": 10, "meo": 2, "geo": 0},
        "by_category": {"Earth observation": 4, "Navigation": 2},
        "leo_earthobs": 4, "gnss_nav": 2,
    }
    s_surge = satellite_component(surge_sat)
    assert s_surge["score"] > 50.0
    assert s_surge["leo_earthobs"] == 4


def test_flight_route_deviation_increases_disruption_index():
    rs = series(flat())
    # Normal traffic with no deviation scores 0
    f_nom = flight_component(rs, len(HOURS) - 1, dev_info=None)
    assert f_nom["score"] == 0.0

    # Traffic with high route deviations (e.g. 2 aircraft deviating 250 km)
    dev_info = {
        "count": 5, "deviating_count": 2, "significant_count": 2, "minor_count": 0,
        "max_km": 250.0, "avg_km": 240.0, "dev_score": 100.0,
    }
    f_dev = flight_component(rs, len(HOURS) - 1, dev_info=dev_info)
    assert f_dev["score"] >= 75.0
    assert f_dev["route_deviations"]["significant_count"] == 2
