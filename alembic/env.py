"""Alembic migration environment for NE-ES (PostgreSQL 16 / psycopg2).

Database URL resolution (highest priority first)
------------------------------------------------
1. ``$NE_EMIS_DATABASE_URL``  – explicit override (CI, one-off runs)
2. ``$DATABASE_URL``          – the usual 12-factor variable
3. ``app.core.config.settings.DATABASE_URL`` – composed from ``DATABASE_URL`` or
   the discrete ``POSTGRES_*`` variables, reading ``.env`` like the app does

The URL is **never** hardcoded in ``alembic.ini``; it is injected at runtime
here, so a single source of truth (``app.core.config``) drives both the app and
the migrations.

Target metadata
---------------
``app.models.base.Base.metadata``.  Importing the ``app.models`` package plus
the individual modules below registers every active model — tenancy
(``private_schools``, ``users``, ``school_roll_sequences``, ``academic_years``),
academic, finance, compliance, backups, biometrics, absence and syllabus — so
``alembic revision --autogenerate`` sees the complete schema.  There is exactly
one declarative base in the codebase (``app.models.base.Base``); the legacy
``app.core.database.Base`` now aliases it, which is what keeps
``InvalidRequestError: Table 'x' is already defined for this MetaData`` away.
"""
from __future__ import annotations

import logging
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import (  # noqa: E402
    normalise_database_url,
    settings,
    validate_database_url,
)
from app.db.session import build_connect_args  # noqa: E402  (shared libpq options)
from app.models.base import Base  # noqa: E402  (the only declarative base)
from app.models import all_models  # noqa: E402,F401  (explicit model registry)
from app.models import (  # noqa: E402,F401  (register tables on Base.metadata)
    absence,
    academic,
    backups,
    biometrics,
    compliance,
    finance,
    syllabus,
    tenancy,
)
from app.models.tenancy import (  # noqa: E402,F401  (bridge models: tenant FKs)
    AcademicYear,
    PrivateSchool,
    SchoolRollSequence,
    User,
)

# --- Alembic Config object (gives access to alembic.ini values) -------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# --- Target metadata for `--autogenerate` -----------------------------------
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# URL resolution
# ---------------------------------------------------------------------------
def get_database_url() -> str:
    """Resolve the migration URL: env override, then app settings."""
    raw = (
        os.getenv("NE_EMIS_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or settings.DATABASE_URL
        or ""
    )
    return validate_database_url(normalise_database_url(raw))


DATABASE_URL = get_database_url()

# ConfigParser interpolates '%', so a URL-encoded password ('%40' -> '@') must
# be escaped before it is stored in the ini section.
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")


# ---------------------------------------------------------------------------
# Autogenerate filters
# ---------------------------------------------------------------------------
def include_object(object_: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
    """Ignore database objects that are not described by the ORM metadata.

    Keeps autogenerate from proposing ``drop_table`` for extension tables
    (``spatial_ref_sys``, ``pg_stat_statements`` …) or for temporary schemas
    that live in the same database.
    """
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def _common_configure_kwargs() -> dict[str, Any]:
    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
        # SQLite cannot ALTER in place; PostgreSQL does not need batch mode.
        "render_as_batch": IS_SQLITE,
        "include_object": include_object,
        "version_table": "alembic_version",
        "transaction_per_migration": True,
    }


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=DATABASE_URL,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_common_configure_kwargs(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    section = dict(config.get_section(config.config_ini_section, {}) or {})
    section["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        # Migrations are short-lived: no pool reuse, no pre-ping overhead.
        poolclass=pool.NullPool,
        connect_args=build_connect_args(DATABASE_URL),
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, **_common_configure_kwargs())

        with context.begin_transaction():
            context.run_migrations()


def _log_resolved_target() -> None:
    """Helpful, password-free startup diagnostics."""
    parts = DATABASE_URL.split("@", 1)
    safe = f"***@{parts[1]}" if len(parts) == 2 else DATABASE_URL
    logger.info(
        "Alembic target: %s (dialect=%s, tables registered=%d)",
        safe,
        "postgresql" if IS_POSTGRES else ("sqlite" if IS_SQLITE else "unknown"),
        len(target_metadata.tables),
    )
    if not target_metadata.tables:
        raise RuntimeError(
            "No tables registered on Base.metadata — check that alembic/env.py "
            "imports app.models.tenancy and the other model modules."
        )


_log_resolved_target()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
