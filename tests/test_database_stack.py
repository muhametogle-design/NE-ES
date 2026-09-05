"""Tests for the PostgreSQL wiring: config, engine/pool, and metadata registry.

These tests are pure unit tests — they never open a connection, so they run in
CI without a database server.  Settings instances are built with
``_env_file=None`` so a developer's local ``.env`` cannot influence them.
"""
from __future__ import annotations

import pytest

from app.core.config import (
    Settings,
    build_postgres_url,
    normalise_database_url,
    validate_database_url,
)
from app.db.session import build_connect_args, build_engine_kwargs
from app.models.base import Base
from sqlalchemy.pool import NullPool, QueuePool, StaticPool

PG_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/ne_es_dev"


def make_settings(**overrides) -> Settings:
    """Build a Settings instance isolated from .env and the ambient env.

    Every database field is passed explicitly as ``None`` first so the
    ``DATABASE_URL`` that ``tests/conftest.py`` injects for the app cannot leak
    into these assertions.
    """
    base = {
        "APP_ENV": "development",
        "DATABASE_URL": None,
        "POSTGRES_HOST": None,
        "POSTGRES_PORT": 5432,
        "POSTGRES_USER": None,
        "POSTGRES_PASSWORD": None,
        "POSTGRES_DB": None,
        "POSTGRES_SSLMODE": None,
        "DB_AUTO_CREATE_SCHEMA": None,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


# ---------------------------------------------------------------------------
# URL normalisation / validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgres://u:p@db:5432/app", "postgresql+psycopg2://u:p@db:5432/app"),
        ("postgresql://u:p@db:5432/app", "postgresql+psycopg2://u:p@db:5432/app"),
        (PG_URL, PG_URL),
        ("  postgresql://u:p@db/app  ", "postgresql+psycopg2://u:p@db/app"),
        ("sqlite:///./data/schoolsystem.db", "sqlite:///./data/schoolsystem.db"),
    ],
)
def test_normalise_database_url(raw, expected):
    assert normalise_database_url(raw) == expected


def test_normalise_rejects_empty_url():
    with pytest.raises(ValueError, match="empty"):
        normalise_database_url("   ")


def test_validate_rejects_unknown_scheme():
    with pytest.raises(ValueError, match="Unsupported DATABASE_URL scheme"):
        validate_database_url("mysql://u:p@db/app")


def test_validate_requires_database_name():
    with pytest.raises(ValueError, match="missing the database name"):
        validate_database_url("postgresql+psycopg2://u:p@localhost:5432")


def test_build_postgres_url_quotes_credentials():
    url = build_postgres_url(
        user="ne es",
        password="p@ss w/ord",
        host="db.internal",
        port=5432,
        database="ne_es_dev",
        sslmode="require",
    )
    assert url.startswith("postgresql+psycopg2://ne%20es:p%40ss%20w%2Ford@db.internal:5432/ne_es_dev")
    assert url.endswith("sslmode=require")


# ---------------------------------------------------------------------------
# Settings resolution
# ---------------------------------------------------------------------------
def test_postgres_url_is_normalised_and_flagged():
    settings = make_settings(APP_ENV="production", DATABASE_URL="postgres://u:p@db:5432/ne_es")
    assert settings.DATABASE_URL == "postgresql+psycopg2://u:p@db:5432/ne_es"
    assert settings.is_postgres and not settings.is_sqlite
    assert settings.is_production


def test_postgres_parts_compose_a_url():
    settings = make_settings(
        APP_ENV="production",
        POSTGRES_HOST="db",
        POSTGRES_USER="ne_es",
        POSTGRES_PASSWORD="secret",
        POSTGRES_DB="ne_es_prod",
    )
    assert settings.DATABASE_URL == "postgresql+psycopg2://ne_es:secret@db:5432/ne_es_prod"


def test_sqlite_fallback_outside_production():
    settings = make_settings(APP_ENV="development")
    assert settings.is_sqlite
    assert settings.DATABASE_URL == "sqlite:///./data/schoolsystem.db"


def test_production_requires_a_database_url():
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        make_settings(APP_ENV="production")


def test_production_rejects_sqlite():
    with pytest.raises(ValueError, match="SQLite is not supported in production"):
        make_settings(APP_ENV="production", DATABASE_URL="sqlite:///./data/prod.db")


