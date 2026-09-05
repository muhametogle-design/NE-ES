"""Central application settings for NE-ES / NE-EMIS.

The module is the single source of truth for database connectivity.  It is
imported by:

* ``app/db/session.py``      – engine + session factory (runtime)
* ``alembic/env.py``         – migration target URL (deploy time)
* ``app/main.py``            – startup wiring

Design rules
------------
1. ``DATABASE_URL`` is the primary knob and **must** be a SQLAlchemy URL.
   PostgreSQL 16 is the production target and is driven through
   ``psycopg2`` (``postgresql+psycopg2://…``).
2. Vendor spellings (``postgres://``, ``postgresql://`` — Heroku, Render,
   Fly.io, Supabase, Railway) are normalised onto ``postgresql+psycopg2``
   so a copy-pasted connection string just works.
3. When ``DATABASE_URL`` is absent the URL is composed from the discrete
   ``POSTGRES_*`` variables.  Only when *neither* is set do we fall back to
   the zero-config SQLite file used for local hacking and the test-suite.
4. SQLite in ``APP_ENV=production`` is rejected — it cannot serve a
   multi-worker deployment.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional
from urllib.parse import quote, urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("ne_emis.config")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Syntax accepted for PostgreSQL. Everything is rewritten to the driver form.
POSTGRES_SCHEMES = frozenset(
    {
        "postgres",
        "postgresql",
        "postgres+psycopg2",
        "postgresql+psycopg2",
    }
)
SQLITE_SCHEMES = frozenset({"sqlite", "sqlite+pysqlite", "sqlite+aiosqlite"})

#: Canonical driver used for every PostgreSQL connection.
POSTGRES_DRIVER = "postgresql+psycopg2"

#: Zero-config fallback used only for local development and tests.
DEFAULT_SQLITE_URL = "sqlite:///./data/schoolsystem.db"

PRODUCTION_ENVIRONMENTS = frozenset({"production", "prod", "live"})
TEST_ENVIRONMENTS = frozenset({"test", "testing", "ci"})


def normalise_database_url(url: str) -> str:
    """Return *url* rewritten onto an explicit, supported SQLAlchemy driver.

    ``postgres://user:pw@host:5432/db``  ->  ``postgresql+psycopg2://user:pw@host:5432/db``
    ``postgresql://…``                   ->  ``postgresql+psycopg2://…``
    ``sqlite:///…``                      ->  unchanged
    """
    cleaned = (url or "").strip().strip("'\"")
    if not cleaned:
        raise ValueError("DATABASE_URL is empty; set a PostgreSQL connection string.")

    lowered = cleaned.lower()
    for legacy in ("postgres://", "postgresql://", "postgres+psycopg2://"):
        if lowered.startswith(legacy):
            return f"{POSTGRES_DRIVER}://{cleaned.split('://', 1)[1]}"
    return cleaned


def validate_database_url(url: str) -> str:
    """Validate the scheme/payload of a normalised URL and return it."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()

    if scheme in SQLITE_SCHEMES:
        return url

    if scheme not in POSTGRES_SCHEMES:
        raise ValueError(
            f"Unsupported DATABASE_URL scheme {scheme!r}. "
            "Use postgresql+psycopg2://… (PostgreSQL 16) or sqlite:///… for local dev."
        )

    database = parts.path.lstrip("/")
    if not database:
        raise ValueError(
            "DATABASE_URL is missing the database name "
            "(expected postgresql+psycopg2://user:password@host:5432/dbname)."
        )
    if not parts.hostname:
        raise ValueError("DATABASE_URL is missing the database host.")
    return url


def build_postgres_url(
    *,
    user: str,
    password: Optional[str],
    host: str,
    port: int,
    database: str,
    sslmode: Optional[str] = None,
) -> str:
    """Compose a psycopg2 URL from discrete parts, safely quoting credentials."""
    netloc = quote(user, safe="")
    if password:
        netloc += f":{quote(password, safe='')}"
    netloc += f"@{host}:{port}"

    url = f"{POSTGRES_DRIVER}://{netloc}/{database.lstrip('/')}"
    if sslmode:
        separator = "&" if "?" in url else "?"
        url += f"{separator}sslmode={sslmode}"
    return url


