"""NE-EMIS — FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Interactive docs:  http://localhost:8000/docs
ReDoc:             http://localhost:8000/redoc
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import auth, finance, students
from app.core.config import settings
from app.core.database import SessionLocal, init_db
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
    logger.info("Starting %s (env=%s)", settings.app_name, settings.env)
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
# CORS — Vite dev server (and any configured origins)
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
