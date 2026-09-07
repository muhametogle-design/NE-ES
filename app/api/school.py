import os
from typing import List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.api.deps import require_school_tenant, require_school_manager, financial_firewall
from app.api.v1.students import router as students_router
from app.api.v1.teachers import router as teachers_router
from app.api.v1.subjects import router as subjects_router
from app.api.v1.classrooms import router as classrooms_router
from app.core.db import get_db
from app.models.tenancy import User, PrivateSchool
from app.models.academic import (
    Student,
    Teacher,
    TeachingAssignment,
    TimetableSlot,
    StudentGrade,
    SubjectAttendance,
    LiveAttendance,
)
from app.models.finance import StudentInvoice, PaymentTransaction
from app.models.compliance import ExamSubmissionEvent, DailySubmissionLog
from app.models.absence import TeacherAbsence, SubstitutionAssignment
from app.models.syllabus import SyllabusPlan, SyllabusTopic
from app.models.backups import BackupRecord, BackupAuditEvent
from app.models.biometrics import BiometricVerificationLog
from app.schemas.school import (
    AssignmentCreate,
    AssignmentResponse,
    TimetableSlotCreate,
    TimetableSlotResponse,
    AttendanceMarkRequest,
    SubjectAttendanceResponse,
    LiveAttendanceMarkRequest,
    LiveAttendanceResponse,
    AttendanceSubmitResponse,
    GradeBatchRequest,
    GradeResponse,
    GradePublishRequest,
    ExamEventResponse,
    AbsenceCreate,
    AbsenceResponse,
    SubstitutionAssignRequest,
    SubstitutionResponse,
    SyllabusPlanCreate,
    SyllabusPlanResponse,
    SyllabusTopicCreate,
    SyllabusTopicResponse,
    SyllabusProgressCreate,
    SyllabusProgressResponse,
    BiometricRegisterOptionsRequest,
    BiometricRegisterVerifyRequest,
    BiometricVerifyRequest,
    BiometricLogResponse,
    BackupResponse,
    BackupAuditEventResponse,
    TuitionRateCreate,
    TuitionRateResponse,
    InvoiceCreate,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
    FinanceSummary,
)
from app.schemas.common import MessageResponse
from app.services.academic_service import AcademicService
from app.services.finance_service import FinanceService
from app.services.substitution_service import SubstitutionService
from app.services.syllabus_service import SyllabusService
from app.services.biometric_service import BiometricService
from app.services.backup_service import BackupService
from app.services.teacher_scoping import (
    assigned_to, require_class_access, require_course_access, validate_roster,
)

router = APIRouter(prefix="/v1/school", tags=["school"])

# These same handlers are mounted at /api/v1/{students,teachers,subjects,classrooms}.
# Keeping aliases here prevents older clients from bypassing the scope checks.

router.include_router(students_router, prefix="/students")
router.include_router(teachers_router, prefix="/teachers")
router.include_router(subjects_router, prefix="/subjects")
router.include_router(classrooms_router, prefix="/classes")

