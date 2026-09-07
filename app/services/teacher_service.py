"""Atomic staff-profile creation, login provisioning, and safe account binding."""
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.academic import Teacher
from app.models.tenancy import User
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherUserCreate
from app.services.tenant_service import TenantService


# The login keeps its own email, password, role and tenant. Only display fields
# are mirrored; rebinding a profile must never overwrite another login's secrets.
DISPLAY_FIELDS = (
    "first_name", "last_name", "phone", "qualifications", "designation", "bio", "is_department_head",
)


def _linkable_user(db: Session, school_id: int, user_id: int, teacher_id=None) -> User:
    account = db.query(User).filter_by(id=user_id, school_id=school_id).with_for_update().first()
    if account is None:
        raise HTTPException(404, "User not found in this school")
    if account.role != "teacher" or not account.is_active:
        raise HTTPException(400, "Only an active teacher user can be linked")
    existing = db.query(Teacher).filter(Teacher.user_id == account.id)
    if teacher_id is not None:
        existing = existing.filter(Teacher.id != teacher_id)
    if existing.first():
        raise HTTPException(409, "User is already linked to a teacher")
    return account


def _sync_display_fields(teacher: Teacher):
    if teacher.user:
        for field in DISPLAY_FIELDS:
            setattr(teacher.user, field, getattr(teacher, field))


def _commit(db: Session, teacher: Teacher) -> Teacher:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent email or user binding claim must roll back BOTH inserts.
        raise HTTPException(409, "Teacher account or staff identifier already exists") from None
    db.refresh(teacher)
    return teacher


def create_teacher(db: Session, school_id: int, data: TeacherCreate) -> Teacher:
    credentials = data.create_user
    if data.password is not None:
        credentials = TeacherUserCreate(email=data.email, password=data.password)

    account = None
    if data.user_id is not None:
        account = _linkable_user(db, school_id, data.user_id)
    elif credentials is not None:
        email = str(credentials.email).lower()
        if db.query(User).filter(func.lower(User.email) == email).first():
            raise HTTPException(409, "User with this email already exists")
        account = User(
            school_id=school_id, email=email,
            password_hash=hash_password(credentials.password.get_secret_value()),
            role="teacher", is_active=True,
            staff_identifier=TenantService.generate_staff_id("NE-TID"),
        )

    fields = data.model_dump(exclude={"create_user", "password", "user_id"})
    if fields["email"] is None and account is not None:
        fields["email"] = account.email
    fields["designation"] = fields["designation"] or "Teacher"
    teacher = Teacher(
        school_id=school_id, user=account,
        staff_identifier=(account.staff_identifier if account else None)
        or TenantService.generate_staff_id("NE-TID"),
        **fields,
    )
    _sync_display_fields(teacher)
    db.add(teacher)  # cascades the new User insert in the same transaction
    return _commit(db, teacher)


def update_teacher(db: Session, teacher: Teacher, data: TeacherUpdate) -> Teacher:
    fields = data.model_dump(exclude_unset=True)
    if "user_id" in fields:
        user_id = fields.pop("user_id")
        teacher.user = (
            _linkable_user(db, teacher.school_id, user_id, teacher.id)
            if user_id is not None else None
        )
    for field, value in fields.items():
        setattr(teacher, field, value)
    _sync_display_fields(teacher)
    return _commit(db, teacher)