def test_pool_options_defaults():
    options = make_settings(APP_ENV="production", DATABASE_URL=PG_URL).pool_options()
    assert options == {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "pool_pre_ping": True,
    }


def test_masked_url_hides_password():
    settings = make_settings(APP_ENV="production", DATABASE_URL=PG_URL)
    assert "postgres:postgres" not in settings.masked_database_url()
    assert settings.masked_database_url() == "postgresql+psycopg2://postgres:***@localhost:5432/ne_es_dev"


def test_auto_create_schema_defaults_off_in_production():
    prod = make_settings(APP_ENV="production", DATABASE_URL=PG_URL)
    dev = make_settings(APP_ENV="development", DATABASE_URL=PG_URL)
    assert prod.DB_AUTO_CREATE_SCHEMA is False
    assert dev.DB_AUTO_CREATE_SCHEMA is True


# ---------------------------------------------------------------------------
# Engine / pool construction
# ---------------------------------------------------------------------------
def test_postgres_engine_kwargs():
    kwargs = build_engine_kwargs(PG_URL)
    assert kwargs["poolclass"] is QueuePool
    assert kwargs["pool_size"] == 10
    assert kwargs["max_overflow"] == 20
    assert kwargs["pool_timeout"] == 30
    assert kwargs["pool_recycle"] == 1800
    assert kwargs["pool_pre_ping"] is True
    assert kwargs["future"] is True


def test_nullpool_drops_sizing_options():
    kwargs = build_engine_kwargs(PG_URL, poolclass=NullPool)
    assert kwargs["poolclass"] is NullPool
    for key in ("pool_size", "max_overflow", "pool_timeout", "pool_recycle"):
        assert key not in kwargs


def test_sqlite_memory_uses_static_pool():
    kwargs = build_engine_kwargs("sqlite+pysqlite:///:memory:")
    assert kwargs["poolclass"] is StaticPool
    assert kwargs["connect_args"] == {"check_same_thread": False}
    assert "pool_size" not in kwargs


def test_sqlite_file_keeps_driver_default_pool():
    kwargs = build_engine_kwargs("sqlite:///./data/schoolsystem.db")
    assert "poolclass" not in kwargs
    assert kwargs["connect_args"] == {"check_same_thread": False}


def test_postgres_connect_args_include_libpq_options():
    args = build_connect_args("postgresql+psycopg2://u:p@db:5432/app?application_name=custom")
    # Options already present in the DSN are never duplicated for libpq.
    assert "application_name" not in args
    assert args["connect_timeout"] == 10


def test_connect_args_empty_for_sqlite():
    assert build_connect_args("sqlite:///./data/x.db") == {"check_same_thread": False}


# ---------------------------------------------------------------------------
# Single declarative base (no metadata duplication)
# ---------------------------------------------------------------------------
def test_legacy_base_aliases_are_the_same_object():
    import app.core.database as legacy
    import app.core.db as compat

    assert legacy.Base is Base
    assert compat.Base is Base


def test_duplicate_model_modules_do_not_register_tables():
    """app.models.student / app.models.user are aliases, not second mappings."""
    from app.models import academic, student, tenancy, user

    assert student.Student is academic.Student
    assert user.User is tenancy.User
    assert len([t for t in Base.metadata.tables if t == "students"]) == 1
    assert len([t for t in Base.metadata.tables if t == "users"]) == 1


def test_all_expected_tables_are_registered():
    expected = {
        "private_schools",
        "school_roll_sequences",
        "users",
        "academic_years",
        "school_classes",
        "subjects",
        "teaching_assignments",
        "timetable_slots",
        "students",
        "student_grades",
        "subject_attendance",
        "live_attendance",
        "tuition_rates",
        "student_invoices",
        "payment_transactions",
        "daily_submission_logs",
        "exam_submission_events",
        "communication_logs",
        "security_audit_log",
        "data_change_log",
        "backup_records",
        "backup_audit_events",
        "biometric_credentials",
        "biometric_verification_logs",
        "teacher_absences",
        "substitution_assignments",
        "syllabus_plans",
        "syllabus_topics",
        "syllabus_progress_entries",
    }
    assert expected.issubset(set(Base.metadata.tables))
