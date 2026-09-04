"""Auth schemas: token payloads and user (de)serialization."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.staff


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class Token(BaseModel):
    """OAuth2-compatible token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserRead


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None


class LoginRequest(BaseModel):
    """JSON login alternative (the OAuth2 form flow is also supported)."""

    email: EmailStr
    password: str
