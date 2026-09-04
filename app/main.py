"""NE-EMIS — FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Production (behind a reverse proxy — enables X-Forwarded-* handling):
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'

Interactive docs:  http://localhost:8000/docs
ReDoc:             http://localhost:8000/redoc

Security hardening
------------------
* CORS origins are driven by settings and **strictly validated** in production
  (explicit https origins only, never ``*``).
* Every response carries ``X-Frame-Options``, ``X-Content-Type-Options``,
  ``Strict-Transport-Security`` and ``Content-Security-Policy`` headers.
* Auth login endpoints are rate limited (see ``app.core.ratelimit``).
* In production the schema is managed by **Alembic** migrations —
  ``Base.metadata.create_all`` is skipped so migrations cannot be bypassed.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select

from app.api import auth, finance, students
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.ratelimit import limiter
from app.core.security import hash_password
from app.models.user import User, UserRole

logger = logging.getLogger("ne_emis")
logging.basicConfig(level=logging.INFO)


def seed_admin() -> None:
    """Create the seed administrator on first boot if no users exist."""
    with SessionLocal() as db:
        existing = db.scalar(select(User).limit(1))
        if existing is not None:
            return
        admin = User(
            email=settings.seed_admin_email.lower().strip(),
            full_name=settings.seed_admin_full_name,
            hashed_password=hash_password(settings.seed_admin_password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        logger.info(
            "Seeded admin account %s (change the password after first login!)",
            settings.seed_admin_email,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s (env=%s, production=%s)",
        settings.app_name,
        settings.env,
        settings.is_production,
    )
    if settings.is_production:
        # Schema is owned by Alembic in production; run `alembic upgrade head`.
        logger.info(
            "Production mode: skipping auto-create_all — ensure "
            "`alembic upgrade head` has been run."
        )
    else:
        init_db()
    seed_admin()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title="NE-EMIS API",
    description=(
        "NE-EMIS — Education Management Information System. "
        "JWT-secured REST API for student records and school finance."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

# ---------------------------------------------------------------------------
# Rate limiting (slowapi) — wired before routes are served
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# Security headers — applied to every response
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = (
        f"max-age={settings.hsts_max_age}; includeSubDomains"
    )
    response.headers["Content-Security-Policy"] = (
        settings.content_security_policy or "default-src 'self'"
    )
    return response


# ---------------------------------------------------------------------------
# CORS — origins come from validated settings (TLS-only in production)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(students.router, prefix=settings.api_v1_prefix)
app.include_router(finance.router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
def root() -> JSONResponse:
    return JSONResponse(
        {
            "app": settings.app_name,
            "version": "1.0.0",
            "status": "ok",
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }
    )


@app.get("/health", include_in_schema=False)
def health() -> dict:
    return {"status": "healthy", "env": settings.env}
