import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, WebSocket, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.db import get_db, set_rls_context, SessionLocal
from app.core.security import decode_token
from app.models.tenancy import User
from app.models.compliance import SecurityAuditLog

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif "authorization" in request.headers:
        auth_hdr = request.headers.get("authorization", "")
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()
        else:
            token = auth_hdr.strip()
    
    if not token:
        # Fallback to cookie or query parameter
        token = request.cookies.get("access_token") or request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject missing")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or account disabled")

    set_rls_context(db, user.school_id, user.role)
    return user

async def get_current_user_ws(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        # Check cookie
        token = websocket.cookies.get("access_token")

    if not token:
        await websocket.close(code=1008)
        raise HTTPException(status_code=401, detail="Missing WebSocket authentication token")

    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008)
        raise HTTPException(status_code=401, detail="Invalid token for WebSocket")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        await websocket.close(code=1008)
        raise HTTPException(status_code=401, detail="User inactive or missing")

    return user

def require_role(*roles: str):
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role '{user.role}' does not have required permissions ({', '.join(roles)})"
            )
        return user
    return role_checker

def require_school_tenant(user: User = Depends(get_current_user)) -> User:
    if user.role not in ["school_manager", "teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="School tenant authorization required"
        )
    if not user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not assigned to any school tenant"
        )
    return user

def state_access_guard(user: User = Depends(get_current_user)) -> User:
    if user.role not in ["state_admin", "inspector"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="State ministry access privileges required"
        )
    return user

def financial_firewall(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    if user.role in ["state_admin", "inspector"]:
        # Log blocked attempt in SecurityAuditLog
        audit = SecurityAuditLog(
            user_id=user.id,
            action="BLOCKED_FINANCE_ACCESS",
            resource=f"finance:{request.url.path}",
            status="BLOCKED",
            details=f"State role '{user.role}' attempted unauthorized access to private school financial records.",
            ip_address=request.client.host if request.client else None
        )
        db.add(audit)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Financial records restricted to school tenants. State oversight firewalled."
        )

    if user.role not in ["school_manager", "teacher"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant financial access required"
        )
    return user
