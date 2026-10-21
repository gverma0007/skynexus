import asyncio

import httpx

from app.core.config import get_settings
from app.services import ai_explainer

METRICS = {
    "region": {"id": "x", "name": "Red Sea"},
    "window_hours": 24,
    "aviation_metrics": {"before": 30.0, "after": 40.0, "delta_pct": 33.3},
    "events_metrics": {"before": 0, "after": 2, "delta_pct": 100.0, "largest": "M5.8, near Jizan"},
    "weather_metrics": {"before": 10.0, "after": 12.0, "delta_pct": 20.0},
    "satellite_metrics": {"before": 30, "after": 31, "delta_pct": 3.3},
}


def test_template_without_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "ANTHROPIC_API_KEY", "")
    text, source = asyncio.run(ai_explainer.get_ai_explanation(METRICS))
    assert source == "template"
    assert "rose 33%" in text and "M5.8" in text
    assert text.endswith("Correlation does not establish causation.")


def test_weather_explains_drop():
    m = dict(METRICS, aviation_metrics={"before": 40.0, "after": 20.0, "delta_pct": -50.0},
             weather_metrics={"before": 10.0, "after": 70.0, "delta_pct": 600.0})
    assert "weather may explain" in ai_explainer.template_explanation(m).lower()


def test_falls_back_when_api_fails(monkeypatch):
    monkeypatch.setattr(get_settings(), "ANTHROPIC_API_KEY", "test-key")

    class Boom(httpx.AsyncClient):
        async def post(self, *a, **k):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(ai_explainer.httpx, "AsyncClient", Boom)
    text, source = asyncio.run(ai_explainer.get_ai_explanation(METRICS))
    assert source == "template"
    assert text.endswith("Correlation does not establish causation.")
