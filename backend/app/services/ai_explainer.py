import httpx

from app.core.config import get_settings

settings = get_settings()

SYSTEM_PROMPT = """
You are an expert analyst for SkyNexus. You are provided with statistical metrics
regarding regional activity (aviation, satellite, weather, events).
Analyze these metrics to provide a concise, plain-language explanation of
observed anomalies.
Hard Rule: Correlation does not establish causation.
"""

DISCLAIMER = "Correlation does not establish causation."


def _local_explanation(metrics: dict) -> str:
    """Deterministic offline analysis used when no ANTHROPIC_API_KEY is set."""
    aviation = metrics.get("aviation_metrics", {})
    weather = metrics.get("weather_metrics", {})
    events = metrics.get("events_metrics", {})
    satellite = metrics.get("satellite_metrics", {})
    region = metrics.get("region", {}).get("name", "the region")

    drivers = []
    if abs(aviation.get("delta_pct", 0)) >= 10:
        direction = "increase" if aviation["delta_pct"] > 0 else "decrease"
        drivers.append(f"a {aviation['delta_pct']:+.1f}% {direction} in flight activity")
    if abs(weather.get("delta_pct", 0)) >= 10 and weather.get("after", 0) > 20:
        drivers.append("elevated storm activity")
    if events.get("after", 0) > events.get("before", 0):
        drivers.append("more reported security events")
    if events.get("after", 0) == 0 and events.get("before", 0) == 0:
        drivers.append("no significant event reporting")

    if not drivers:
        return (
            f"Conditions over {region} remained broadly stable across the compared "
            f"windows, with no metric shifting beyond 10%. {DISCLAIMER}"
        )
    return (
        f"The observed changes over {region} align with {' and '.join(drivers)}. "
        f"Flight counts moved from {aviation.get('before', 0)} to "
        f"{aviation.get('after', 0)} per day, and satellite passes registered "
        f"{satellite.get('before', 0)} -> {satellite.get('after', 0)} observations. "
        f"{DISCLAIMER}"
    )


async def get_ai_explanation(metrics: dict) -> str:
    if not settings.ANTHROPIC_API_KEY:
        return _local_explanation(metrics)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-sonnet-20240620",
                    "max_tokens": 1024,
                    "system": SYSTEM_PROMPT,
                    "messages": [
                        {"role": "user", "content": f"Analyze these metrics: {metrics}"}
                    ],
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
    except Exception:
        return _local_explanation(metrics)
