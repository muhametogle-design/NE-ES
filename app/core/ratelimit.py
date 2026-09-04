"""Shared slowapi rate limiter.

Wired into the FastAPI app in ``app.main`` (middleware + exception handler)
and applied per-route via ``@limiter.limit(...)`` — see ``app.api.auth``.

Keys are the client IP. When running behind a reverse proxy (nginx, Docker
ingress, load balancer), launch uvicorn with ``--proxy-headers`` so
``X-Forwarded-For`` is honoured instead of the proxy's address.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],          # global default off; limits are opt-in per route
    headers_enabled=True,       # emit X-RateLimit-* headers
)
