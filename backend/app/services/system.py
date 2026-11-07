"""System monitoring and data source health service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import ingest

SOURCES = {
    "opensky": ("Air traffic", "OpenSky Network worldwide live ADS-B vectors", "https://opensky-network.org"),
    "adsb.lol": ("Air traffic", "ADS-B aircraft positions", "https://adsb.lol"),
    "celestrak": ("Satellites", "Orbital elements (TLE), positioned with SGP4", "https://celestrak.org"),
    "open-meteo": ("Weather", "Wind, gusts and rain at each region centre", "https://open-meteo.com"),
    "usgs": ("Conflict & Seismic Feeds", "USGS M2.5+ and security threat events", "https://earthquake.usgs.gov"),
    "demo_dataset": ("Demo data", "Generated 8-day synthetic world", None),
}

DOMAIN_LABELS = {
    "flights": "Air traffic",
    "satellites": "Satellite positions",
    "weather": "Weather",
    "events": "Conflict & Incidents",
}


def get_system_health(db: Session) -> dict:
    """Collect data-source health, counts, and runtime settings."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    rows = db.execute(text(
        """
        SELECT 'flights', source, COUNT(*) FILTER (WHERE ingested_at >= now() - interval '24 hours'),
               COUNT(*), MAX(ingested_at) FROM flight_observations GROUP BY source
        UNION ALL
        SELECT 'satellites', source, COUNT(*) FILTER (WHERE ingested_at >= now() - interval '24 hours'),
               COUNT(*), MAX(ingested_at) FROM satellite_observations GROUP BY source
        UNION ALL
        SELECT 'weather', source, COUNT(*) FILTER (WHERE ingested_at >= now() - interval '24 hours'),
               COUNT(*), MAX(ingested_at) FROM weather_observations GROUP BY source
        UNION ALL
        SELECT 'events', source, COUNT(*) FILTER (WHERE ingested_at >= now() - interval '24 hours'),
               COUNT(*), MAX(ingested_at) FROM events GROUP BY source
        """
    )).all()
    stale = timedelta(seconds=max(settings.LIVE_INGEST_INTERVAL_S * 3, 1800))
    sources = []
    for domain, source, n24, total, latest in rows:
        _, desc, url = SOURCES.get(source, (domain.title(), source, None))
        name = DOMAIN_LABELS.get(domain, domain.title())
        if source == "demo_dataset":
            status = "demo"
        elif source == "usgs":
            status = "ok"  # quakes are bursty; absence of new rows is normal
        else:
            status = "ok" if latest and now - latest <= stale else "stale"
        sources.append({
            "domain": domain,
            "source": source,
            "name": name,
            "description": desc,
            "url": url,
            "rows_24h": n24,
            "rows_total": total,
            "last_seen": latest.isoformat() if latest else None,
            "status": status,
        })

    counts = dict(db.execute(text(
        """
        SELECT 'regions', COUNT(*) FROM regions UNION ALL
        SELECT 'airports', COUNT(*) FROM airports UNION ALL
        SELECT 'satellites', COUNT(*) FROM satellites UNION ALL
        SELECT 'anomalies', COUNT(*) FROM anomaly_scores UNION ALL
        SELECT 'reports', COUNT(*) FROM what_changed_reports
        """
    )).all())
    return {
        "data_mode": settings.DATA_MODE,
        "live_ingest": bool(settings.LIVE_INGEST),
        "ingest_interval_s": settings.LIVE_INGEST_INTERVAL_S,
        "retention_days": settings.RETENTION_DAYS,
        "ai_mode": "claude" if settings.ANTHROPIC_API_KEY else "template",
        "ai_model": settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else None,
        "ingest": ingest.state,
        "sources": sources,
        "counts": counts,
        "server_time": now.isoformat(),
    }


def switch_data_mode(db: Session, mode: str) -> dict:
    """Switch active runtime data mode between 'live' and 'demo'."""
    settings = get_settings()
    if mode not in ("live", "demo"):
        return {"status": "error", "message": f"Invalid mode: {mode}"}

    settings.DATA_MODE = mode

    if mode == "demo":
        has_demo = db.execute(text(
            "SELECT COUNT(*) FROM flight_observations WHERE source = 'demo_dataset'"
        )).scalar()
        if not has_demo:
            import random
            from app.data import demo_dataset
            demo_dataset.generate(random.Random(42))

    from app.services import geo, satellites, series
    series.invalidate()
    satellites.invalidate()
    geo.invalidate()

    def _run_bg():
        from app.core.db import SessionLocal
        from app.ml.anomaly import run_anomaly_detection
        bg_db = SessionLocal()
        try:
            run_anomaly_detection(bg_db)
        except Exception:
            pass
        finally:
            bg_db.close()

    import threading
    threading.Thread(target=_run_bg, daemon=True).start()

    return {
        "status": "ok",
        "data_mode": settings.DATA_MODE,
        "message": f"Switched to {mode} mode",
    }


