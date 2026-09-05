import math
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.api.deps import state_access_guard
from app.core.config import settings
from app.core.db import get_db
from app.models.tenancy import User, PrivateSchool, SchoolRollSequence
from app.models.academic import Student, SchoolClass, Subject, TeachingAssignment, LiveAttendance
from app.models.compliance import DailySubmissionLog, CommunicationLog, ExamSubmissionEvent
from app.schemas.state import (
    StateSchoolView, StateSchoolDetailView, StateSchoolCreate,
    StateStudentView, ComplianceMapItem, AlarmItem,
    RollSequenceResponse, RollSequenceUpdate, StateAnalyticsSummary
)
from app.schemas.common import MessageResponse
from app.services.tenant_service import TenantService
from app.services.compliance_service import run_attendance_audit

router = APIRouter(prefix="/v1/state", tags=["state"])

# ==========================================
# 1. INSTITUTIONS / SCHOOLS
# ==========================================
@router.get("/schools", response_model=List[StateSchoolView])
async def list_schools(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    schools = db.query(PrivateSchool).all()
    results = []
    for s in schools:
        st_count = db.query(Student).filter(Student.school_id == s.id, Student.is_active == True).count()
        t_count = db.query(User).filter(User.school_id == s.id, User.role == "teacher", User.is_active == True).count()
        results.append({
            "id": s.id,
            "school_code": s.school_code,
            "school_name": s.school_name,
            "state_license_number": s.state_license_number,
            "proprietor_name": s.proprietor_name,
            "contact_phone": s.contact_phone,
            "contact_email": s.contact_email,
            "physical_address": s.physical_address,
            "accreditation_status": s.accreditation_status,
            "student_count": st_count,
            "teacher_count": t_count,
            "created_at": s.created_at
        })
    return results

@router.get("/schools/{id}", response_model=StateSchoolView)
async def get_school(id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    s = db.query(PrivateSchool).filter(PrivateSchool.id == id).first()
    if not s:
        raise HTTPException(404, "School not found")
    st_count = db.query(Student).filter(Student.school_id == s.id, Student.is_active == True).count()
    t_count = db.query(User).filter(User.school_id == s.id, User.role == "teacher", User.is_active == True).count()
    return {
        "id": s.id,
        "school_code": s.school_code,
        "school_name": s.school_name,
        "state_license_number": s.state_license_number,
        "proprietor_name": s.proprietor_name,
        "contact_phone": s.contact_phone,
        "contact_email": s.contact_email,
        "physical_address": s.physical_address,
        "accreditation_status": s.accreditation_status,
        "student_count": st_count,
        "teacher_count": t_count,
        "created_at": s.created_at
    }

@router.post("/schools", response_model=StateSchoolView, status_code=201)
async def register_school(data: StateSchoolCreate, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    tenant_payload = {
        "code": data.school_code.upper(),
        "name": data.school_name,
        "license": data.state_license_number,
        "proprietor": data.proprietor_name,
        "phone": data.contact_phone,
        "email": data.contact_email,
        "address": data.physical_address,
        "domain": f"{data.school_code.lower()}.edu.so",
        "streams": ["A", "B"]
    }
    school = TenantService.provision_school_template(db, tenant_payload, state_admin_id=user.id)
    return {
        "id": school.id,
        "school_code": school.school_code,
        "school_name": school.school_name,
        "state_license_number": school.state_license_number,
        "proprietor_name": school.proprietor_name,
        "contact_phone": school.contact_phone,
        "contact_email": school.contact_email,
        "physical_address": school.physical_address,
        "accreditation_status": school.accreditation_status,
        "student_count": 0,
        "teacher_count": 0,
        "created_at": school.created_at
    }

@router.get("/institutions/{id}/classes")
async def list_institution_classes(id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    classes = db.query(SchoolClass).filter(SchoolClass.school_id == id).order_by(SchoolClass.class_level, SchoolClass.stream).all()
    results = []
    for c in classes:
        st_count = db.query(Student).filter(Student.class_id == c.id, Student.is_active == True).count()
        results.append({
            "id": c.id,
            "class_level": c.class_level,
            "stream": c.stream,
            "student_count": st_count
        })
    return results

@router.get("/institutions/{id}/classes/{cid}/breakdown")
async def get_institution_class_breakdown(id: int, cid: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    c = db.query(SchoolClass).filter(SchoolClass.id == cid, SchoolClass.school_id == id).first()
    if not c:
        raise HTTPException(404, "Class not found")

    students = db.query(Student).filter(Student.class_id == cid, Student.is_active == True).all()
    male_count = sum(1 for s in students if s.gender.lower() == "male")
    female_count = sum(1 for s in students if s.gender.lower() == "female")

    assignments = db.query(TeachingAssignment).filter(TeachingAssignment.class_id == cid).all()
    subjects = []
    for a in assignments:
        subjects.append({
            "subject_code": a.subject.code if a.subject else "N/A",
            "subject_name": a.subject.name if a.subject else "Unknown",
            "teacher_name": f"{a.teacher.first_name} {a.teacher.last_name}" if a.teacher else "Unassigned"
        })

    return {
        "class_id": c.id,
        "class_level": c.class_level,
        "stream": c.stream,
        "total_students": len(students),
        "male_count": male_count,
        "female_count": female_count,
        "subjects": subjects
    }

@router.get("/institutions/{id}/teachers")
async def list_institution_teachers(id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    teachers = db.query(User).filter(User.school_id == id, User.role == "teacher").all()
    return [{
        "id": t.id,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "email": t.email,
        "staff_identifier": t.staff_identifier,
        "qualifications": t.qualifications,
        "designation": t.designation,
        "is_department_head": t.is_department_head
    } for t in teachers]

@router.get("/teachers/{id}")
async def get_state_teacher(id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    t = db.query(User).filter(User.id == id, User.role == "teacher").first()
    if not t:
        raise HTTPException(404, "Teacher not found")
    return {
        "id": t.id,
        "school_id": t.school_id,
        "school_name": t.school.school_name if t.school else None,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "email": t.email,
        "staff_identifier": t.staff_identifier,
        "qualifications": t.qualifications,
        "designation": t.designation,
        "is_department_head": t.is_department_head,
        "phone": t.phone
    }

# ==========================================
# 2. ROLL SEQUENCE MANAGEMENT
# ==========================================
@router.get("/schools/{id}/roll-sequence", response_model=RollSequenceResponse)
async def get_school_roll_sequence(id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    school = db.query(PrivateSchool).filter(PrivateSchool.id == id).first()
    if not school:
        raise HTTPException(404, "School not found")

    seq = db.query(SchoolRollSequence).filter(SchoolRollSequence.school_id == id).first()
    if not seq:
        seq = SchoolRollSequence(school_id=id, next_value=10000)
        db.add(seq)
        db.commit()

    return {
        "school_id": school.id,
        "school_code": school.school_code,
        "next_value": seq.next_value
    }

@router.patch("/schools/{id}/roll-sequence", response_model=RollSequenceResponse)
async def update_school_roll_sequence(id: int, data: RollSequenceUpdate, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    school = db.query(PrivateSchool).filter(PrivateSchool.id == id).first()
    if not school:
        raise HTTPException(404, "School not found")

    updated_seq = TenantService.update_roll_sequence(db, id, data.next_value)
    return {
        "school_id": school.id,
        "school_code": school.school_code,
        "next_value": updated_seq.next_value
    }

# ==========================================
# 3. STUDENT REGISTRY & LOOKUP
# ==========================================
@router.get("/students/search", response_model=List[StateStudentView])
async def search_state_students(
    q: str = Query(..., min_length=1),
    user: User = Depends(state_access_guard),
    db: Session = Depends(get_db)
):
    search = f"%{q}%"
    students = db.query(Student).filter(
        or_(
            Student.first_name.ilike(search),
            Student.last_name.ilike(search),
            Student.roll_number.ilike(search),
            Student.national_student_id.ilike(search),
            Student.emis_id.ilike(search)
        )
    ).limit(50).all()

    return [{
        "roll_number": s.roll_number,
        "national_student_id": s.national_student_id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "gender": s.gender,
        "school_code": s.school.school_code if s.school else "??",
        "school_name": s.school.school_name if s.school else "Unknown",
        "class_level": s.class_ref.class_level if s.class_ref else None,
        "stream": s.class_ref.stream if s.class_ref else None,
        "is_active": s.is_active
    } for s in students]

@router.get("/students/lookup", response_model=StateStudentView)
async def lookup_state_student(
    ne_sid: str = Query(..., description="Student Roll Number or National ID"),
    user: User = Depends(state_access_guard),
    db: Session = Depends(get_db)
):
    student = db.query(Student).filter(
        or_(
            Student.roll_number == ne_sid,
            Student.national_student_id == ne_sid,
            Student.emis_id == ne_sid
        )
    ).first()

    if not student:
        raise HTTPException(404, f"No student record found with identifier '{ne_sid}'")

    return {
        "roll_number": student.roll_number,
        "national_student_id": student.national_student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "gender": student.gender,
        "school_code": student.school.school_code if student.school else "??",
        "school_name": student.school.school_name if student.school else "Unknown",
        "class_level": student.class_ref.class_level if student.class_ref else None,
        "stream": student.class_ref.stream if student.class_ref else None,
        "is_active": student.is_active
    }

# ==========================================
# 4. COMPLIANCE & ALARMS
# ==========================================
@router.get("/compliance-map", response_model=List[ComplianceMapItem])
async def get_compliance_map(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    try:
        tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()

    schools = db.query(PrivateSchool).all()
    result = []
    for s in schools:
        log = db.query(DailySubmissionLog).filter_by(school_id=s.id, log_date=today).first()
        result.append({
            "school_id": s.id,
            "school_code": s.school_code,
            "school_name": s.school_name,
            "submitted": log.attendance_submitted if log else False,
            "submitted_at": log.submitted_at if log else None,
            "alarm": log.alarm_triggered if log else False,
            "alarm_raised_at": log.alarm_raised_at if log else None
        })
    return result

@router.get("/alarms", response_model=List[AlarmItem])
async def list_alarms(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    alarms = db.query(CommunicationLog).order_by(CommunicationLog.created_at.desc()).limit(100).all()
    results = []
    for a in alarms:
        results.append({
            "id": a.id,
            "school_id": a.school_id,
            "school_code": a.school.school_code if a.school else None,
            "school_name": a.school.school_name if a.school else None,
            "type": a.type,
            "status": a.status,
            "content": a.content,
            "created_at": a.created_at
        })
    return results

@router.post("/alarms/dismiss", response_model=MessageResponse)
async def dismiss_alarm(alarm_id: int, user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    log = db.query(CommunicationLog).filter_by(id=alarm_id).first()
    if log:
        log.status = "Resolved"
        db.commit()
    return {"message": "Alarm marked as resolved"}

@router.post("/audit/run")
async def trigger_compliance_audit(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    result = run_attendance_audit(db)
    return {"success": True, "details": result, "message": "Manual compliance attendance audit executed successfully"}

@router.get("/exam-events")
async def list_state_exam_events(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    events = db.query(ExamSubmissionEvent).order_by(ExamSubmissionEvent.created_at.desc()).limit(100).all()
    return [{
        "id": e.id,
        "school_id": e.school_id,
        "school_code": e.school.school_code if e.school else None,
        "school_name": e.school.school_name if e.school else None,
        "exam_id": e.exam_id,
        "action": e.action,
        "performed_by_name": f"{e.user.first_name} {e.user.last_name}" if e.user else None,
        "created_at": e.created_at
    } for e in events]

# ==========================================
# 5. ATTENDANCE & ANALYTICS
# ==========================================
@router.get("/attendance/live")
async def list_state_live_attendance(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    today = date.today()
    live = db.query(LiveAttendance).filter(LiveAttendance.date == today).limit(100).all()
    return [{
        "id": l.id,
        "school_id": l.school_id,
        "school_code": l.student.school.school_code if l.student and l.student.school else "??",
        "student_name": f"{l.student.first_name} {l.student.last_name}" if l.student else "Unknown",
        "status": l.status,
        "date": l.date
    } for l in live]

@router.get("/attendance/summary")
async def get_state_attendance_summary(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    today = date.today()
    total_schools = db.query(PrivateSchool).count()
    submitted = db.query(DailySubmissionLog).filter(DailySubmissionLog.log_date == today, DailySubmissionLog.attendance_submitted == True).count()
    alarms = db.query(DailySubmissionLog).filter(DailySubmissionLog.log_date == today, DailySubmissionLog.alarm_triggered == True).count()

    rate = round((submitted / max(1, total_schools)) * 100.0, 1)
    return {
        "date": today.isoformat(),
        "total_schools": total_schools,
        "submitted_schools": submitted,
        "alarm_schools": alarms,
        "compliance_percentage": rate
    }

@router.get("/analytics/enrollment-by-class")
async def analytics_enrollment_by_class(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    results = db.query(
        SchoolClass.class_level,
        func.count(Student.id).label("student_count")
    ).join(Student, Student.class_id == SchoolClass.id).filter(
        Student.is_active == True
    ).group_by(SchoolClass.class_level).order_by(SchoolClass.class_level).all()

    return [{"grade": f"Grade {r[0]}", "count": r[1]} for r in results]

@router.get("/analytics/gender-distribution")
async def analytics_gender_distribution(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    male = db.query(Student).filter(func.lower(Student.gender) == "male", Student.is_active == True).count()
    female = db.query(Student).filter(func.lower(Student.gender) == "female", Student.is_active == True).count()
    return {"male": male, "female": female, "total": male + female}

@router.get("/analytics/school-rankings")
async def analytics_school_rankings(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    schools = db.query(PrivateSchool).all()
    rankings = []
    for s in schools:
        st_count = db.query(Student).filter(Student.school_id == s.id, Student.is_active == True).count()
        rankings.append({
            "school_id": s.id,
            "school_code": s.school_code,
            "school_name": s.school_name,
            "total_enrolled": st_count,
            "accreditation": s.accreditation_status
        })
    rankings.sort(key=lambda r: r["total_enrolled"], reverse=True)
    return rankings

@router.get("/analytics/summary", response_model=StateAnalyticsSummary)
async def analytics_summary(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    today = date.today()
    total_schools = db.query(PrivateSchool).count()
    total_students = db.query(Student).filter(Student.is_active == True).count()
    total_teachers = db.query(User).filter(User.role == "teacher", User.is_active == True).count()
    active_alarms = db.query(DailySubmissionLog).filter(DailySubmissionLog.log_date == today, DailySubmissionLog.alarm_triggered == True).count()
    submitted = db.query(DailySubmissionLog).filter(DailySubmissionLog.log_date == today, DailySubmissionLog.attendance_submitted == True).count()
    rate = round((submitted / max(1, total_schools)) * 100.0, 1) if total_schools > 0 else 100.0

    return {
        "total_schools": total_schools,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "active_alarms_today": active_alarms,
        "compliance_rate": rate
    }

# ==========================================
# 6. HELPERS
# ==========================================
@router.get("/class-levels")
async def list_class_levels(user: User = Depends(state_access_guard)):
    return [{"level": i, "name": f"Grade {i} (Primary/Secondary)"} for i in range(1, 13)]

@router.get("/school-code-suggestion")
async def get_school_code_suggestion(user: User = Depends(state_access_guard), db: Session = Depends(get_db)):
    existing_codes = {s.school_code for s in db.query(PrivateSchool.school_code).all()}
    candidates = ["SO", "PL", "SL", "WD", "SN", "BY", "HI", "JD", "MD", "TG"]
    for c in candidates:
        if c not in existing_codes:
            return {"suggested_code": c}
    return {"suggested_code": "NE"}
