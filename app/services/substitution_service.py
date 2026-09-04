from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.tenancy import User
from app.models.academic import TimetableSlot, TeachingAssignment, SchoolClass
from app.models.absence import TeacherAbsence, SubstitutionAssignment

class SubstitutionService:
    @staticmethod
    def record_absence(db: Session, school_id: int, teacher_id: int, abs_date: date, reason: Optional[str] = None) -> TeacherAbsence:
        teacher = db.query(User).filter_by(id=teacher_id, school_id=school_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found in this school")

        absence = TeacherAbsence(
            school_id=school_id,
            teacher_id=teacher_id,
            date=abs_date,
            reason=reason,
            status="reported"
        )
        db.add(absence)
        db.commit()
        db.refresh(absence)
        return absence

    @staticmethod
    def find_candidates_for_slot(db: Session, school_id: int, slot_id: int, abs_date: date) -> List[Dict[str, Any]]:
        slot = db.query(TimetableSlot).filter_by(id=slot_id, school_id=school_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Timetable slot not found")

        absent_teacher_id = slot.teacher_id
        day_of_week = slot.day_of_week
        period = slot.period
        subject_id = slot.subject_id

        # All teachers in school except the absent teacher
        teachers = db.query(User).filter(
            User.school_id == school_id,
            User.role == "teacher",
            User.is_active == True,
            User.id != absent_teacher_id
        ).all()

        # Slot collisions for this period
        busy_teacher_ids = {
            s.teacher_id for s in db.query(TimetableSlot).filter(
                TimetableSlot.school_id == school_id,
                TimetableSlot.day_of_week == day_of_week,
                TimetableSlot.period == period
            ).all()
        }

        # Also busy if already assigned as substitute for this slot
        busy_sub_ids = {
            sub.substitute_teacher_id for sub in db.query(SubstitutionAssignment).join(TimetableSlot).filter(
                SubstitutionAssignment.school_id == school_id,
                TimetableSlot.day_of_week == day_of_week,
                TimetableSlot.period == period
            ).all()
        }
        busy_teacher_ids.update(busy_sub_ids)

        candidates = []
        for teacher in teachers:
            is_free = teacher.id not in busy_teacher_ids

            # Department match check
            teaches_subject = db.query(TeachingAssignment).filter(
                TeachingAssignment.teacher_id == teacher.id,
                TeachingAssignment.subject_id == subject_id
            ).first() is not None

            # Current load count
            load_count = db.query(TeachingAssignment).filter(
                TeachingAssignment.teacher_id == teacher.id
            ).count()

            match_score = 0
            if is_free:
                match_score += 50
            if teaches_subject:
                match_score += 30
            if teacher.is_department_head:
                match_score += 10
            # Lower load bonus
            match_score += max(0, 20 - load_count)

            candidates.append({
                "teacher_id": teacher.id,
                "teacher_name": f"{teacher.first_name} {teacher.last_name}",
                "match_score": match_score,
                "is_same_department": teaches_subject,
                "is_free": is_free,
                "current_load": load_count,
            })

        # Sort descending by match score
        candidates.sort(key=lambda c: c["match_score"], reverse=True)
        return candidates

    @staticmethod
    def assign_substitution(
        db: Session,
        school_id: int,
        absence_id: int,
        substitute_teacher_id: int,
        slot_id: int
    ) -> SubstitutionAssignment:
        absence = db.query(TeacherAbsence).filter_by(id=absence_id, school_id=school_id).first()
        if not absence:
            raise HTTPException(status_code=404, detail="Absence record not found")

        slot = db.query(TimetableSlot).filter_by(id=slot_id, school_id=school_id).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Timetable slot not found")

        sub_teacher = db.query(User).filter_by(id=substitute_teacher_id, school_id=school_id).first()
        if not sub_teacher:
            raise HTTPException(status_code=404, detail="Substitute teacher not found")

        assignment = SubstitutionAssignment(
            school_id=school_id,
            absence_id=absence_id,
            substitute_teacher_id=substitute_teacher_id,
            timetable_slot_id=slot_id,
            confirmed=False
        )
        db.add(assignment)
        absence.status = "covered"
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def confirm_substitution(db: Session, school_id: int, substitution_id: int) -> SubstitutionAssignment:
        sub = db.query(SubstitutionAssignment).filter_by(id=substitution_id, school_id=school_id).first()
        if not sub:
            raise HTTPException(status_code=404, detail="Substitution assignment not found")
        sub.confirmed = True
        db.commit()
        db.refresh(sub)
        return sub
