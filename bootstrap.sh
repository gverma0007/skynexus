#!/bin/bash
# Bootstrap SkyNexus demo environment.
# Runs everything inside the docker-compose services, so no host-side
# Python dependencies are required. Start the stack first:
#   docker compose up -d
set -e

echo "Starting SkyNexus bootstrap..."

# 1. Ensure DB is ready
echo "Waiting for database..."
until docker compose exec -T db pg_isready -U user -d skynexus > /dev/null 2>&1; do
  sleep 2
done
echo "Database is ready."

# 2. Run migrations
echo "Running migrations..."
docker compose exec -T backend alembic upgrade head

# 3. Seed regions
echo "Seeding regions..."
docker compose exec -T backend python -m app.data.seed_regions

# 4. Generate demo data
echo "Generating demo dataset..."
docker compose exec -T backend python -m app.data.demo_dataset --reset

echo ""
echo "Bootstrap complete."
echo "  Frontend:  http://localhost:5173"
echo "  API docs:  http://localhost:8000/docs"
