#!/bin/sh
# Prepare the database, then start the API.
set -e

echo "[skynexus] waiting for the database..."
python - <<'PY'
import os, sys, time
import psycopg2
url = os.environ.get("DATABASE_URL", "postgresql://user:password@db:5432/skynexus")
for attempt in range(60):
    try:
        psycopg2.connect(url).close()
        sys.exit(0)
    except Exception as exc:
        print(f"  not ready ({exc.__class__.__name__}), retrying...", flush=True)
        time.sleep(2)
sys.exit("database never became available")
PY

echo "[skynexus] applying migrations..."
alembic upgrade head

echo "[skynexus] seeding regions and airports..."
python -m app.data.seed_regions
python -m app.data.seed_airports

MODE="${DATA_MODE:-live}"
if [ "$MODE" = "demo" ]; then
  HAS_DEMO=$(python -c "from sqlalchemy import text; from app.core.db import engine; c=engine.connect(); print(c.execute(text(\"SELECT COUNT(*) FROM flight_observations WHERE source='demo_dataset'\")).scalar()); c.close()")
  if [ "$HAS_DEMO" = "0" ] || [ "${DEMO_RESET:-0}" = "1" ]; then
    echo "[skynexus] generating the demo world (about 30 s)..."
    python -m app.data.demo_dataset --reset
  else
    echo "[skynexus] demo data already present (set DEMO_RESET=1 to regenerate)"
  fi
else
  echo "[skynexus] live mode: removing any demo rows"
  python -m app.data.seed_airports --purge-synthetic
fi

echo "[skynexus] starting API on :8000 (data mode: $MODE)"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
