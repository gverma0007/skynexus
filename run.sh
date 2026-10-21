#!/bin/sh
# SkyNexus launcher for macOS / Linux.
# Usage: ./run.sh [live|demo|stop|logs|reset|wipe]
cd "$(dirname "$0")" || exit 1

WEB_PORT=$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2)
URL="http://localhost:${WEB_PORT:-5173}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Get it from https://www.docker.com/products/docker-desktop/"; exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and try again."; exit 1
fi
[ -f .env ] || { cp .env.example .env && echo "Created .env from .env.example."; }

open_url() { (command -v open >/dev/null && open "$URL") || (command -v xdg-open >/dev/null && xdg-open "$URL") || true; }

start() {
  echo "Starting SkyNexus in $DATA_MODE mode (first run can take 5-10 minutes)..."
  DATA_MODE=$DATA_MODE DEMO_RESET=${DEMO_RESET:-0} docker compose up -d --build || exit 1
  printf "Waiting for SkyNexus to be ready"
  i=0
  until curl -sf "$URL/api/health" >/dev/null 2>&1; do
    i=$((i + 1)); [ $i -gt 120 ] && { echo; docker compose logs --tail 40 backend; exit 1; }
    printf "."; sleep 3
  done
  echo; echo "SkyNexus is running at $URL"; open_url
}

case "${1:-}" in
  live) DATA_MODE=live start ;;
  demo) DATA_MODE=demo start ;;
  reset) DATA_MODE=demo DEMO_RESET=1 start ;;
  stop) docker compose stop ;;
  logs) docker compose logs -f --tail 100 backend ;;
  wipe) printf "Type YES to delete all SkyNexus data: "; read -r a; [ "$a" = "YES" ] && docker compose down -v ;;
  *)
    echo "1) Start with live data   2) Start with demo data   3) Stop   4) Logs   5) Regenerate demo   6) Delete all data"
    printf "Choose: "; read -r c
    case "$c" in 1) DATA_MODE=live start ;; 2) DATA_MODE=demo start ;; 3) docker compose stop ;;
      4) docker compose logs -f --tail 100 backend ;; 5) DATA_MODE=demo DEMO_RESET=1 start ;;
      6) printf "Type YES: "; read -r a; [ "$a" = "YES" ] && docker compose down -v ;; esac ;;
esac
