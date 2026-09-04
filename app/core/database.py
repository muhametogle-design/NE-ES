"""SQLAlchemy engine, session factory and declarative base.

Works with SQLite (default, zero-config) and PostgreSQL
(``postgresql+psycopg://...``) without code changes.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


# SQLite needs ``check_same_thread`` for FastAPI's threadpool; Postgres does not.
_connect_args = (
    {"check_same_thread": False} if settings.is_sqlite else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Imported models register themselves on ``Base``."""
    # Import side-effect: ensures models are registered before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
