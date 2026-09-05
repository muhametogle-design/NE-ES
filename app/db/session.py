"""SQLAlchemy 2.0 engine + session factory, tuned for PostgreSQL 16 / psycopg2.

This module is the **single source of truth** for database connectivity:

* ``engine``       – one process-wide :class:`~sqlalchemy.engine.Engine`
* ``SessionLocal``– :class:`~sqlalchemy.orm.sessionmaker` bound to that engine
* ``get_db()``     – FastAPI dependency yielding a request-scoped ``Session``
* ``session_scope()`` – context manager for scripts, schedulers and CLI jobs

Pooling
-------
PostgreSQL runs on :class:`~sqlalchemy.pool.QueuePool` with the production
defaults ``pool_size=10`` / ``max_overflow=20`` / ``pool_pre_ping=True`` and
``pool_recycle=1800`` so that connections dropped byPgBouncer, RDS failover or
an idle firewall are recycled before the application ever sees them.  Sizing is
configurable through ``DB_*`` environment variables (see ``app.core.config``).

SQLite (local development and the test-suite) keeps its own defaults — QueuePool
has no meaning for an in-process database, so ``:memory:`` databases get a
:class:`~sqlalchemy.pool.StaticPool` and file databases keep the driver default.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from importlib import import_module
from typing import Any, Optional, Union

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, StaticPool

from app.core.config import settings
from app.models.base import Base  # re-exported: legacy code imports Base from here

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "build_connect_args",
    "build_engine_kwargs",
    "create_database_engine",
    "get_db",
    "session_scope",
    "init_db",
    "migrate_sqlite_columns",
    "set_rls_context",
    "check_database_connection",
    "dispose_engine",
]

logger = logging.getLogger("ne_emis.db")

StrUrl = Union[str, URL]


# ---------------------------------------------------------------------------
# Engine construction helpers
# ---------------------------------------------------------------------------
def _ensure_sqlite_parent_dir(url: URL) -> None:
    """Create the parent directory for a file-backed SQLite database."""
    if url.get_backend_name() != "sqlite":
        return
    database = url.database
    if not database or database == ":memory:":
        return
    parent = os.path.dirname(os.path.abspath(database))
    if parent:
        os.makedirs(parent, exist_ok=True)


def build_connect_args(url: StrUrl) -> dict[str, Any]:
    """Dialect-specific ``connect_args`` for *url*.

    PostgreSQL receives libpq-level options (``connect_timeout``,
    ``application_name``, ``statement_timeout``) so a hung query or an
    unreachable host fails fast instead of stalling the whole pool.  Options
    already present in the DSN always win — libpq would otherwise see the key
    twice.
    """
    sa_url = make_url(str(url))

    if sa_url.get_backend_name() == "sqlite":
        # Required for FastAPI's threadpool and for background schedulers.
        return {"check_same_thread": False}

    if sa_url.get_backend_name() != "postgresql":
        return {}

    existing = {str(key).lower() for key in sa_url.query}
    connect_args: dict[str, Any] = {}

    if settings.DB_CONNECT_TIMEOUT and "connect_timeout" not in existing:
        connect_args["connect_timeout"] = int(settings.DB_CONNECT_TIMEOUT)
    if settings.DB_APPLICATION_NAME and "application_name" not in existing:
        connect_args["application_name"] = settings.DB_APPLICATION_NAME
    if settings.DB_STATEMENT_TIMEOUT_MS and "options" not in existing:
        connect_args["options"] = f"-c statement_timeout={int(settings.DB_STATEMENT_TIMEOUT_MS)}"

    return connect_args


def build_engine_kwargs(url: StrUrl, *, poolclass: Optional[type] = None) -> dict[str, Any]:
    """Keyword arguments for :func:`sqlalchemy.create_engine`.

    ``poolclass`` lets callers (Alembic uses :class:`NullPool`) replace the pool
    implementation; the QueuePool sizing options are dropped in that case
    because they are not accepted by every pool implementation.
    """
    sa_url = make_url(str(url))
    is_sqlite = sa_url.get_backend_name() == "sqlite"

    kwargs: dict[str, Any] = {
        "echo": settings.DB_ECHO,
        "future": True,
        "pool_pre_ping": settings.DB_POOL_PRE_PING,
        "connect_args": build_connect_args(sa_url),
    }

    if is_sqlite:
        # An in-memory database dies with its connection: pin one connection.
        if not sa_url.database or sa_url.database == ":memory:":
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["poolclass"] = QueuePool
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
        )

    if poolclass is not None:
        kwargs["poolclass"] = poolclass
        for invalid in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
            kwargs.pop(invalid, None)

    return kwargs


def create_database_engine(url: Optional[StrUrl] = None, **overrides: Any) -> Engine:
    """Create an engine for *url* (default: ``settings.DATABASE_URL``)."""
    resolved = str(url or settings.DATABASE_URL)
    try:
        sa_url = make_url(resolved)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid DATABASE_URL: {exc}") from exc

    _ensure_sqlite_parent_dir(sa_url)
    kwargs = build_engine_kwargs(sa_url)
    kwargs.update(overrides)

    engine = create_engine(sa_url, **kwargs)
    logger.debug(
        "SQLAlchemy engine created (dialect=%s, pool=%s, pool_size=%s, max_overflow=%s)",
        sa_url.get_backend_name(),
        kwargs.get("poolclass", QueuePool).__name__,
        kwargs.get("pool_size", "n/a"),
        kwargs.get("max_overflow", "n/a"),
    )
    return engine


# ---------------------------------------------------------------------------
# Process-wide engine + session factory
# ---------------------------------------------------------------------------
engine: Engine = create_database_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    # Attributes stay loaded after commit: response models can be serialised
    # without triggering extra SELECTs or DetachedInstanceError.
    expire_on_commit=False,
    class_=Session,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped session; roll back on error, always close.

    Usage::

        @router.get("/things")
        def list_things(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts, schedulers and CLI entry points.

    Commits on success, rolls back on any exception, always closes::

        with session_scope() as db:
            db.add(obj)
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------
def init_db() -> None:
    """Make sure the schema the application needs exists.

    * SQLite / development – ``Base.metadata.create_all`` (plus the legacy
      additive column migration) so a fresh checkout boots with zero setup.
    * PostgreSQL – Alembic owns the schema (``alembic upgrade head``).
      ``create_all(checkfirst=True)`` is still available behind
      ``DB_AUTO_CREATE_SCHEMA`` for throw-away environments; it is disabled by
      default in production so a deploy can never silently drift away from the
      migration history.
    """
    # Import side-effect: registers every model on Base.metadata.
    import_module("app.models")

    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)
        migrate_sqlite_columns()
        return

    if settings.DB_AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Schema verified against %s", settings.masked_database_url())
    else:
        logger.info(
            "Schema is managed by Alembic (DB_AUTO_CREATE_SCHEMA=false); "
            "run `alembic upgrade head` before starting the API."
        )


def migrate_sqlite_columns() -> None:
    """Additive, best-effort column migration for legacy SQLite files."""
    if not settings.is_sqlite:
        return
    try:
        inspector = inspect(engine)
        with engine.connect() as conn:
            for table_name in inspector.get_table_names():
                columns = {col["name"] for col in inspector.get_columns(table_name)}
                model_table = Base.metadata.tables.get(table_name)
                if model_table is None:
                    continue
                for col in model_table.columns:
                    if col.name not in columns:
                        col_type = col.type.compile(engine.dialect)
                        nullable = "NULL" if col.nullable else "NOT NULL DEFAULT ''"
                        conn.execute(
                            text(f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}")
                        )
            conn.commit()
    except Exception as exc:  # pragma: no cover - schema drift is non-fatal
        logger.debug("SQLite column migration skipped: %s", exc)


# ---------------------------------------------------------------------------
# PostgreSQL session context (row-level security)
# ---------------------------------------------------------------------------
def set_rls_context(db: Session, school_id: Optional[int], role: str) -> None:
    """Publish the tenant context on the PostgreSQL session.

    Policies in ``sql/002_security_firewall.sql`` read ``app.school_id`` and
    ``app.role`` through ``current_setting(...)``.  ``set_config(..., true)`` is
    transaction-local, which is exactly what a request-scoped session needs.
    No-op on SQLite.
    """
    if not settings.is_postgres:
        return
    try:
        db.execute(
            text("SELECT set_config('app.school_id', :school_id, true)"),
            {"school_id": str(school_id) if school_id is not None else ""},
        )
        db.execute(text("SELECT set_config('app.role', :role, true)"), {"role": role or ""})
    except SQLAlchemyError as exc:
        logger.debug("Could not set RLS context: %s", exc)


# ---------------------------------------------------------------------------
# Operational helpers
# ---------------------------------------------------------------------------
def check_database_connection() -> bool:
    """Lightweight liveness probe (``SELECT 1``). Safe for /health endpoints."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Database health check failed: %s", exc)
        return False


def dispose_engine() -> None:
    """Close every pooled connection (call from shutdown hooks / forks)."""
    engine.dispose()
    logger.info("Database connection pool disposed.")
