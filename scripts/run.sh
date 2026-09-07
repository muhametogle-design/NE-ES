#!/usr/bin/env bash
# =============================================================================
# NE-EMIS — start the whole system locally (Linux / macOS / WSL / Git Bash)
#
#   ./scripts/run.sh              # install deps, build frontend, seed, serve
#   ./scripts/run.sh --reset      # also wipe + reseed the SQLite demo database
#   ./scripts/run.sh --no-build   # skip the React build (backend + API only)
#   ./scripts/run.sh --no-reload  # no file watcher (cleanest for breakpoints)
#   PORT=9000 ./scripts/run.sh    # serve on a different port
#
# Serves the built React SPA and the REST API from one process:
#   App     http://localhost:8000
#   Swagger http://localhost:8000/docs
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
RESET=0; BUILD=1; RELOAD=1
for arg in "$@"; do
  case "$arg" in
    --reset)     RESET=1 ;;
    --no-build)  BUILD=0 ;;
    --no-reload) RELOAD=0 ;;
    -h|--help)   sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

PY=python3
command -v "$PY" >/dev/null || PY=python

echo "▶ 1/5  Creating virtual environment (.venv)..."
[ -d .venv ] || "$PY" -m venv .venv
VENV_PY=.venv/bin/python

echo "▶ 2/5  Installing Python dependencies..."
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet -r requirements-dev.txt

echo "▶ 3/5  Preparing .env..."
[ -f .env ] || { cp .env.example .env; echo "    created .env from .env.example"; }
mkdir -p data

if [ "$BUILD" = "1" ]; then
  echo "▶ 4/5  Building React frontend (web/)..."
  if command -v npm >/dev/null; then
    ( cd web && npm install --no-audit --no-fund && npm run build )
  else
    echo "    npm not found — skipping. The API still runs; the SPA at / will be blank."
  fi
else
  echo "▶ 4/5  Skipping frontend build (--no-build)"
fi

echo "▶ 5/5  Database..."
if [ "$RESET" = "1" ]; then
  "$VENV_PY" -m scripts.seed_data --reset
else
  "$VENV_PY" -m scripts.seed_data 2>/dev/null || echo "    (already seeded — pass --reset to reseed)"
fi

ARGS=(app.main:app --host "$HOST" --port "$PORT")
[ "$RELOAD" = "1" ] && ARGS+=(--reload --reload-dir app)

echo
echo "✅  Starting NE-EMIS on http://localhost:${PORT}  (docs: /docs, Ctrl+C to stop)"
echo
exec "$VENV_PY" -m uvicorn "${ARGS[@]}"
