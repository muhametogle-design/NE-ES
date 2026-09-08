"""Teacher staff-profile provisioning, account binding and serialization.

A *staff profile* (:class:`app.models.auth.Teacher`) is the human-resources
record; a *user account* (:class:`app.models.tenancy.User` with
``role="teacher"``) is the login. ``teachers.user_id`` binds the two:

* creating a profile can **auto-provision** the account in the same call
  (``TeacherCreate.auto_provision_user`` — the default);
* an existing teacher account can be **linked manually**
  (``TeacherCreate.link_user_id`` / ``POST /api/v1/teachers/{id}/link-user``);
* a profile may be created first and linked later (``user_id`` NULL).

Portraits are mirrored between ``teachers.photo_url`` and ``users.photo_url``
(:meth:`TeacherService.sync_photo`) so the legacy account endpoints
(``/api/v1/school/teachers``) and the profile endpoints
(``/api/v1/teachers``) always serve the same image.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_pin
from app.models.academic import Subject, TeachingAssignment
from app.models.auth import Teacher, TeacherSubject
from app.models.tenancy import PrivateSchool, User
from app.schemas.teacher import (
    TeacherCreate, TeacherUpdate, TeacherUserProvision,
)
from app.services.tenant_service import TenantService

#: Fields a staff profile owns outright (mirrored from/to the bound account).
PROFILE_FIELDS = (
    "first_name",
    "last_name",
    "phone",
    "qualifications",
    "designation",
    "bio",
    "is_department_head",
    "photo_url",
)
#: Fields a teacher may change on their own profile (self-service).
SELF_SERVICE_FIELDS = ("photo_url", "phone", "bio")

#: Sentinel separating "photo_url not supplied" from "photo_url explicitly null".
_UNSET: Any = object()


class TeacherService:
    #: Writable on a staff profile by a school manager.
    PROFILE_FIELDS = PROFILE_FIELDS + ("is_active", "staff_identifier", "email")
    #: Writable by the teacher on their own profile / account.
    SELF_SERVICE_FIELDS = SELF_SERVICE_FIELDS
    #: Writable on a legacy teacher *account* (``users`` row) by a manager.
    ACCOUNT_FIELDS = (
        "first_name",
        "last_name",
        "phone",
        "qualifications",
        "designation",
        "bio",
        "is_department_head",
        "is_active",
        "photo_url",
    )

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------
    @staticmethod
    def provision_account(
        db: Session,
        *,
        school_id: int,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        qualifications: Optional[str] = None,
        designation: Optional[str] = None,
        bio: Optional[str] = None,
        is_department_head: bool = False,
        photo_url: Optional[str] = None,
        staff_pin: Optional[str] = None,
    ) -> User:
        """Create a ``role="teacher"`` login for the given school tenant."""
        normalized_email = (email or "").strip().lower()
        if db.query(User).filter(User.email == normalized_email).first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user account with email '{normalized_email}' already exists",
            )

        account = User(
            school_id=school_id,
            email=normalized_email,
            password_hash=hash_password(password),
            role="teacher",
            first_name=first_name,
            last_name=last_name,
            staff_identifier=TenantService.generate_staff_id("NE-TID"),
            phone=phone,
            qualifications=qualifications,
            designation=designation or "Teacher",
            bio=bio,
            photo_url=photo_url,
            is_department_head=is_department_head,
            staff_pin_hash=hash_pin(staff_pin) if staff_pin else None,
            is_active=True,
        )
        db.add(account)
        db.flush()
        return account

    @staticmethod
    def account_from_provision(
        db: Session, school_id: int, provision: TeacherUserProvision, fallback: Dict[str, Any]
    ) -> User:
        return TeacherService.provision_account(
            db,
            school_id=school_id,
            email=str(provision.email),
            password=provision.password,
            first_name=provision.first_name or fallback.get("first_name"),
            last_name=provision.last_name or fallback.get("last_name"),
            phone=fallback.get("phone"),
            qualifications=fallback.get("qualifications"),
            designation=fallback.get("designation"),
            bio=fallback.get("bio"),
            is_department_head=bool(fallback.get("is_department_head", False)),
            photo_url=fallback.get("photo_url"),
            staff_pin=provision.staff_pin,
        )

    @staticmethod
    def resolve_linkable_account(db: Session, school_id: int, user_id: int) -> User:
        """Fetch an existing teacher account that can be bound to a profile."""
        account = (
            db.query(User)
            .filter(User.id == user_id, User.school_id == school_id)
            .first()
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User account {user_id} not found in this school",
            )
        if account.role != "teacher":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"User account {user_id} has role '{account.role}'; "
                    "only teacher accounts can be bound to a staff profile"
                ),
            )
        existing = db.query(Teacher).filter(Teacher.user_id == account.id).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"User account {account.id} is already bound to staff profile {existing.id}"
                ),
            )
        return account

    # ------------------------------------------------------------------
    # Profiles
    # ------------------------------------------------------------------
    @staticmethod
    def resolve_school_id(db: Session, caller: User, requested: Optional[int]) -> int:
        if caller.school_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller is not attached to a school tenant",
            )
        if requested is not None and requested != caller.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot manage staff profiles of another school tenant",
            )
        if db.query(PrivateSchool).filter(PrivateSchool.id == caller.school_id).first() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="School not found"
            )
        return caller.school_id

    @staticmethod
    def create_profile(
        db: Session, *, caller: User, payload: TeacherCreate, commit: bool = True
    ) -> Teacher:
        """Create a staff profile, provisioning or linking its login account."""
        school_id = TeacherService.resolve_school_id(db, caller, payload.school_id)

        account: Optional[User] = None
        if payload.link_user_id is not None:
            account = TeacherService.resolve_linkable_account(db, school_id, payload.link_user_id)
        elif payload.auto_provision_user:
            fallback = {
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "phone": payload.phone,
                "qualifications": payload.qualifications,
                "designation": payload.designation,
                "bio": payload.bio,
                "is_department_head": payload.is_department_head,
                "photo_url": payload.photo_url,
            }
            if payload.user is not None:
                account = TeacherService.account_from_provision(db, school_id, payload.user, fallback)
            else:
                account = TeacherService.provision_account(
                    db,
                    school_id=school_id,
                    email=str(payload.email),
                    password=payload.password or "",
                    **fallback,
                )

        email = None
        if account is not None:
            email = account.email
        elif payload.email is not None:
            email = str(payload.email).strip().lower()

        if email:
            duplicate = (
                db.query(Teacher)
                .filter(Teacher.school_id == school_id, Teacher.email == email)
                .first()
            )
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A staff profile with email '{email}' already exists in this school",
                )

        profile = Teacher(
            school_id=school_id,
            user_id=account.id if account is not None else None,
            staff_identifier=(payload.staff_identifier or (account.staff_identifier if account else None)),
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=email,
            phone=payload.phone or (account.phone if account else None),
            designation=payload.designation or (account.designation if account else None),
            qualifications=payload.qualifications or (account.qualifications if account else None),
            bio=payload.bio if payload.bio is not None else (account.bio if account else None),
            photo_url=payload.photo_url if payload.photo_url is not None else (account.photo_url if account else None),
            is_department_head=payload.is_department_head or bool(account.is_department_head if account else False),
            is_active=True,
        )
        db.add(profile)
        db.flush()

        if payload.subject_ids:
            TeacherService.set_subjects(db, profile, payload.subject_ids, commit=False)

        if commit:
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def ensure_profile_for_user(db: Session, user: User, commit: bool = True) -> Teacher:
        """Auto-link: return (creating if needed) the profile bound to ``user``."""
        if user.role != "teacher":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User account {user.id} has role '{user.role}', not 'teacher'",
            )
        if user.school_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User account {user.id} is not attached to a school tenant",
            )

        existing = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if existing is not None:
            return existing

        profile = Teacher(
            school_id=user.school_id,
            user_id=user.id,
            staff_identifier=user.staff_identifier,
            first_name=user.first_name or "Unknown",
            last_name=user.last_name or "",
            email=user.email,
            phone=user.phone,
            designation=user.designation,
            qualifications=user.qualifications,
            bio=user.bio,
            photo_url=user.photo_url,
            is_department_head=bool(user.is_department_head),
            is_active=bool(user.is_active),
        )
        db.add(profile)
        if commit:
            db.commit()
            db.refresh(profile)
        else:
            db.flush()
        return profile

    @staticmethod
    def link_user(db: Session, profile: Teacher, user_id: int, commit: bool = True) -> Teacher:
        """Manually bind a profile to an existing teacher account."""
        account = TeacherService.resolve_linkable_account(db, profile.school_id, user_id)
        profile.user_id = account.id
        profile.email = account.email
        if not profile.staff_identifier:
            profile.staff_identifier = account.staff_identifier
        TeacherService.sync_photo(db, profile=profile, user=account)
        if commit:
            db.commit()
            db.refresh(profile)
        return profile

    @staticmethod
    def update_profile(
        db: Session,
        profile: Teacher,
        payload: TeacherUpdate,
        *,
        self_service: bool = False,
        commit: bool = True,
    ) -> Teacher:
        """Apply a partial update; ``self_service`` limits writable fields."""
        data = payload.model_dump(exclude_unset=True)
        subject_ids = data.pop("subject_ids", None)
        new_user_id = data.pop("user_id", None)

        allowed = (
            TeacherService.SELF_SERVICE_FIELDS if self_service else TeacherService.PROFILE_FIELDS
        )
        for field, value in data.items():
            if field not in allowed:
                if self_service:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "Teachers may only update their own photo, phone and bio; "
                            f"field '{field}' requires a school manager"
                        ),
                    )
                continue
            setattr(profile, field, value)

        if new_user_id is not None and not self_service:
            if new_user_id != profile.user_id:
                TeacherService.link_user(db, profile, new_user_id, commit=False)

        if "photo_url" in data:
            # Explicit value (possibly None) — mirror it onto the bound account.
            TeacherService.sync_photo(db, profile=profile, photo_url=data["photo_url"])
        else:
            TeacherService.sync_photo(db, profile=profile)

        if subject_ids is not None and not self_service:
            TeacherService.set_subjects(db, profile, subject_ids, commit=False)

        if commit:
            db.commit()
            db.refresh(profile)
        return profile

    # ------------------------------------------------------------------
    # Subject-level assignment
    # ------------------------------------------------------------------
    @staticmethod
    def validate_subjects(db: Session, school_id: int, subject_ids: Iterable[int]) -> List[int]:
        unique_ids = sorted({int(sid) for sid in subject_ids})
        if not unique_ids:
            return []
        found = {
            row[0]
            for row in db.query(Subject.id)
            .filter(Subject.id.in_(unique_ids), Subject.school_id == school_id)
            .all()
        }
        missing = [sid for sid in unique_ids if sid not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Subject(s) {', '.join(str(m) for m in missing)} "
                    "do not exist in this school tenant"
                ),
            )
        return unique_ids

    @staticmethod
    def set_subjects(
        db: Session,
        profile: Teacher,
        subject_ids: Iterable[int],
        primary_subject_id: Optional[int] = None,
        commit: bool = True,
    ) -> List[TeacherSubject]:
        """Replace the profile's subject mappings with ``subject_ids``."""
        target_ids = TeacherService.validate_subjects(db, profile.school_id, subject_ids)
        if primary_subject_id is not None and primary_subject_id not in target_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_subject_id must be part of subject_ids",
            )

        existing = {
            link.subject_id: link
            for link in db.query(TeacherSubject)
            .filter(TeacherSubject.teacher_id == profile.id)
            .all()
        }
        for subject_id, link in existing.items():
            if subject_id not in target_ids:
                db.delete(link)
        for subject_id in target_ids:
            link = existing.get(subject_id)
            if link is None:
                link = TeacherSubject(
                    teacher_id=profile.id, subject_id=subject_id, school_id=profile.school_id
                )
                db.add(link)
            link.is_primary = subject_id == primary_subject_id

        if commit:
            db.commit()
        else:
            db.flush()
        return [
            link
            for link in db.query(TeacherSubject)
            .filter(TeacherSubject.teacher_id == profile.id)
            .order_by(TeacherSubject.subject_id)
            .all()
        ]

    @staticmethod
    def add_subject(
        db: Session, profile: Teacher, subject_id: int, is_primary: bool = False, commit: bool = True
    ) -> TeacherSubject:
        TeacherService.validate_subjects(db, profile.school_id, [subject_id])
        link = (
            db.query(TeacherSubject)
            .filter(
                TeacherSubject.teacher_id == profile.id,
                TeacherSubject.subject_id == subject_id,
            )
            .first()
        )
        if link is None:
            link = TeacherSubject(
                teacher_id=profile.id,
                subject_id=subject_id,
                school_id=profile.school_id,
                is_primary=is_primary,
            )
            db.add(link)
        else:
            link.is_primary = is_primary or link.is_primary
        if commit:
            db.commit()
            db.refresh(link)
        else:
            db.flush()
        return link

    @staticmethod
    def remove_subject(db: Session, profile: Teacher, subject_id: int, commit: bool = True) -> None:
        deleted = (
            db.query(TeacherSubject)
            .filter(
                TeacherSubject.teacher_id == profile.id,
                TeacherSubject.subject_id == subject_id,
            )
            .delete(synchronize_session=False)
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject {subject_id} is not assigned to this teacher",
            )
        if commit:
            db.commit()

    # ------------------------------------------------------------------
    # Photo mirroring
    # ------------------------------------------------------------------
    @staticmethod
    def sync_photo(
        db: Session,
        profile: Optional[Teacher] = None,
        user: Optional[User] = None,
        photo_url: Any = _UNSET,
    ) -> Optional[str]:
        """Keep ``teachers.photo_url`` and ``users.photo_url`` identical.

        Callers pass whichever side they just wrote plus, when the value is
        known, ``photo_url`` (``None`` clears both sides). When it is left as
        the sentinel the surviving value of either side wins, which is what
        binding an existing account to a profile needs.
        """
        if profile is None and user is not None:
            profile = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if user is None and profile is not None and profile.user_id is not None:
            user = db.query(User).filter(User.id == profile.user_id).first()

        if photo_url is _UNSET:
            effective = None
            if profile is not None and profile.photo_url:
                effective = profile.photo_url
            elif user is not None and user.photo_url:
                effective = user.photo_url
        else:
            effective = photo_url

        if profile is not None:
            profile.photo_url = effective
        if user is not None:
            user.photo_url = effective
        return effective

    # ------------------------------------------------------------------
    # Backfill / demo data
    # ------------------------------------------------------------------
    @staticmethod
    def sync_profiles_from_accounts(
        db: Session, school_id: Optional[int] = None, commit: bool = True
    ) -> Dict[str, int]:
        """Backfill staff profiles and subject mappings from teacher accounts.

        Idempotent, and safe to re-run after a migration: every ``role="teacher"``
        account gets a bound profile (``teachers.user_id``) and a
        ``teacher_subjects`` row for each subject it already teaches through
        ``teaching_assignments``. Teachers provisioned before subject-level
        scoping existed therefore keep working instead of seeing an empty
        ``/api/v1/subjects``.
        """
        query = db.query(User).filter(User.role == "teacher")
        if school_id is not None:
            query = query.filter(User.school_id == school_id)
        accounts = query.order_by(User.id).all()

        created_profiles = 0
        created_links = 0
        for account in accounts:
            if account.school_id is None:
                continue

            existed = db.query(Teacher).filter(Teacher.user_id == account.id).first()
            profile = TeacherService.ensure_profile_for_user(db, account, commit=False)
            if existed is None:
                created_profiles += 1

            subject_ids = {
                row[0]
                for row in db.query(TeachingAssignment.subject_id)
                .filter(
                    TeachingAssignment.school_id == account.school_id,
                    TeachingAssignment.teacher_id == account.id,
                )
                .distinct()
                .all()
                if row[0] is not None
            }
            if not subject_ids:
                continue
            already = {
                row[0]
                for row in db.query(TeacherSubject.subject_id)
                .filter(TeacherSubject.teacher_id == profile.id)
                .all()
            }
            for subject_id in sorted(subject_ids - already):
                db.add(
                    TeacherSubject(
                        teacher_id=profile.id,
                        subject_id=subject_id,
                        school_id=profile.school_id,
                    )
                )
                created_links += 1

        if commit:
            db.commit()
        return {
            "profiles_created": created_profiles,
            "subject_links_created": created_links,
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    @staticmethod
    def serialize_many(db: Session, profiles: Sequence[Teacher]) -> List[Dict[str, Any]]:
        """Build ``TeacherResponse`` payloads with batched lookups (no N+1)."""
        if not profiles:
            return []

        profile_ids = [p.id for p in profiles]
        user_ids = sorted({p.user_id for p in profiles if p.user_id is not None})

        links = (
            db.query(TeacherSubject, Subject)
            .join(Subject, Subject.id == TeacherSubject.subject_id)
            .filter(TeacherSubject.teacher_id.in_(profile_ids))
            .order_by(TeacherSubject.subject_id)
            .all()
        )
        subjects_by_profile: Dict[int, List[Dict[str, Any]]] = {pid: [] for pid in profile_ids}
        for link, subject in links:
            subjects_by_profile.setdefault(link.teacher_id, []).append(
                {
                    "id": subject.id,
                    "code": subject.code,
                    "name": subject.name,
                    "level": subject.level,
                    "is_primary": bool(link.is_primary),
                }
            )

        classes_by_user: Dict[int, List[int]] = {}
        accounts: Dict[int, User] = {}
        if user_ids:
            for teacher_id, class_id in (
                db.query(TeachingAssignment.teacher_id, TeachingAssignment.class_id)
                .filter(TeachingAssignment.teacher_id.in_(user_ids))
                .order_by(TeachingAssignment.class_id)
                .all()
            ):
                bucket = classes_by_user.setdefault(teacher_id, [])
                if class_id not in bucket:
                    bucket.append(class_id)
            accounts = {
                account.id: account
                for account in db.query(User).filter(User.id.in_(user_ids)).all()
            }

        payloads: List[Dict[str, Any]] = []
        for profile in profiles:
            assigned_subjects = subjects_by_profile.get(profile.id, [])
            account = accounts.get(profile.user_id) if profile.user_id is not None else None
            payloads.append(
                {
                    "id": profile.id,
                    "school_id": profile.school_id,
                    "user_id": profile.user_id,
                    "staff_identifier": profile.staff_identifier,
                    "email": profile.email or (account.email if account else None),
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "full_name": profile.full_name,
                    "phone": profile.phone,
                    "qualifications": profile.qualifications,
                    "designation": profile.designation,
                    "bio": profile.bio,
                    "photo_url": profile.photo_url or (account.photo_url if account else None),
                    "is_department_head": bool(profile.is_department_head),
                    "is_active": bool(profile.is_active),
                    "subject_ids": [entry["id"] for entry in assigned_subjects],
                    "assigned_subjects": assigned_subjects,
                    "class_ids": classes_by_user.get(profile.user_id, []) if profile.user_id else [],
                    "account": (
                        {
                            "id": account.id,
                            "email": account.email,
                            "role": account.role,
                            "staff_identifier": account.staff_identifier,
                            "is_active": bool(account.is_active),
                            "photo_url": account.photo_url,
                        }
                        if account
                        else None
                    ),
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at,
                }
            )
        return payloads

    @staticmethod
    def serialize(db: Session, profile: Teacher) -> Dict[str, Any]:
        return TeacherService.serialize_many(db, [profile])[0]

    @staticmethod
    def account_payload(user: User) -> Dict[str, Any]:
        """``TeacherAccountResponse`` payload for a ``role="teacher"`` user.

        Uses the ``user.teacher_profile`` relationship; callers rendering a list
        should ``joinedload(User.teacher_profile)`` to avoid one query per row.
        """
        profile = user.teacher_profile
        return {
            "id": user.id,
            "school_id": user.school_id,
            "user_id": user.id,
            "teacher_profile_id": profile.id if profile else None,
            "email": user.email,
            "role": user.role,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "staff_identifier": user.staff_identifier,
            "phone": user.phone,
            "qualifications": user.qualifications,
            "designation": user.designation,
            "bio": user.bio,
            "is_department_head": bool(user.is_department_head),
            "is_active": bool(user.is_active),
            "photo_url": user.photo_url or (profile.photo_url if profile else None),
            "created_at": user.created_at,
        }
