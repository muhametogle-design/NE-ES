"""Application settings — environment-driven via pydantic-settings.

All settings are prefixed ``NE_EMIS_`` so they can be injected by
docker-compose / the dev container without colliding with other variables.

Production hardening
--------------------
When ``NE_EMIS_ENV=production`` strict validators reject:

* weak/default secret keys (``admin1234``, ``change-me``, short keys, …);
* wildcard or non-``https`` CORS origins;

and a strict ``Content-Security-Policy`` (``default-src 'self'``) is applied
unless explicitly overridden.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Security constants
# ---------------------------------------------------------------------------
_MIN_PRODUCTION_KEY_LENGTH = 32

# Exact values that are never acceptable in production.
_WEAK_KEY_EXACT = {
    "insecure-dev-key-change-me",
    "changeme",
    "change-me",
    "change_me",
    "admin1234",
    "password",
    "secret",
    "neemis",
    "ne-emis",
    "test",
    "dev",
}

# Substrings that flag a placeholder/derivative secret.
_WEAK_KEY_FRAGMENTS = (
    "change-me",
    "changeme",
    "change_me",
    "admin1234",
    "insecure",
    "placeholder",
    "example",
    "your-secret",
    "xxxxxxxx",
)

# Strict production CSP (per security baseline). Overridable via
# NE_EMIS_CONTENT_SECURITY_POLICY when the app needs extra sources.
_PRODUCTION_CSP = "default-src 'self'"

# Development CSP — keeps Vite HMR (inline React-Refresh preamble, ws:/wss:
# sockets) and Google Fonts working while still sending the header.
_DEVELOPMENT_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NE_EMIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    app_name: str = "NE-EMIS"
    env: str = Field(
        default="development",
        pattern="^(development|staging|production|test)$",
    )
    api_v1_prefix: str = "/api"

    # --- Security / JWT ---
    secret_key: str = Field(
        default="insecure-dev-key-change-me",
        description="HMAC signing key for JWT access tokens. "
        "Must be a strong, unique value in production.",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # --- Database ---
    database_url: str = "sqlite:///./ne_emis.db"

    # --- CORS ---
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # --- Security headers ---
    # None → environment-specific default (strict in production, relaxed in dev).
    content_security_policy: Optional[str] = Field(
        default=None,
        description="Override the Content-Security-Policy header value.",
    )
    hsts_max_age: int = Field(
        default=31536000,
        description="Strict-Transport-Security max-age (seconds); 1 year default.",
    )

    # --- Rate limiting (slowapi) ---
    rate_limit_enabled: bool = True
    login_rate_limit: str = Field(
        default="5/minute",
        description="Auth login rate limit, e.g. '5/minute' or '10/hour'.",
    )

    # --- First-boot seed admin ---
    seed_admin_email: str = "admin@neemis.edu"
    seed_admin_password: str = "admin1234"
    seed_admin_full_name: str = "System Administrator"

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------
    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Allow CORS origins to be supplied as a JSON or CSV string."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("secret_key")
    @classmethod
    def _enforce_strong_secret_key(cls, value: str, info) -> str:
        """Reject weak/default secret keys when running in production."""
        env = info.data.get("env", "development")
        if env != "production":
            return value

        key = (value or "").strip()
        default_key = cls.model_fields["secret_key"].default

        errors: list[str] = []
        if not key or key == default_key:
            errors.append("the built-in development default key is not allowed")
        if len(key) < _MIN_PRODUCTION_KEY_LENGTH:
            errors.append(
                f"key must be at least {_MIN_PRODUCTION_KEY_LENGTH} characters "
                f"(got {len(key)})"
            )
        low = key.lower()
        if low in _WEAK_KEY_EXACT:
            errors.append("key is on the well-known weak-secret list")
        matched_fragments = [f for f in _WEAK_KEY_FRAGMENTS if f in low]
        if matched_fragments:
            errors.append(
                "key looks like a placeholder (contains: "
                f"{', '.join(sorted(set(matched_fragments)))})"
            )

        if errors:
            raise ValueError(
                "NE_EMIS_SECRET_KEY is insecure for ENV=production: "
                + "; ".join(errors)
                + ". Generate one with: openssl rand -hex 32"
            )
        return key

    @field_validator("cors_origins")
    @classmethod
    def _restrict_cors_in_production(cls, origins: List[str], info) -> List[str]:
        """Production CORS must be explicit and TLS-only."""
        env = info.data.get("env", "development")
        if env != "production":
            return origins

        if not origins:
            raise ValueError(
                "NE_EMIS_CORS_ORIGINS must list at least one origin in production"
            )
        for origin in origins:
            if origin.strip() == "*":
                raise ValueError(
                    "Wildcard CORS origin '*' is not allowed in production"
                )
            if not origin.startswith("https://"):
                raise ValueError(
                    f"CORS origin {origin!r} must use https:// in production "
                    "(set NE_EMIS_CORS_ORIGINS to your explicit TLS frontend origin)"
                )
        return origins

    @model_validator(mode="after")
    def _apply_environment_security_defaults(self) -> "Settings":
        """Populate environment-specific defaults that depend on other fields."""
        if not self.content_security_policy:
            self.content_security_policy = (
                _PRODUCTION_CSP if self.is_production else _DEVELOPMENT_CSP
            )
        return self

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
