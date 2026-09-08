"""Classroom serialization for ``/api/v1/classrooms``.

Roster counts and the teaching staff of each classroom are loaded with two
grouped queries regardless of how many classrooms are returned, so a
teacher-scoped list stays cheap.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Student, TeachingAssignment


class ClassroomService:
    @staticmethod
    def serialize_many(db: Session, school_id: int, classes: Sequence[SchoolClass]) -> List[Dict[str, Any]]:
        if not classes:
            return []
        class_ids = [c.id for c in classes]

        roster: Dict[int, Dict[str, int]] = {cid: {"total": 0, "male": 0, "female": 0} for cid in class_ids}
        for class_id, gender, count in (
            db.query(Student.class_id, Student.gender, func.count(Student.id))
            .filter(
                Student.school_id == school_id,
                Student.is_active.is_(True),
                Student.class_id.in_(class_ids),
            )
            .group_by(Student.class_id, Student.gender)
            .all()
        ):
            bucket = roster.setdefault(class_id, {"total": 0, "male": 0, "female": 0})
            bucket["total"] += count
            normalized = (gender or "").strip().lower()
            if normalized.startswith("m"):
                bucket["male"] += count
            elif normalized.startswith("f"):
                bucket["female"] += count

        staff: Dict[int, List[int]] = {cid: [] for cid in class_ids}
        subjects: Dict[int, List[int]] = {cid: [] for cid in class_ids}
        for class_id, teacher_id, subject_id in (
            db.query(
                TeachingAssignment.class_id,
                TeachingAssignment.teacher_id,
                TeachingAssignment.subject_id,
            )
            .filter(
                TeachingAssignment.school_id == school_id,
                TeachingAssignment.class_id.in_(class_ids),
            )
            .order_by(TeachingAssignment.class_id, TeachingAssignment.teacher_id)
            .all()
        ):
            if teacher_id is not None and teacher_id not in staff.setdefault(class_id, []):
                staff[class_id].append(teacher_id)
            if subject_id is not None and subject_id not in subjects.setdefault(class_id, []):
                subjects[class_id].append(subject_id)

        payloads: List[Dict[str, Any]] = []
        for school_class in classes:
            counts = roster.get(school_class.id, {"total": 0, "male": 0, "female": 0})
            payloads.append(
                {
                    "id": school_class.id,
                    "school_id": school_class.school_id,
                    "class_level": school_class.class_level,
                    "stream": school_class.stream,
                    "academic_year_id": school_class.academic_year_id,
                    "label": school_class.label,
                    "created_at": school_class.created_at,
                    "student_count": counts["total"],
                    "male_students": counts["male"],
                    "female_students": counts["female"],
                    "teacher_ids": staff.get(school_class.id, []),
                    "subject_ids": subjects.get(school_class.id, []),
                }
            )
        return payloads

    @staticmethod
    def serialize(db: Session, school_id: int, school_class: SchoolClass) -> Dict[str, Any]:
        return ClassroomService.serialize_many(db, school_id, [school_class])[0]
