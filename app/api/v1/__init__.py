"""Version-1 API routers.

Each module in this package exposes a ``router`` whose prefix already starts
with ``/v1/...``; ``app.main`` mounts the aggregate ``v1_router`` under
``/api`` so the final paths are ``/api/v1/...`` — consistent with the existing
``/api/v1/state`` and ``/api/v1/school`` routers.
"""
from fastapi import APIRouter

from app.api.v1.districts import router as districts_router

v1_router = APIRouter()
v1_router.include_router(districts_router)

__all__ = ["v1_router", "districts_router"]
