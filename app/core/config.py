from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import field_validator

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/schoolsystem.db"
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    APP_ENV: str = "development"
    APP_NAME: str = "NE-EMIS"
    CORS_ORIGINS_RAW: str = "*"
    COOKIE_SAMESITE: str = "lax"
    COOKIE_SECURE: str = "auto"
    ATTENDANCE_DEADLINE: str = "12:00"
    ALARM_AUDIT_TIME: str = "15:00"
    PLATFORM_TIMEZONE: str = "Africa/Nairobi"
    AUTO_SEED_DEMO: bool = True
    ENABLE_SCHEDULER: bool = True
    BACKUP_TIME: str = "00:00"
    BACKUP_DIR: str = "data/backups"
    BACKUP_RETENTION_DAYS: int = 30
    ENABLE_BACKUP_SCHEDULER: bool = True
    BACKUP_ENCRYPTION_KEY: Optional[str] = None
    WEBAUTHN_RP_ID: str = "auto"
    WEBAUTHN_EXPECTED_ORIGINS: str = "auto"
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    @field_validator("BACKUP_ENCRYPTION_KEY", mode="before")
    @classmethod
    def validate_backup_key(cls, v, info):
        if not v and info.data.get("APP_ENV") == "production":
            jwt_key = info.data.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
            return jwt_key[:32].ljust(32, "0")
        if not v:
            return "0123456789abcdef0123456789abcdef"  # 32 bytes fallback for aes-256
        return v

settings = Settings()
