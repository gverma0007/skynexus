from datetime import datetime, timezone

import pytest

from app.services.orbits import gmst_deg, make_tle, orbit_params, positions_now, propagate

ISS_L1 = "1 25544U 98067A   26273.50000000  .00012784  00000+0  22631-3 0  9991"
ISS_L2 = "2 25544  51.6412 211.8842 0003712  86.1410 274.0021 15.50214433476128"


def test_gmst_at_j2000_epoch():
    # By definition GMST at 2000-01-01 12:00 UT1 is 280.46061837 degrees.
    assert gmst_deg(datetime(2000, 1, 1, 12, tzinfo=timezone.utc)) == pytest.approx(280.4606, abs=1e-3)


def test_iss_subpoint_matches_reference():
    # Reference sub-point computed independently with Skyfield (geodetic):
    # lat -12.00, lon 90.93 at 2026-10-01 06:30 UTC.
    lat, lon, alt, speed = propagate(ISS_L1, ISS_L2, datetime(2026, 10, 1, 6, 30, tzinfo=timezone.utc))
    assert lat == pytest.approx(-12.0, abs=0.2)  # geocentric vs geodetic differ slightly
    assert lon == pytest.approx(90.93, abs=0.1)
    assert 380 < alt < 450
    assert 7.5 < speed < 7.8


def test_generated_tle_round_trips():
    l1, l2 = make_tle(90001, 53.0, 120.0, 0.0001, 90.0, 10.0, 15.06)
    assert len(l1) == 69 and len(l2) == 69
    params = orbit_params(l1, l2)
    assert params["inclination_deg"] == pytest.approx(53.0)
    assert params["period_minutes"] == pytest.approx(1440 / 15.06, abs=0.1)
    lat, _, alt, _ = propagate(l1, l2, datetime.now(timezone.utc))
    assert abs(lat) <= 53.5 and 450 < alt < 650


def test_batch_matches_single():
    when = datetime(2026, 10, 1, 6, 30, tzinfo=timezone.utc)
    batch = positions_now([("iss", ISS_L1, ISS_L2)], when)["iss"]
    single = propagate(ISS_L1, ISS_L2, when)
    assert batch[0] == pytest.approx(single[0], abs=1e-6)
    assert batch[1] == pytest.approx(single[1], abs=1e-6)
