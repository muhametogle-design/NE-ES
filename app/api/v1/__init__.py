"""V1 API routers."""
from fastapi import APIRouter

from app.api.v1.classrooms import router as classrooms_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(classrooms_router)

__all__ = ["api_v1_router", "classrooms_router"]
