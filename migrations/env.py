"""Alembic migration environment for NE-EMIS.

Resolves the database URL from the DATABASE_URL environment variable first
(CI / Docker / production convention), then falls back to the application's
pydantic settings (local .env or the built-in default).
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import the application's declarative Base and pull in every model module so
# that Base.metadata contains the full schema (autogenerate diffing source).
from app.models.base import Base  # noqa: E402
import app.models  # noqa: F401,E402  (registers all models on Base.metadata)
from app.core.config import settings  # noqa: E402

config = context.config

# Interpret the config file for Python logging if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _resolve_url() -> str:
    """DATABASE_URL env var wins; otherwise the app settings (env/.env)."""
    env_url = os.environ.get("DATABASE_URL", "").strip()
    return env_url or settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DB needed)."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _resolve_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
