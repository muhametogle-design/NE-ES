"""Version-1 API routers.

Each module in this package exposes a ``router`` whose prefix already starts
with ``/v1/...``; ``app.main`` mounts the aggregate ``v1_router`` under
``/api`` so the final paths are ``/api/v1/...`` — consistent with the existing
``/api/v1/state`` and ``/api/v1/school`` routers.

``media.files_router`` is the exception: it is mounted at the application root
by ``app.main`` so uploaded portraits are served from ``/media/...`` (the value
of ``settings.MEDIA_URL_PREFIX``) rather than ``/api/media/...``.
"""
from fastapi import APIRouter

from app.api.v1.districts import router as districts_router
from app.api.v1.biometrics import router as biometrics_router
from app.api.v1.classrooms import router as classrooms_router
from app.api.v1.media import files_router as media_files_router
from app.api.v1.media import router as media_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.teachers import router as teachers_router

v1_router = APIRouter()
v1_router.include_router(districts_router)
v1_router.include_router(biometrics_router)
v1_router.include_router(teachers_router)
v1_router.include_router(subjects_router)
v1_router.include_router(classrooms_router)
v1_router.include_router(media_router)

__all__ = [
    "v1_router",
    "districts_router",
    "biometrics_router",
    "teachers_router",
    "subjects_router",
    "classrooms_router",
    "media_router",
    "media_files_router",
]
