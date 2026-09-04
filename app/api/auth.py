"""Authentication endpoints: login, current user, and registration helpers."""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession, require_roles
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )
    return user


def _issue_token(user: User) -> Token:
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token(
        subject=user.id,
        expires_delta=expires,
        extra_claims={"role": user.role.value, "email": user.email},
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires.total_seconds()),
        user=UserRead.model_validate(user),
    )


@router.post("/login", response_model=Token, summary="OAuth2 password login")
def login_oauth2(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """Standard OAuth2 form login (``username`` field carries the email)."""
    user = _authenticate(db, form_data.username, form_data.password)
    return _issue_token(user)


@router.post("/login/json", response_model=Token, summary="JSON login")
def login_json(payload: LoginRequest, db: DbSession) -> Token:
    """Convenience JSON login for frontends that don't send form data."""
    user = _authenticate(db, payload.email, payload.password)
    return _issue_token(user)


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff account (admin only)",
    dependencies=[Depends(require_roles(UserRole.admin))],
)
def register(payload: UserCreate, db: DbSession) -> User:
    existing = db.scalar(
        select(User).where(User.email == payload.email.lower().strip())
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(
        email=payload.email.lower().strip(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
