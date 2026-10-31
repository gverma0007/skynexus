"""Integration tests against a running database (skipped when unavailable).

Run inside the stack: docker compose exec backend python -m pytest -q
"""
import pytest
from sqlalchemy import text

try:
    from app.core.db import engine

    with engine.connect() as c:
        HAS_DATA = (c.execute(text("SELECT COUNT(*) FROM regions")).scalar() or 0) > 0
except Exception:  # pragma: no cover
    HAS_DATA = False

pytestmark = pytest.mark.skipif(not HAS_DATA, reason="needs a seeded database")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_regions_have_scores(client):
    regions = client.get("/api/regions").json()
    assert len(regions) == 15
    for r in regions:
        assert 0 <= r["composite_index"] <= 100
        assert r["status"] in ("Calm", "Watch", "Elevated", "Critical")


def test_pacific_does_not_cover_gulf_of_guinea(client):
    outline = {o["name"]: o["ring"] for o in client.get("/api/regions/outline").json()}
    lons = [p[1] for p in outline["Pacific"]]
    assert max(lons) - min(lons) <= 40


def test_region_endpoints(client):
    rid = client.get("/api/regions").json()[0]["region_id"]
    for path in ("", "/history", "/overhead", "/forecast"):
        assert client.get(f"/api/regions/{rid}{path}").status_code == 200


def test_report_round_trip(client):
    rid = client.get("/api/regions").json()[0]["region_id"]
    created = client.post("/api/reports", json={"region_id": rid, "hours": 6})
    assert created.status_code == 201
    body = created.json()
    assert body["overall_assessment"].endswith("Correlation does not establish causation.")
    assert client.get(f"/api/reports/{body['id']}").status_code == 200
    assert client.delete(f"/api/reports/{body['id']}").status_code == 204


def test_misc_endpoints(client):
    for path in ("/api/stats", "/api/flights/live", "/api/satellites/live", "/api/events",
                 "/api/anomalies", "/api/alerts", "/api/system/health", "/api/system/mode", "/api/search?q=a"):
        assert client.get(path).status_code == 200, path


def test_system_mode_toggle(client):
    res = client.get("/api/system/mode")
    assert res.status_code == 200
    orig_mode = res.json()["data_mode"]

    # Toggle to live
    set_live = client.post("/api/system/mode", json={"mode": "live"})
    assert set_live.status_code == 200
    assert set_live.json()["data_mode"] == "live"

    # Restore original mode
    client.post("/api/system/mode", json={"mode": orig_mode})