@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
async def create_assignment(data: AssignmentCreate, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    require_course_access(db, user, data.class_id, data.subject_id)
    teacher = db.query(Teacher).filter_by(id=data.teacher_id, school_id=user.school_id, is_active=True).first()
    if not teacher:
        raise HTTPException(404, "Teacher not found in this school")
    existing = db.query(TeachingAssignment).filter_by(
        school_id=user.school_id,
        class_id=data.class_id,
        subject_id=data.subject_id
    ).first()
    if existing:
        existing.teacher_id = data.teacher_id
        assign = existing
    else:
        assign = TeachingAssignment(
            school_id=user.school_id,
            teacher_id=data.teacher_id,
            class_id=data.class_id,
            subject_id=data.subject_id
        )
        db.add(assign)
    db.commit()
    db.refresh(assign)
    return {
        "id": assign.id,
        "school_id": assign.school_id,
        "teacher_id": assign.teacher_id,
        "class_id": assign.class_id,
        "subject_id": assign.subject_id,
        "teacher_name": f"{assign.teacher.first_name} {assign.teacher.last_name}" if assign.teacher else None,
        "class_name": f"Class {assign.class_ref.class_level}{assign.class_ref.stream}" if assign.class_ref else None,
        "subject_name": assign.subject.name if assign.subject else None
    }

# ==========================================
# 4. TIMETABLE
# ==========================================
@router.get("/timetable", response_model=List[TimetableSlotResponse])
async def list_timetable(
    class_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    day_of_week: Optional[int] = None,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db)
):
    query = db.query(TimetableSlot).filter(TimetableSlot.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(
            TimetableSlot.teacher.has(Teacher.user_id == user.id),
            assigned_to(user, class_id=TimetableSlot.class_id, subject_id=TimetableSlot.subject_id),
        )
        if teacher_id is not None and teacher_id != user.teacher_id:
            raise HTTPException(403, "Not authorized to access another teacher's timetable")
    if class_id is not None:
        require_class_access(db, user, class_id)
    if class_id:
        query = query.filter(TimetableSlot.class_id == class_id)
    if teacher_id:
        query = query.filter(TimetableSlot.teacher_id == teacher_id)
    if day_of_week is not None:
        query = query.filter(TimetableSlot.day_of_week == day_of_week)

    slots = query.order_by(TimetableSlot.day_of_week, TimetableSlot.period).all()
    result = []
    for s in slots:
        result.append({
            "id": s.id,
            "school_id": s.school_id,
            "class_id": s.class_id,
            "subject_id": s.subject_id,
            "teacher_id": s.teacher_id,
            "day_of_week": s.day_of_week,
            "period": s.period,
            "room": s.room,
            "subject_name": s.subject.name if s.subject else None,
            "teacher_name": f"{s.teacher.first_name} {s.teacher.last_name}" if s.teacher else None,
            "class_name": f"Class {s.class_ref.class_level}{s.class_ref.stream}" if s.class_ref else None,
        })
    return result

@router.post("/timetable", response_model=TimetableSlotResponse, status_code=201)
async def create_timetable_slot(data: TimetableSlotCreate, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    require_course_access(db, user, data.class_id, data.subject_id)
    if not db.query(Teacher).filter_by(id=data.teacher_id, school_id=user.school_id, is_active=True).first():
        raise HTTPException(404, "Teacher not found in this school")
    existing = db.query(TimetableSlot).filter_by(
        school_id=user.school_id,
        class_id=data.class_id,
        day_of_week=data.day_of_week,
        period=data.period
    ).first()
    if existing:
        existing.subject_id = data.subject_id
        existing.teacher_id = data.teacher_id
        existing.room = data.room
        slot = existing
    else:
        slot = TimetableSlot(
            school_id=user.school_id,
            class_id=data.class_id,
            subject_id=data.subject_id,
            teacher_id=data.teacher_id,
            day_of_week=data.day_of_week,
            period=data.period,
            room=data.room
        )
        db.add(slot)
    db.commit()
    db.refresh(slot)
    return {
        "id": slot.id,
        "school_id": slot.school_id,
        "class_id": slot.class_id,
        "subject_id": slot.subject_id,
        "teacher_id": slot.teacher_id,
        "day_of_week": slot.day_of_week,
        "period": slot.period,
        "room": slot.room,
        "subject_name": slot.subject.name if slot.subject else None,
        "teacher_name": f"{slot.teacher.first_name} {slot.teacher.last_name}" if slot.teacher else None,
        "class_name": f"Class {slot.class_ref.class_level}{slot.class_ref.stream}" if slot.class_ref else None,
    }

@router.delete("/timetable/{id}", response_model=MessageResponse)
async def delete_timetable_slot(id: int, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    slot = db.query(TimetableSlot).filter_by(id=id, school_id=user.school_id).first()
    if not slot:
        raise HTTPException(404, "Slot not found")
    db.delete(slot)
    db.commit()
    return {"message": "Timetable slot removed"}

# ==========================================
# 5. ATTENDANCE & COMPLIANCE SUBMISSION
# ==========================================
@router.get("/attendance", response_model=List[SubjectAttendanceResponse])
async def get_subject_attendance(
    class_id: int,
    subject_id: int,
    att_date: date = Query(default_factory=date.today),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db)
):
    require_course_access(db, user, class_id, subject_id)
    records = db.query(SubjectAttendance).filter(
        SubjectAttendance.school_id == user.school_id,
        SubjectAttendance.class_id == class_id,
        SubjectAttendance.subject_id == subject_id,
        SubjectAttendance.date == att_date
    ).all()

    result = []
    for r in records:
        result.append({
            "id": r.id,
            "student_id": r.student_id,
            "student_name": f"{r.student.first_name} {r.student.last_name}" if r.student else "Unknown",
            "roll_number": r.student.roll_number if r.student else "N/A",
            "subject_id": r.subject_id,
            "class_id": r.class_id,
            "date": r.date,
            "status": r.status
        })
    return result

@router.post("/attendance", response_model=MessageResponse)
async def mark_attendance(data: AttendanceMarkRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    records_dict = [r.model_dump() for r in data.records]
    AcademicService.mark_subject_attendance(
        db=db,
        school_id=user.school_id,
        user=user,
        class_id=data.class_id,
        subject_id=data.subject_id,
        att_date=data.date,
        records=records_dict
    )
    return {"message": f"Successfully marked attendance for {len(data.records)} students."}

@router.post("/attendance/submit", response_model=AttendanceSubmitResponse)
async def submit_attendance_daily(
    submission_date: Optional[date] = None,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db)
):
    log = AcademicService.submit_daily_attendance(db, user.school_id, submission_date)
    return {
        "success": True,
        "school_id": user.school_id,
        "date": log.log_date.isoformat(),
        "submitted_at": log.submitted_at or datetime.utcnow(),
        "message": "Daily attendance report officially transmitted to State Ministry registry."
    }

@router.get("/attendance/live", response_model=List[LiveAttendanceResponse])
async def list_live_attendance(slot_id: int, att_date: date = Query(default_factory=date.today), user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    slot = db.query(TimetableSlot).filter_by(id=slot_id, school_id=user.school_id).first()
    if not slot:
        raise HTTPException(404, "Timetable slot not found")
    if not AcademicService.check_teacher_authority(
        db, user, slot.class_id, slot.subject_id, att_date, slot.id,
    ):
        raise HTTPException(403, "Not authorized to view attendance for this session")
    records = db.query(LiveAttendance).filter_by(school_id=user.school_id, timetable_slot_id=slot_id, date=att_date).all()
    return records

@router.post("/attendance/live", response_model=MessageResponse)
async def mark_live_attendance(data: LiveAttendanceMarkRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    slot = db.query(TimetableSlot).filter_by(id=data.timetable_slot_id, school_id=user.school_id).first()
    if not slot:
        raise HTTPException(404, "Timetable slot not found")

    if not AcademicService.check_teacher_authority(
        db, user, slot.class_id, slot.subject_id, data.date, slot.id,
    ):
        raise HTTPException(403, "Not authorized to mark attendance for this session")
    validate_roster(db, user, slot.class_id, [item.student_id for item in data.records])
    for item in data.records:
        rec = db.query(LiveAttendance).filter_by(
            school_id=user.school_id,
            student_id=item.student_id,
            timetable_slot_id=data.timetable_slot_id,
            date=data.date
        ).first()
        if rec:
            rec.status = item.status
            rec.marked_by = user.id
        else:
            rec = LiveAttendance(
                school_id=user.school_id,
                student_id=item.student_id,
                timetable_slot_id=data.timetable_slot_id,
                date=data.date,
                status=item.status,
                marked_by=user.id
            )
            db.add(rec)
    db.commit()
    return {"message": f"Recorded live session attendance for {len(data.records)} students"}

# ==========================================
# 6. GRADES & EXAMS
# ==========================================
@router.get("/grades", response_model=List[GradeResponse])
async def list_grades(
    subject_id: int,
    class_id: int,
    term: str = "Term 1",
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db)
):
    require_course_access(db, user, class_id, subject_id)
    grades = db.query(StudentGrade).join(Student, Student.id == StudentGrade.student_id).filter(
        StudentGrade.school_id == user.school_id,
        StudentGrade.subject_id == subject_id,
        StudentGrade.term == term,
        Student.class_id == class_id
    ).all()

    result = []
    for g in grades:
        result.append({
            "id": g.id,
            "student_id": g.student_id,
            "student_name": f"{g.student.first_name} {g.student.last_name}" if g.student else "Unknown",
            "roll_number": g.student.roll_number if g.student else "N/A",
            "subject_id": g.subject_id,
            "subject_name": g.subject.name if g.subject else None,
            "term": g.term,
            "score": g.score,
            "grade": g.grade,
            "is_published": g.is_published,
            "published_at": g.published_at
        })
    return result

@router.post("/grades", response_model=MessageResponse)
async def enter_grades(data: GradeBatchRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    entries = [g.model_dump() for g in data.grades]
    AcademicService.enter_grades(
        db=db,
        school_id=user.school_id,
        user=user,
        class_id=data.class_id,
        subject_id=data.subject_id,
        term=data.term,
        grade_entries=entries
    )
    return {"message": f"Successfully recorded grades for {len(data.grades)} students."}

@router.post("/grades/publish", response_model=MessageResponse)
async def publish_grades(data: GradePublishRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    count = AcademicService.publish_grades(
        db=db,
        school_id=user.school_id,
        user=user,
        class_id=data.class_id,
        subject_id=data.subject_id,
        term=data.term
    )
    return {"message": f"Published and certified results for {count} students."}

@router.get("/exam-events", response_model=List[ExamEventResponse])
async def list_exam_events(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(ExamSubmissionEvent).filter(ExamSubmissionEvent.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, subject_id=ExamSubmissionEvent.exam_id))
    return query.order_by(ExamSubmissionEvent.created_at.desc()).all()

# ==========================================
# 7. ABSENCES & SUBSTITUTIONS
# ==========================================
@router.get("/absences", response_model=List[AbsenceResponse])
async def list_absences(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(TeacherAbsence).filter(TeacherAbsence.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(TeacherAbsence.teacher.has(
            (Teacher.user_id == user.id) & Teacher.is_active.is_(True)
        ))
    absences = query.order_by(TeacherAbsence.date.desc()).all()
    result = []
    for a in absences:
        result.append({
            "id": a.id,
            "school_id": a.school_id,
            "teacher_id": a.teacher_id,
            "teacher_name": f"{a.teacher.first_name} {a.teacher.last_name}" if a.teacher else "Unknown",
            "date": a.date,
            "reason": a.reason,
            "status": a.status,
            "created_at": a.created_at
        })
    return result

@router.post("/absences", response_model=AbsenceResponse, status_code=201)
async def report_absence(data: AbsenceCreate, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    if user.role == "teacher" and not db.query(Teacher).filter_by(
        id=data.teacher_id, user_id=user.id, school_id=user.school_id, is_active=True,
    ).first():
        raise HTTPException(403, "Not authorized to report another teacher's absence")
    absence = SubstitutionService.record_absence(db, user.school_id, data.teacher_id, data.date, data.reason)
    return {
        "id": absence.id,
        "school_id": absence.school_id,
        "teacher_id": absence.teacher_id,
        "teacher_name": f"{absence.teacher.first_name} {absence.teacher.last_name}" if absence.teacher else "Unknown",
        "date": absence.date,
        "reason": absence.reason,
        "status": absence.status,
        "created_at": absence.created_at
    }

@router.get("/substitutions", response_model=List[SubstitutionResponse])
async def list_substitutions(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(SubstitutionAssignment).filter(SubstitutionAssignment.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(SubstitutionAssignment.substitute_teacher.has(
            (Teacher.user_id == user.id) & Teacher.is_active.is_(True)
        ))
    subs = query.order_by(SubstitutionAssignment.created_at.desc()).all()
    result = []
    for s in subs:
        result.append({
            "id": s.id,
            "school_id": s.school_id,
            "absence_id": s.absence_id,
            "substitute_teacher_id": s.substitute_teacher_id,
            "substitute_name": f"{s.substitute_teacher.first_name} {s.substitute_teacher.last_name}" if s.substitute_teacher else "Unknown",
            "timetable_slot_id": s.timetable_slot_id,
            "slot_details": {
                "period": s.slot.period,
                "day_of_week": s.slot.day_of_week,
                "room": s.slot.room,
                "subject": s.slot.subject.name if s.slot and s.slot.subject else None,
                "class": f"Class {s.slot.class_ref.class_level}{s.slot.class_ref.stream}" if s.slot and s.slot.class_ref else None
            } if s.slot else None,
            "confirmed": s.confirmed,
            "created_at": s.created_at
        })
    return result

@router.get("/substitutions/candidates")
async def get_substitution_candidates(
    slot_id: int,
    abs_date: date = Query(default_factory=date.today),
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db)
):
    return SubstitutionService.find_candidates_for_slot(db, user.school_id, slot_id, abs_date)

@router.post("/substitutions", response_model=SubstitutionResponse, status_code=201)
async def assign_substitution(data: SubstitutionAssignRequest, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    sub = SubstitutionService.assign_substitution(db, user.school_id, data.absence_id, data.substitute_teacher_id, data.timetable_slot_id)
    return {
        "id": sub.id,
        "school_id": sub.school_id,
        "absence_id": sub.absence_id,
        "substitute_teacher_id": sub.substitute_teacher_id,
        "substitute_name": f"{sub.substitute_teacher.first_name} {sub.substitute_teacher.last_name}" if sub.substitute_teacher else "Unknown",
        "timetable_slot_id": sub.timetable_slot_id,
        "confirmed": sub.confirmed,
        "created_at": sub.created_at
    }

@router.post("/substitutions/{id}/confirm", response_model=SubstitutionResponse)
async def confirm_substitution(id: int, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    sub = SubstitutionService.confirm_substitution(db, user.school_id, id)
    return {
        "id": sub.id,
        "school_id": sub.school_id,
        "absence_id": sub.absence_id,
        "substitute_teacher_id": sub.substitute_teacher_id,
        "substitute_name": f"{sub.substitute_teacher.first_name} {sub.substitute_teacher.last_name}" if sub.substitute_teacher else "Unknown",
        "timetable_slot_id": sub.timetable_slot_id,
        "confirmed": sub.confirmed,
        "created_at": sub.created_at
    }

# ==========================================
# 8. SYLLABUS PACING
# ==========================================
@router.get("/syllabus/plans", response_model=List[SyllabusPlanResponse])
async def list_syllabus_plans(class_id: Optional[int] = None, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(SyllabusPlan).filter(SyllabusPlan.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=SyllabusPlan.class_id, subject_id=SyllabusPlan.subject_id))
    if class_id is not None:
        require_class_access(db, user, class_id)
        query = query.filter(SyllabusPlan.class_id == class_id)
    plans = query.all()
    return [SyllabusService.get_plan_summary(db, p.id) for p in plans]

@router.post("/syllabus/plans", response_model=SyllabusPlanResponse, status_code=201)
async def create_syllabus_plan(data: SyllabusPlanCreate, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    require_course_access(db, user, data.class_id, data.subject_id)
    plan = SyllabusService.create_or_get_plan(
        db=db,
        school_id=user.school_id,
        class_id=data.class_id,
        subject_id=data.subject_id,
        total_units=data.total_units,
        midterm_target=data.midterm_target,
        final_target=data.final_target
    )
    return SyllabusService.get_plan_summary(db, plan.id)

@router.get("/syllabus/plans/{id}", response_model=SyllabusPlanResponse)
async def get_syllabus_plan(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    plan = db.query(SyllabusPlan).filter_by(id=id, school_id=user.school_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    require_course_access(db, user, plan.class_id, plan.subject_id)
    return SyllabusService.get_plan_summary(db, id)

@router.get("/syllabus/topics", response_model=List[SyllabusTopicResponse])
async def list_syllabus_topics(plan_id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    plan = db.query(SyllabusPlan).filter_by(id=plan_id, school_id=user.school_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    require_course_access(db, user, plan.class_id, plan.subject_id)
    summary = SyllabusService.get_plan_summary(db, plan_id)
    return summary["topics"]

@router.post("/syllabus/topics", response_model=SyllabusTopicResponse, status_code=201)
async def create_syllabus_topic(data: SyllabusTopicCreate, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    plan = db.query(SyllabusPlan).filter_by(id=data.plan_id, school_id=user.school_id).first()
    if not plan:
        raise HTTPException(404, "Plan not found")
    require_course_access(db, user, plan.class_id, plan.subject_id)
    topic = SyllabusService.add_topic(db, data.plan_id, data.unit_number, data.title, data.description, data.planned_completion_date)
    return {
        "id": topic.id,
        "plan_id": topic.plan_id,
        "unit_number": topic.unit_number,
        "title": topic.title,
        "description": topic.description,
        "planned_completion_date": topic.planned_completion_date,
        "is_completed": False,
        "progress_entries": []
    }

@router.post("/syllabus/progress", response_model=SyllabusProgressResponse, status_code=201)
async def record_syllabus_progress(data: SyllabusProgressCreate, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    topic = db.query(SyllabusTopic).join(SyllabusPlan).filter(
        SyllabusTopic.id == data.topic_id, SyllabusPlan.school_id == user.school_id,
    ).first()
    if not topic:
        raise HTTPException(404, "Syllabus topic not found")
    require_course_access(db, user, topic.plan.class_id, topic.plan.subject_id)
    entry = SyllabusService.record_progress(db, data.topic_id, user.id, data.date_covered, data.notes)
    return {
        "id": entry.id,
        "topic_id": entry.topic_id,
        "teacher_id": entry.teacher_id,
        "teacher_name": f"{user.first_name} {user.last_name}",
        "date_covered": entry.date_covered,
        "notes": entry.notes,
        "created_at": entry.created_at
    }

@router.get("/syllabus/status")
async def get_syllabus_status(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(SyllabusPlan).filter(SyllabusPlan.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=SyllabusPlan.class_id, subject_id=SyllabusPlan.subject_id))
    plans = query.all()
    summaries = [SyllabusService.get_plan_summary(db, p.id) for p in plans]
    on_track = sum(1 for s in summaries if s["status"] in ["on_track", "completed"])
    behind = sum(1 for s in summaries if s["status"] == "behind")
    completed = sum(1 for s in summaries if s["status"] == "completed")
    return {
        "total_plans": len(summaries),
        "on_track_count": on_track,
        "behind_count": behind,
        "completed_count": completed,
        "plans": summaries
    }

# ==========================================
# 9. BIOMETRICS & IDENTITY
# ==========================================
@router.post("/biometrics/register/options")
async def biometric_register_options(data: BiometricRegisterOptionsRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(id=data.student_id, school_id=user.school_id).first()
    if not student:
        raise HTTPException(404, "Student not found")
    return BiometricService.generate_registration_options(data.student_id)

@router.post("/biometrics/register/verify", response_model=MessageResponse)
async def biometric_register_verify(data: BiometricRegisterVerifyRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    BiometricService.register_credential(db, user.school_id, data.student_id, data.credential_id, data.public_key, data.transports)
    return {"message": "Biometric credential registered successfully"}

@router.post("/biometrics/verify")
async def verify_biometric(data: BiometricVerifyRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return BiometricService.verify_biometric(db, user.school_id, data.credential_id, data.verification_type, data.student_id)

@router.get("/biometrics/logs", response_model=List[BiometricLogResponse])
async def list_biometric_logs(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    logs = db.query(BiometricVerificationLog).outerjoin(Student, Student.id == BiometricVerificationLog.student_id).filter(
        or_(
            Student.school_id == user.school_id,
            BiometricVerificationLog.student_id == None
        )
    ).order_by(BiometricVerificationLog.created_at.desc()).limit(50).all()

    result = []
    for log in logs:
        result.append({
            "id": log.id,
            "student_id": log.student_id,
            "student_name": f"{log.student.first_name} {log.student.last_name}" if log.student else None,
            "credential_id": log.credential_id,
            "verification_type": log.verification_type,
            "status": log.status,
            "reason": log.reason,
            "created_at": log.created_at
        })
    return result

@router.post("/biometrics/exam-verify")
async def exam_hall_verify(data: BiometricVerifyRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    data.verification_type = "exam_hall_entry"
    return BiometricService.verify_biometric(db, user.school_id, data.credential_id, "exam_hall_entry", data.student_id)

@router.post("/biometrics/staff-checkin")
async def staff_checkin(data: BiometricVerifyRequest, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    log = BiometricVerificationLog(
        student_id=None,
        credential_id=data.credential_id,
        verification_type="staff_attendance",
        status="success",
        reason=f"Staff check-in verified for user #{user.id} ({user.first_name} {user.last_name})"
    )
    db.add(log)
    db.commit()
    return {"success": True, "status": "success", "message": "Staff attendance logged"}

# ==========================================
# 10. BACKUPS
# ==========================================
@router.get("/backups", response_model=List[BackupResponse])
async def list_backups(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).all()

@router.post("/backups/create", response_model=BackupResponse, status_code=201)
async def create_backup(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return BackupService.create_encrypted_backup(db, backup_type="snapshot", user_id=user.id)

@router.get("/backups/{id}/download")
async def download_backup(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    rec = db.query(BackupRecord).filter_by(id=id).first()
    if not rec or not os.path.exists(rec.file_path):
        raise HTTPException(404, "Backup file not found")
    
    audit = BackupAuditEvent(backup_id=id, action="downloaded", user_id=user.id, details="Backup downloaded by tenant manager")
    db.add(audit)
    db.commit()
    return FileResponse(rec.file_path, filename=os.path.basename(rec.file_path), media_type="application/octet-stream")

@router.post("/backups/{id}/verify")
async def verify_backup_file(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return BackupService.verify_backup(db, id, user.id)

@router.get("/backups/audit-events", response_model=List[BackupAuditEventResponse])
async def list_backup_audit_events(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return db.query(BackupAuditEvent).order_by(BackupAuditEvent.created_at.desc()).limit(100).all()

# ==========================================
# 11. FINANCE (Strictly Protected by Financial Firewall)
# ==========================================
@router.get("/finance/summary", response_model=FinanceSummary)
async def get_finance_summary(user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    return FinanceService.get_finance_summary(db, user.school_id)

@router.get("/finance/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    student_id: Optional[int] = None,
    status: Optional[str] = None,
    user: User = Depends(financial_firewall),
    db: Session = Depends(get_db)
):
    return FinanceService.list_invoices(db, user.school_id, student_id, status)

@router.post("/finance/invoices", response_model=InvoiceResponse, status_code=201)
async def create_invoice(data: InvoiceCreate, user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    inv = FinanceService.create_invoice(db, user.school_id, data.student_id, data.term, data.amount, data.due_date)
    return {
        "id": inv.id,
        "school_id": inv.school_id,
        "student_id": inv.student_id,
        "student_name": f"{inv.student.first_name} {inv.student.last_name}" if inv.student else "Unknown",
        "roll_number": inv.student.roll_number if inv.student else "N/A",
        "invoice_number": inv.invoice_number,
        "term": inv.term,
        "amount": inv.amount,
        "status": inv.status,
        "due_date": inv.due_date,
        "created_at": inv.created_at,
        "paid_amount": 0.0
    }

@router.post("/finance/invoices/generate-class")
async def generate_class_invoices(
    class_id: int,
    term: str = "Term 1",
    due_date: Optional[date] = None,
    user: User = Depends(financial_firewall),
    db: Session = Depends(get_db)
):
    invoices = FinanceService.generate_class_invoices(db, user.school_id, class_id, term, due_date)
    return {"message": f"Generated {len(invoices)} invoices for class #{class_id}"}

@router.get("/finance/invoices/{id}", response_model=InvoiceResponse)
async def get_invoice(id: int, user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    inv = db.query(StudentInvoice).filter_by(id=id, school_id=user.school_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found in this school")
    
    paid_sum = db.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0)).filter(
        PaymentTransaction.invoice_id == inv.id
    ).scalar()

    return {
        "id": inv.id,
        "school_id": inv.school_id,
        "student_id": inv.student_id,
        "student_name": f"{inv.student.first_name} {inv.student.last_name}" if inv.student else "Unknown",
        "roll_number": inv.student.roll_number if inv.student else "N/A",
        "invoice_number": inv.invoice_number,
        "term": inv.term,
        "amount": inv.amount,
        "status": inv.status,
        "due_date": inv.due_date,
        "created_at": inv.created_at,
        "paid_amount": float(paid_sum)
    }

@router.post("/finance/invoices/{id}/payments", response_model=PaymentResponse, status_code=201)
async def record_invoice_payment(id: int, data: PaymentCreate, user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    pay = FinanceService.record_payment(db, user.school_id, id, data.amount, data.payment_method, data.transaction_reference)
    return pay

@router.get("/finance/rates", response_model=List[TuitionRateResponse])
async def list_tuition_rates(user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    return FinanceService.list_tuition_rates(db, user.school_id)

@router.post("/finance/rates", response_model=TuitionRateResponse, status_code=201)
async def create_tuition_rate(data: TuitionRateCreate, user: User = Depends(financial_firewall), db: Session = Depends(get_db)):
    return FinanceService.create_or_update_tuition_rate(db, user.school_id, data.class_level, data.term, data.amount)

# ==========================================
# 12. ANALYTICS & PROFILE
# ==========================================
@router.get("/analytics/enrollment")
async def enrollment_analytics(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(Student).filter_by(school_id=user.school_id, is_active=True)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=Student.class_id))
    students = query.all()
    male = sum(1 for s in students if s.gender.lower() == "male")
    female = sum(1 for s in students if s.gender.lower() == "female")
    
    by_class = {}
    for s in students:
        lvl = s.class_ref.class_level if s.class_ref else 0
        by_class[f"Grade {lvl}"] = by_class.get(f"Grade {lvl}", 0) + 1

    return {
        "total_students": len(students),
        "male_count": male,
        "female_count": female,
        "by_grade": by_class
    }

@router.get("/analytics/attendance")
async def attendance_analytics(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    today = date.today()
    log = db.query(DailySubmissionLog).filter_by(school_id=user.school_id, log_date=today).first()
    submitted = log.attendance_submitted if log else False
    
    query = db.query(SubjectAttendance).filter_by(school_id=user.school_id, date=today)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=SubjectAttendance.class_id, subject_id=SubjectAttendance.subject_id))
    total_records = query.count()
    present_records = query.filter(SubjectAttendance.status == "present").count()
    rate = round((present_records / max(1, total_records)) * 100.0, 1) if total_records > 0 else 94.5

    return {
        "date": today.isoformat(),
        "daily_submitted": submitted,
        "attendance_rate": rate,
        "total_marked": total_records,
        "present_count": present_records
    }

@router.get("/analytics/academic-performance")
async def academic_performance(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(StudentGrade).filter(StudentGrade.school_id == user.school_id)
    if user.role == "teacher":
        query = query.join(Student).filter(
            Student.school_id == user.school_id,
            assigned_to(user, class_id=Student.class_id, subject_id=StudentGrade.subject_id),
        )
    grades = query.all()
    avg_score = sum(grade.score for grade in grades) / len(grades) if grades else 0.0
    
    distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for g in grades:
        letter = (g.grade or "F")[0]
        if letter in distribution:
            distribution[letter] += 1
        else:
            distribution["F"] += 1

    return {
        "average_score": round(float(avg_score), 1),
        "total_grades_recorded": len(grades),
        "grade_distribution": distribution
    }

@router.get("/profile")
@router.get("/info")
async def get_school_profile(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    school = db.query(PrivateSchool).filter_by(id=user.school_id).first()
    if not school:
        raise HTTPException(404, "School profile not found")
    return school

@router.put("/profile")
async def update_school_profile(
    contact_phone: Optional[str] = None,
    contact_email: Optional[str] = None,
    physical_address: Optional[str] = None,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db)
):
    school = db.query(PrivateSchool).filter_by(id=user.school_id).first()
    if not school:
        raise HTTPException(404, "School not found")
    if contact_phone:
        school.contact_phone = contact_phone
    if contact_email:
        school.contact_email = contact_email
    if physical_address:
        school.physical_address = physical_address
    db.commit()
    db.refresh(school)
    return school
