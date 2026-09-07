"""District (Regional Education Office) endpoints — ``/api/v1/districts``.

Access policy
    * ``GET``  — any state-ministry role (``state_admin``, ``inspector``).
    * ``POST`` / ``PATCH`` — ``state_admin`` only (districts are a state-level
      reference table; school tenants never manage them).
"""
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_role, state_access_guard
from app.core.db import get_db
from app.models.academic import District
from app.models.tenancy import PrivateSchool, User
from app.schemas.common import PaginatedResponse
from app.schemas.district import DistrictCreate, DistrictResponse, DistrictUpdate

router = APIRouter(prefix="/v1/districts", tags=["districts"])

require_state_admin = require_role("state_admin")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _school_count(db: Session, district_id: UUID) -> int:
    return db.query(func.count(PrivateSchool.id)).filter(PrivateSchool.district_id == district_id).scalar() or 0


def _serialize(db: Session, district: District, school_count: Optional[int] = None) -> DistrictResponse:
    if school_count is None:
        school_count = _school_count(db, district.id)
    return DistrictResponse.model_validate(district, from_attributes=True).model_copy(
        update={"school_count": school_count}
    )


def _get_district_or_404(db: Session, district_id: UUID) -> District:
    district = db.query(District).filter(District.id == district_id).first()
    if district is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    return district


def _ensure_code_available(db: Session, code: str, exclude_id: Optional[UUID] = None) -> None:
    query = db.query(District.id).filter(District.code == code)
    if exclude_id is not None:
        query = query.filter(District.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"District with code '{code}' already exists",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=PaginatedResponse[DistrictResponse], summary="List districts")
async def list_districts(
    region: Optional[str] = Query(None, description="Case-insensitive exact match on region"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    q: Optional[str] = Query(None, min_length=1, description="Search in code or name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(state_access_guard),
    db: Session = Depends(get_db),
):
    query = db.query(District)
    if region:
        query = query.filter(func.lower(District.region) == region.strip().lower())
    if is_active is not None:
        query = query.filter(District.is_active == is_active)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(District.code.ilike(pattern), District.name.ilike(pattern)))

    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    districts = (
        query.order_by(District.region, District.code)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    # One grouped query for the school counts of the current page.
    counts = {}
    if districts:
        rows = (
            db.query(PrivateSchool.district_id, func.count(PrivateSchool.id))
            .filter(PrivateSchool.district_id.in_([d.id for d in districts]))
            .group_by(PrivateSchool.district_id)
            .all()
        )
        counts = {district_id: count for district_id, count in rows}

    items = [_serialize(db, d, counts.get(d.id, 0)) for d in districts]
    return {"items": items, "total": total, "page": page, "pages": pages}


@router.post("", response_model=DistrictResponse, status_code=status.HTTP_201_CREATED, summary="Create district")
async def create_district(
    data: DistrictCreate,
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    _ensure_code_available(db, data.code)

    district = District(**data.model_dump())
    db.add(district)
    try:
        db.commit()
    except IntegrityError:
        # Concurrent insert with the same code slipped past the pre-check.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"District with code '{data.code}' already exists",
        )
    db.refresh(district)
    return _serialize(db, district, school_count=0)


@router.get("/{district_id}", response_model=DistrictResponse, summary="Get district")
async def get_district(
    district_id: UUID,
    user: User = Depends(state_access_guard),
    db: Session = Depends(get_db),
):
    district = _get_district_or_404(db, district_id)
    return _serialize(db, district)


@router.patch("/{district_id}", response_model=DistrictResponse, summary="Update district")
async def update_district(
    district_id: UUID,
    data: DistrictUpdate,
    user: User = Depends(require_state_admin),
    db: Session = Depends(get_db),
):
    district = _get_district_or_404(db, district_id)

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    if "code" in changes and changes["code"] != district.code:
        _ensure_code_available(db, changes["code"], exclude_id=district.id)

    for field, value in changes.items():
        setattr(district, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"District with code '{changes.get('code')}' already exists",
        )
    db.refresh(district)
    return _serialize(db, district)
