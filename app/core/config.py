"""Application settings — environment-driven via pydantic-settings.

All settings are prefixed ``NE_EMIS_`` so they can be injected by
docker-compose / the dev container without colliding with other variables.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    env: str = Field(default="development")
    api_v1_prefix: str = "/api"

    # --- Security / JWT ---
    secret_key: str = Field(
        default="insecure-dev-key-change-me",
        description="HMAC signing key for JWT access tokens.",
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

    # --- First-boot seed admin ---
    seed_admin_email: str = "admin@neemis.edu"
    seed_admin_password: str = "admin1234"
    seed_admin_full_name: str = "System Administrator"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        """Allow CORS origins to be supplied as a JSON string in env vars."""
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("["):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            # Comma-separated fallback
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
