"""Subject catalog helpers: teacher ownership plus response serialization.

Subject-level ownership lives in ``teacher_subjects``
(:class:`app.models.auth.TeacherSubject`) and is what
:class:`app.services.teacher_scope.TeacherScope` consults when narrowing a
teacher's view of ``/api/v1/subjects``.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.academic import Subject
from app.models.auth import Teacher, TeacherSubject


class SubjectService:
    @staticmethod
    def validate_teachers(db: Session, school_id: int, teacher_ids: Iterable[int]) -> List[int]:
        """Ensure every profile id belongs to the school tenant."""
        unique_ids = sorted({int(tid) for tid in teacher_ids})
        if not unique_ids:
            return []
        found = {
            row[0]
            for row in db.query(Teacher.id)
            .filter(Teacher.id.in_(unique_ids), Teacher.school_id == school_id)
            .all()
        }
        missing = [tid for tid in unique_ids if tid not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Teacher profile(s) {', '.join(str(m) for m in missing)} "
                    "do not exist in this school tenant"
                ),
            )
        return unique_ids

    @staticmethod
    def teacher_map(db: Session, subject_ids: Sequence[int]) -> Dict[int, List[Dict[str, Any]]]:
        """Batch-load ``subject_id -> assigned teacher summaries``."""
        result: Dict[int, List[Dict[str, Any]]] = {sid: [] for sid in subject_ids}
        if not subject_ids:
            return result

        rows = (
            db.query(TeacherSubject, Teacher)
            .join(Teacher, Teacher.id == TeacherSubject.teacher_id)
            .filter(TeacherSubject.subject_id.in_(list(subject_ids)))
            .order_by(TeacherSubject.is_primary.desc(), Teacher.last_name, Teacher.first_name)
            .all()
        )
        for link, teacher in rows:
            result.setdefault(link.subject_id, []).append(
                {
                    "teacher_id": teacher.id,
                    "user_id": teacher.user_id,
                    "full_name": teacher.full_name,
                    "photo_url": teacher.photo_url,
                    "is_primary": bool(link.is_primary),
                }
            )
        return result

    @staticmethod
    def serialize_many(db: Session, subjects: Sequence[Subject]) -> List[Dict[str, Any]]:
        teachers_by_subject = SubjectService.teacher_map(db, [s.id for s in subjects])
        payloads: List[Dict[str, Any]] = []
        for subject in subjects:
            assigned = teachers_by_subject.get(subject.id, [])
            payloads.append(
                {
                    "id": subject.id,
                    "school_id": subject.school_id,
                    "code": subject.code,
                    "name": subject.name,
                    "level": subject.level,
                    "created_at": subject.created_at,
                    "teacher_ids": [entry["teacher_id"] for entry in assigned],
                    "assigned_teachers": assigned,
                }
            )
        return payloads

    @staticmethod
    def serialize(db: Session, subject: Subject) -> Dict[str, Any]:
        return SubjectService.serialize_many(db, [subject])[0]

    @staticmethod
    def set_teachers(
        db: Session,
        subject: Subject,
        teacher_ids: Iterable[int],
        primary_teacher_id: Optional[int] = None,
        commit: bool = True,
    ) -> List[TeacherSubject]:
        """Replace the subject's teacher roster."""
        target_ids = SubjectService.validate_teachers(db, subject.school_id, teacher_ids)
        if primary_teacher_id is not None and primary_teacher_id not in target_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="primary_teacher_id must be part of teacher_ids",
            )

        existing = {
            link.teacher_id: link
            for link in db.query(TeacherSubject)
            .filter(TeacherSubject.subject_id == subject.id)
            .all()
        }
        for teacher_id, link in existing.items():
            if teacher_id not in target_ids:
                db.delete(link)
        for teacher_id in target_ids:
            link = existing.get(teacher_id)
            if link is None:
                link = TeacherSubject(
                    teacher_id=teacher_id, subject_id=subject.id, school_id=subject.school_id
                )
                db.add(link)
            link.is_primary = teacher_id == primary_teacher_id

        if commit:
            db.commit()
        else:
            db.flush()
        return (
            db.query(TeacherSubject)
            .filter(TeacherSubject.subject_id == subject.id)
            .order_by(TeacherSubject.teacher_id)
            .all()
        )

    @staticmethod
    def add_teacher(
        db: Session, subject: Subject, teacher_id: int, is_primary: bool = False, commit: bool = True
    ) -> TeacherSubject:
        SubjectService.validate_teachers(db, subject.school_id, [teacher_id])
        link = (
            db.query(TeacherSubject)
            .filter(
                TeacherSubject.subject_id == subject.id,
                TeacherSubject.teacher_id == teacher_id,
            )
            .first()
        )
        if link is None:
            link = TeacherSubject(
                teacher_id=teacher_id,
                subject_id=subject.id,
                school_id=subject.school_id,
                is_primary=is_primary,
            )
            db.add(link)
        elif is_primary:
            link.is_primary = True
        if commit:
            db.commit()
            db.refresh(link)
        else:
            db.flush()
        return link

    @staticmethod
    def remove_teacher(db: Session, subject: Subject, teacher_id: int, commit: bool = True) -> None:
        deleted = (
            db.query(TeacherSubject)
            .filter(
                TeacherSubject.subject_id == subject.id,
                TeacherSubject.teacher_id == teacher_id,
            )
            .delete(synchronize_session=False)
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher profile {teacher_id} is not assigned to this subject",
            )
        if commit:
            db.commit()
