from typing import List, Dict, Any, Optional
from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException
from app.core.config import settings
from app.models.tenancy import User, PrivateSchool
from app.models.academic import (
    SchoolClass, Subject, TeachingAssignment, TimetableSlot,
    Student, StudentGrade, SubjectAttendance, LiveAttendance
)
from app.models.compliance import DailySubmissionLog, ExamSubmissionEvent, CommunicationLog
from app.models.absence import SubstitutionAssignment

class AcademicService:
    @staticmethod
    def calculate_letter_grade(score: float) -> str:
        if score >= 90:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 50:
            return "D"
        else:
            return "F"

    @staticmethod
    def check_teacher_authority(
        db: Session,
        user: User,
        class_id: int,
        subject_id: Optional[int] = None,
        date_check: Optional[date] = None,
        timetable_slot_id: Optional[int] = None
    ) -> bool:
        if user.role in ["school_manager", "state_admin"]:
            return True
        if user.role != "teacher":
            return False

        # Direct assignment
        query = db.query(TeachingAssignment).filter(
            TeachingAssignment.school_id == user.school_id,
            TeachingAssignment.teacher_id == user.id,
            TeachingAssignment.class_id == class_id
        )
        if subject_id:
            query = query.filter(TeachingAssignment.subject_id == subject_id)
        if query.first():
            return True

        # Substitution coverage check
        if timetable_slot_id:
            sub = db.query(SubstitutionAssignment).filter(
                SubstitutionAssignment.school_id == user.school_id,
                SubstitutionAssignment.substitute_teacher_id == user.id,
                SubstitutionAssignment.timetable_slot_id == timetable_slot_id
            ).first()
            if sub:
                return True

        return False

    @staticmethod
    def mark_subject_attendance(
        db: Session,
        school_id: int,
        user: User,
        class_id: int,
        subject_id: int,
        att_date: date,
        records: List[Dict[str, Any]]
    ) -> List[SubjectAttendance]:
        if not AcademicService.check_teacher_authority(db, user, class_id, subject_id, att_date):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to mark attendance for this class and subject"
            )

        saved_records = []
        for item in records:
            student_id = item["student_id"]
            status = item["status"]

            record = db.query(SubjectAttendance).filter_by(
                student_id=student_id,
                subject_id=subject_id,
                date=att_date
            ).first()

            if record:
                record.status = status
                record.marked_by = user.id
            else:
                record = SubjectAttendance(
                    school_id=school_id,
                    student_id=student_id,
                    subject_id=subject_id,
                    class_id=class_id,
                    date=att_date,
                    status=status,
                    marked_by=user.id
                )
                db.add(record)
            saved_records.append(record)

        db.commit()
        return saved_records

    @staticmethod
    def submit_daily_attendance(db: Session, school_id: int, sub_date: Optional[date] = None) -> DailySubmissionLog:
        tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
        today = sub_date or datetime.now(tz).date()
        now_dt = datetime.now(tz)

        log = db.query(DailySubmissionLog).filter_by(
            school_id=school_id,
            log_date=today
        ).first()

        if log:
            log.attendance_submitted = True
            log.submitted_at = now_dt
            log.alarm_triggered = False
        else:
            log = DailySubmissionLog(
                school_id=school_id,
                log_date=today,
                attendance_submitted=True,
                submitted_at=now_dt,
                alarm_triggered=False
            )
            db.add(log)

        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def enter_grades(
        db: Session,
        school_id: int,
        user: User,
        class_id: int,
        subject_id: int,
        term: str,
        grade_entries: List[Dict[str, Any]]
    ) -> List[StudentGrade]:
        if not AcademicService.check_teacher_authority(db, user, class_id, subject_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to enter grades for this class and subject"
            )

        results = []
        for item in grade_entries:
            student_id = item["student_id"]
            score = float(item["score"])
            calc_grade = item.get("grade") or AcademicService.calculate_letter_grade(score)

            grade_obj = db.query(StudentGrade).filter_by(
                school_id=school_id,
                student_id=student_id,
                subject_id=subject_id,
                term=term
            ).first()

            if grade_obj:
                grade_obj.score = score
                grade_obj.grade = calc_grade
            else:
                grade_obj = StudentGrade(
                    school_id=school_id,
                    student_id=student_id,
                    subject_id=subject_id,
                    term=term,
                    score=score,
                    grade=calc_grade,
                    is_published=False
                )
                db.add(grade_obj)
            results.append(grade_obj)

        db.commit()
        return results

    @staticmethod
    def publish_grades(
        db: Session,
        school_id: int,
        user: User,
        class_id: int,
        subject_id: int,
        term: str
    ) -> int:
        if not AcademicService.check_teacher_authority(db, user, class_id, subject_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to publish grades for this class and subject"
            )

        grades = db.query(StudentGrade).join(Student, Student.id == StudentGrade.student_id).filter(
            StudentGrade.school_id == school_id,
            StudentGrade.subject_id == subject_id,
            StudentGrade.term == term,
            Student.class_id == class_id
        ).all()

        now_dt = datetime.utcnow()
        for g in grades:
            g.is_published = True
            g.published_at = now_dt

        # Log audit event
        event = ExamSubmissionEvent(
            school_id=school_id,
            exam_id=subject_id,
            action="published",
            performed_by=user.id
        )
        db.add(event)
        db.commit()
        return len(grades)
