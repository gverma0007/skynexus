import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ai_explainer import get_ai_explanation


@pytest.mark.asyncio
async def test_get_ai_explanation_success():
    metrics = {"aviation": "delta"}
    with patch("app.services.ai_explainer.settings") as mock_settings, patch(
        "httpx.AsyncClient.post"
    ) as mock_post:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_post.return_value.status_code = 200
        # response.json() is synchronous in httpx, so it must be a MagicMock,
        # not an AsyncMock child of the patched async post().
        mock_post.return_value.json = MagicMock(
            return_value={
                "content": [
                    {
                        "text": "Analysis: Everything looks normal. "
                        "Correlation does not establish causation."
                    }
                ]
            }
        )

        explanation = await get_ai_explanation(metrics)
        assert "Analysis" in explanation
        assert "Correlation does not establish causation" in explanation


@pytest.mark.asyncio
async def test_get_ai_explanation_failure():
    metrics = {"aviation": "delta"}
    with patch("app.services.ai_explainer.settings") as mock_settings, patch(
        "httpx.AsyncClient.post"
    ) as mock_post:
        mock_settings.ANTHROPIC_API_KEY = "test-key"
        mock_post.side_effect = Exception("API Error")

        explanation = await get_ai_explanation(metrics)
        # On API failure the deterministic local analysis is used as fallback.
        assert "Correlation does not establish causation" in explanation
        assert len(explanation) > 20


@pytest.mark.asyncio
async def test_get_ai_explanation_offline_fallback():
    """Without an API key, a deterministic local analysis is returned."""
    metrics = {
        "region": {"name": "Middle East"},
        "aviation_metrics": {"before": 10.0, "after": 5.0, "delta_pct": -50.0},
        "weather_metrics": {"before": 5.0, "after": 6.0, "delta_pct": 20.0},
        "events_metrics": {"before": 0, "after": 2, "delta_pct": 100.0},
        "satellite_metrics": {"before": 4, "after": 4, "delta_pct": 0.0},
    }
    with patch("app.services.ai_explainer.settings") as mock_settings:
        mock_settings.ANTHROPIC_API_KEY = ""
        explanation = await get_ai_explanation(metrics)
        assert "Middle East" in explanation
        assert "Correlation does not establish causation" in explanation
