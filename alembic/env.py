"""Alembic migration environment for NE-EMIS.

Database URL resolution (highest priority first):
    1. ``NE_EMIS_DATABASE_URL`` — explicit, Alembic-only override.
    2. ``DATABASE_URL`` — from the shell environment or from the repo-root
       ``.env`` file, which is loaded with python-dotenv *before* anything
       from ``app`` is imported (shell variables win over ``.env`` values).
    3. ``app.core.config.settings.DATABASE_URL`` — the application default
       (SQLite at ``./data/schoolsystem.db``), so Alembic always targets the
       same database the API would use.

The resolved URL is written back into the Alembic config via
``config.set_main_option("sqlalchemy.url", ...)``; the ``sqlalchemy.url``
entry in ``alembic.ini`` is intentionally left blank.

Target metadata:
    ``app.models.base.Base.metadata`` — importing the ``app.models`` package
    registers every model (tenancy, academic, finance, compliance, backups,
    biometrics, absence, syllabus) on the declarative registry before
    autogenerate/upgrade run.
"""
from __future__ import annotations

import logging
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

# ---------------------------------------------------------------------------
# Load the repo-root .env into os.environ FIRST, so that os.getenv() below and
# app.core.config.settings (imported afterwards) both see the same
# DATABASE_URL regardless of the directory `alembic` is invoked from.
# Variables already exported in the shell take precedence (override=False).
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

# ---------------------------------------------------------------------------
# Import the declarative Base AND the models package so all tables register.
# ---------------------------------------------------------------------------
from app.core.config import settings  # noqa: E402
from app.models import Base  # noqa: E402  (re-exported from app.models.base)
from app.models import (  # noqa: E402,F401
    absence,
    academic,
    backups,
    base,
    biometrics,
    compliance,
    finance,
    syllabus,
    tenancy,
)

config = context.config

# --- Logging configuration (from alembic.ini) ---
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Target metadata for autogenerate support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Resolve the database URL dynamically.
# ---------------------------------------------------------------------------
def get_database_url() -> str:
    """Return the target database URL (precedence documented in the module docstring)."""
    db_url = (
        os.getenv("NE_EMIS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or settings.DATABASE_URL
    )
    if not db_url:
        raise RuntimeError(
            "No database URL configured. Set DATABASE_URL in the environment or in "
            f"{REPO_ROOT / '.env'} (see .env.example)."
        )
    return db_url


DATABASE_URL = get_database_url()

# Override the (blank) alembic.ini value so engine_from_config() uses our URL.
# ConfigParser treats '%' as an interpolation marker, so a literal '%' (e.g. a
# URL-encoded password such as 'p%40ss') must be escaped as '%%' when stored;
# config.get_section() un-escapes it again when the engine is built.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

logger.info(
    "Target database: %s",
    make_url(DATABASE_URL).render_as_string(hide_password=True),
)

# SQLite needs batch mode (no native ALTER) and relaxed thread checks.
IS_SQLITE = DATABASE_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=IS_SQLITE,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (real connection + transaction)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False} if IS_SQLITE else {},
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=IS_SQLITE,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