class Settings(BaseSettings):
    """Environment-driven application settings.

    Values are read from (highest priority first): constructor kwargs,
    process environment, ``.env`` file, Docker/Kubernetes secrets.
    """

    # --- environment --------------------------------------------------------
    # Declared first so validators below can depend on it via ``info.data``.
    APP_ENV: str = "development"
    APP_NAME: str = "NE-EMIS"

    # --- database -----------------------------------------------------------
    DATABASE_URL: Optional[str] = None

    # Discrete parts, used only when DATABASE_URL is not supplied.
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_SSLMODE: Optional[str] = None

    # Connection pool (PostgreSQL only — SQLite uses fixed pools).
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True

    # Connection tuning / observability.
    DB_ECHO: bool = False
    DB_CONNECT_TIMEOUT: int = 10
    DB_STATEMENT_TIMEOUT_MS: int = 0  # 0 = inherit the server default
    DB_APPLICATION_NAME: str = "ne-es-api"

    # Schema bootstrap. ``None`` => auto-create outside production only.
    DB_AUTO_CREATE_SCHEMA: Optional[bool] = None

    # --- security -----------------------------------------------------------
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # --- application --------------------------------------------------------
    CORS_ORIGINS_RAW: str = "*"
    COOKIE_SAMESITE: str = "lax"
    COOKIE_SECURE: str = "auto"
    ATTENDANCE_DEADLINE: str = "12:00"
    ALARM_AUDIT_TIME: str = "15:00"
    PLATFORM_TIMEZONE: str = "Africa/Nairobi"
    AUTO_SEED_DEMO: bool = True
    ENABLE_SCHEDULER: bool = True

    # --- backups ------------------------------------------------------------
    BACKUP_TIME: str = "00:00"
    BACKUP_DIR: str = "data/backups"
    BACKUP_RETENTION_DAYS: int = 30
    ENABLE_BACKUP_SCHEDULER: bool = True
    BACKUP_ENCRYPTION_KEY: Optional[str] = None

    # --- webauthn / rate limiting ------------------------------------------
    WEBAUTHN_RP_ID: str = "auto"
    WEBAUTHN_EXPECTED_ORIGINS: str = "auto"
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _normalise_env(cls, v: object) -> str:
        return str(v).strip().lower() if v is not None else "development"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _clean_database_url(cls, v: object) -> Optional[str]:
        if v is None:
            return None
        text = str(v).strip()
        return text or None

    @field_validator("BACKUP_ENCRYPTION_KEY", mode="before")
    @classmethod
    def validate_backup_key(cls, v, info):
        if not v and info.data.get("APP_ENV") in PRODUCTION_ENVIRONMENTS:
            jwt_key = info.data.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
            return jwt_key[:32].ljust(32, "0")
        if not v:
            return "0123456789abcdef0123456789abcdef"  # 32 bytes fallback for aes-256
        return v

    @model_validator(mode="after")
    def _resolve_database_settings(self) -> "Settings":
        """Resolve DATABASE_URL, then enforce environment invariants."""
        # 1. Compose from POSTGRES_* parts when DATABASE_URL is not supplied.
        if not self.DATABASE_URL and self.POSTGRES_HOST and self.POSTGRES_USER:
            self.DATABASE_URL = build_postgres_url(
                user=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                database=self.POSTGRES_DB or "ne_es_dev",
                sslmode=self.POSTGRES_SSLMODE,
            )

        # 2. Fall back to SQLite (development / tests) or fail loudly.
        if not self.DATABASE_URL:
            if self.is_production:
                raise ValueError(
                    "DATABASE_URL is required when APP_ENV=production. "
                    "Example: postgresql+psycopg2://postgres:postgres@localhost:5432/ne_es_dev"
                )
            self.DATABASE_URL = DEFAULT_SQLITE_URL
            logger.warning(
                "DATABASE_URL is not set – falling back to SQLite (%s). "
                "Set DATABASE_URL before deploying.",
                self.DATABASE_URL,
            )

        # 3. Normalise the driver and validate the payload.
        self.DATABASE_URL = validate_database_url(normalise_database_url(self.DATABASE_URL))

        # 4. Environment invariants.
        if self.is_production and self.is_sqlite:
            raise ValueError(
                "SQLite is not supported in production (APP_ENV=production). "
                "Provide a PostgreSQL 16 connection string via DATABASE_URL."
            )
        if self.is_production and self.JWT_SECRET_KEY.startswith("dev-"):
            logger.warning(
                "SECURITY: JWT_SECRET_KEY still has its development default – "
                "override it before going live."
            )

        # 5. Schema bootstrap policy: Alembic owns PostgreSQL in production.
        if self.DB_AUTO_CREATE_SCHEMA is None:
            self.DB_AUTO_CREATE_SCHEMA = not self.is_production

        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.APP_ENV in PRODUCTION_ENVIRONMENTS

    @property
    def is_development(self) -> bool:
        return self.APP_ENV in {"development", "dev", "local"}

    @property
    def is_test(self) -> bool:
        return self.APP_ENV in TEST_ENVIRONMENTS

    @property
    def is_sqlite(self) -> bool:
        return urlsplit(self.DATABASE_URL or "").scheme.lower() in SQLITE_SCHEMES

    @property
    def is_postgres(self) -> bool:
        return urlsplit(self.DATABASE_URL or "").scheme.lower() in POSTGRES_SCHEMES

    @property
    def database_url(self) -> str:
        """Resolved SQLAlchemy URL (lower-case alias for legacy call sites)."""
        return self.DATABASE_URL or DEFAULT_SQLITE_URL

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Alias kept for tooling that expects the Flask-style name."""
        return self.database_url

    def pool_options(self) -> dict:
        """QueuePool sizing for PostgreSQL (ignored by SQLite)."""
        return {
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
            "pool_recycle": self.DB_POOL_RECYCLE,
            "pool_pre_ping": self.DB_POOL_PRE_PING,
        }

    def masked_database_url(self) -> str:
        """Connection string with the password replaced – safe for logs."""
        url = self.database_url
        parts = urlsplit(url)
        if not parts.password or not parts.hostname:
            return url
        netloc = parts.hostname
        if parts.username:
            netloc = f"{parts.username}:***@{netloc}"
        if parts.port:
            netloc = f"{netloc}:{parts.port}"
        return f"{parts.scheme}://{netloc}{parts.path}"


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
settings = Settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """FastAPI-friendly accessor; returns the module-level singleton."""
    return settings
