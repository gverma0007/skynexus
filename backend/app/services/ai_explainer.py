"""Plain-language assessment for What-Changed reports.

Claude receives only the computed metrics (never raw rows). Without an API
key, or if the call fails, a deterministic template writes the text. Every
output ends with the causation disclaimer.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger("ai_explainer")

DISCLAIMER = "Correlation does not establish causation."

SYSTEM_PROMPT = """You write short situation assessments for SkyNexus, a dashboard that
compares a region's recent activity with the period just before it.

You receive computed metrics only: aircraft per hour, conflict & security threat counts and
magnitudes, storm intensity, satellite passes and a 0-100 disruption index.

Rules:
- 3 to 4 sentences of plain English for a non-specialist. No headings, no lists.
- Lead with the biggest change. Use the numbers you are given; never invent any.
- If storm intensity is high and air traffic fell, say weather may explain it.
- Never claim or imply a cause, motive, military or hostile activity.
- Do not add a disclaimer; the application adds one."""


def _fmt_pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:+.0f}%"


def template_explanation(m: dict) -> str:
    region = m["region"]["name"]
    hours = m["window_hours"]
    av, ev, wx = m["aviation_metrics"], m["events_metrics"], m["weather_metrics"]
    parts: list[str] = []

    if av["before"] is None or av["after"] is None:
        parts.append(f"There is not enough air-traffic data yet to compare the last {hours} hours over {region}.")
    elif av["delta_pct"] is not None and abs(av["delta_pct"]) >= 10:
        word = "rose" if av["delta_pct"] > 0 else "fell"
        parts.append(
            f"Air traffic over {region} {word} {abs(av['delta_pct']):.0f}% in the last {hours} hours, "
            f"from {av['before']:.1f} to {av['after']:.1f} aircraft per hour."
        )
    else:
        parts.append(
            f"Air traffic over {region} held steady at about {av['after']:.1f} aircraft per hour "
            f"({_fmt_pct(av['delta_pct'])} on the previous {hours} hours)."
        )

    if av.get("week_delta_pct") is not None and abs(av["week_delta_pct"]) >= 15:
        w_word = "above" if av["week_delta_pct"] > 0 else "below"
        parts.append(f"Traffic is running {abs(av['week_delta_pct']):.0f}% {w_word} the 7-day weekly average.")

    if ev["after"] > 0:
        largest = ev.get("largest")
        tail = f", the largest {largest}" if largest else ""
        parts.append(f"{ev['after']} security incident{'s were' if ev['after'] != 1 else ' was'} recorded "
                     f"(previously {ev['before']}){tail}.")
    elif ev["before"] > 0:
        parts.append(f"No security incidents were recorded, down from {ev['before']} in the period before.")

    if wx["after"] is not None:
        if wx["after"] >= 40:
            parts.append(f"Storm intensity was high at {wx['after']:.0f}/100.")
            if av["delta_pct"] is not None and av["delta_pct"] <= -10:
                parts.append("The weather may explain the lower traffic.")
        else:
            parts.append(f"Storm intensity stayed low ({wx['after']:.0f}/100), so weather is unlikely "
                         f"to explain changes in traffic.")

    fdev = m.get("flight_deviations")
    if fdev and fdev.get("significant_deviations", 0) > 0:
        parts.append(
            f"Significant flight route deviations were observed ({fdev['significant_deviations']} flight(s) "
            f"deviating up to {fdev['max_deviation_km']:.0f} km from nominal flight corridors)."
        )
    elif fdev and fdev.get("deviating_flights", 0) > 0:
        parts.append(
            f"Minor route diversions were noted ({fdev['deviating_flights']} flight(s) off nominal corridors)."
        )

    sat = m.get("satellite_metrics")
    if sat and sat.get("after") is not None:
        if sat.get("delta_pct") is not None and abs(sat["delta_pct"]) >= 10:
            sw = "rose" if sat["delta_pct"] > 0 else "fell"
            parts.append(
                f"Satellite passes {sw} {abs(sat['delta_pct']):.0f}% "
                f"({sat['after']} passes vs {sat['before']} in the previous window)."
            )
        else:
            parts.append(
                f"Satellite coverage was steady with {sat['after']} passes "
                f"({_fmt_pct(sat.get('delta_pct'))} delta)."
            )
    return " ".join(parts)


async def get_ai_explanation(metrics: dict) -> tuple[str, str]:
    """Return (text, source) where source is 'claude' or 'template'."""
    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        return f"{template_explanation(metrics)} {DISCLAIMER}", "template"
    payload = {k: v for k, v in metrics.items() if k != "overall_assessment"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.ANTHROPIC_MODEL,
                    "max_tokens": 400,
                    "system": SYSTEM_PROMPT,
                    "messages": [{
                        "role": "user",
                        "content": "Metrics (JSON):\n" + json.dumps(payload, default=str),
                    }],
                },
            )
            res.raise_for_status()
            text = "".join(b.get("text", "") for b in res.json().get("content", [])).strip()
            if text:
                return f"{text} {DISCLAIMER}", "claude"
    except Exception as exc:
        logger.warning("Claude call failed, using template: %s", exc)
    return f"{template_explanation(metrics)} {DISCLAIMER}", "template"
