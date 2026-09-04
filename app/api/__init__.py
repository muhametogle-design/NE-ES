from app.api.auth import router as auth_router
from app.api.school import router as school_router
from app.api.state import router as state_router
from app.api.ws import router as ws_router

__all__ = ["auth_router", "school_router", "state_router", "ws_router"]
