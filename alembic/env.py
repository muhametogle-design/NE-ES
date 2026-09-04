"""Alembic migration environment for NE-EMIS.

Database URL resolution (highest priority first):
    1. ``NE_EMIS_DATABASE_URL`` / ``DATABASE_URL`` environment variable
    2. ``app.core.config.settings.DATABASE_URL`` (reads .env / host environment)

Target metadata:
    ``app.models.base.Base.metadata`` — importing the ``app.models`` package
    registers every model (tenancy, academic, finance, compliance, backups,
    biometrics, absence, syllabus) on the declarative registry before
    autogenerate/upgrade run.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

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

# Target metadata for autogenerate support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Resolve the database URL dynamically.
# ---------------------------------------------------------------------------
def get_database_url() -> str:
    """Prefer explicit environment variables, then the app settings object."""
    return (
        os.getenv("NE_EMIS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or settings.DATABASE_URL
    )


DATABASE_URL = get_database_url()
config.set_main_option("sqlalchemy.url", DATABASE_URL)

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
