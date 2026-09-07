"""Version-1 API routes, mounted by app.main under /api.

Academic routers are reusable: their /v1/school aliases share exactly the same
handlers and authorization as the canonical resource URLs.
"""
from fastapi import APIRouter

from app.api.v1.districts import router as districts_router
from app.api.v1.biometrics import router as biometrics_router
from app.api.v1.students import router as students_router
from app.api.v1.teachers import router as teachers_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.classrooms import router as classrooms_router
from app.api.v1.media import router as media_router

v1_router = APIRouter()
v1_router.include_router(districts_router)
v1_router.include_router(biometrics_router)
v1_router.include_router(media_router)
v1_router.include_router(students_router, prefix="/v1/students")
v1_router.include_router(teachers_router, prefix="/v1/teachers")
v1_router.include_router(subjects_router, prefix="/v1/subjects")
v1_router.include_router(classrooms_router, prefix="/v1/classrooms")

__all__ = ["v1_router"]
