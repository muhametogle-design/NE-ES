from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_password, verify_password, hash_pin, verify_pin, create_access_token
from app.core.ratelimit import rate_limit
from app.models.tenancy import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, ChangePasswordRequest, SetPinRequest
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
@rate_limit(max_requests=settings.LOGIN_RATE_LIMIT, window_seconds=settings.LOGIN_RATE_WINDOW_SECONDS)
async def login(request: Request, login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = None
    if login_data.email and login_data.password:
        user = db.query(User).filter(User.email == login_data.email).first()
        if not user or not verify_password(login_data.password, user.password_hash):
            user = None
    elif login_data.staff_identifier and login_data.pin:
        user = db.query(User).filter(User.staff_identifier == login_data.staff_identifier).first()
        if not user or not user.staff_pin_hash or not verify_pin(login_data.pin, user.staff_pin_hash):
            user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please verify your email/password or Staff ID/PIN.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "school_id": user.school_id,
        "email": user.email
    })

    secure_cookie = settings.COOKIE_SECURE == "true" or (
        settings.COOKIE_SECURE == "auto" and settings.APP_ENV == "production"
    )

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=secure_cookie,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user

@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Successfully logged out", "detail": "Session cookie cleared"}

@router.post("/change-password", response_model=MessageResponse)
async def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}

@router.post("/set-pin", response_model=MessageResponse)
async def set_pin(data: SetPinRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(data.pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")

    user.staff_pin_hash = hash_pin(data.pin)
    db.commit()
    return {"message": "Staff PIN updated successfully"}
