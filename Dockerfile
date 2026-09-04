# =============================================================================
# NE-EMIS — Full-stack development image
# Python 3.11 backend (FastAPI) + Node.js 20 frontend (Vite/React)
# =============================================================================
FROM python:3.11-slim-bookworm

# ---------------------------------------------------------------------------
# System packages
# ---------------------------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        build-essential \
        libpq-dev \
        ca-certificates \
        gnupg \
        bash \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Node.js 20 (LTS) — installed from NodeSource so we control the major version
# ---------------------------------------------------------------------------
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version && npm --version

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
WORKDIR /workspace
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Frontend dependencies (cached layer; node_modules lives on the bind mount in
# dev, but installing here makes the image self-sufficient for CI/preview).
# ---------------------------------------------------------------------------
COPY web/package.json web/package-lock.json* /tmp/web/
RUN cd /tmp/web && npm install --no-audit --no-fund || true

# Expose FastAPI (8000) and Vite dev server (5173)
EXPOSE 8000 5173

# Default command is overridden by docker-compose; this keeps the image usable
# standalone (`docker run` will launch the API).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
