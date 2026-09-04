#!/usr/bin/env bash
# =============================================================================
# NE-EMIS — dev container post-create hook
# Runs once after the container is created (see devcontainer.json).
# =============================================================================
set -euo pipefail

echo "▶ NE-EMIS post-create: installing backend dependencies..."
pip install --upgrade pip
pip install -r /workspace/requirements.txt

echo "▶ NE-EMIS post-create: installing frontend dependencies..."
cd /workspace/web
npm install --no-audit --no-fund

echo "▶ NE-EMIS post-create: verifying toolchain..."
python --version
node --version
npm --version

echo "▶ NE-EMIS post-create: running database migrations (alembic upgrade head)..."
cd /workspace
alembic upgrade head

echo "✅ NE-EMIS dev container ready."
echo "   • Backend : uvicorn app.main:app --reload --port 8000  (or: docker compose up app)"
echo "   • Frontend: cd web && npm run dev                       (or: docker compose up web)"
