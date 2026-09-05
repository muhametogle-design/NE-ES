import uuid
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

# ----------------- Students -----------------
class StudentBase(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None

class StudentCreate(StudentBase):
    pass

class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None
    is_active: Optional[bool] = None

class StudentResponse(StudentBase):
    id: uuid.UUID
    school_id: int
    emis_id: str
    national_student_id: Optional[str] = None
    roll_number: Optional[str] = None
    classroom_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Classes & Subjects -----------------
class ClassCreate(BaseModel):
    class_level: int
    stream: str
    academic_year_id: Optional[int] = None

class ClassResponse(BaseModel):
    id: int
    school_id: int
    class_level: int
    stream: str
    academic_year_id: Optional[int] = None

    class Config:
        from_attributes = True

class SubjectCreate(BaseModel):
    code: str
    name: str
    level: int

class SubjectResponse(BaseModel):
    id: int
    school_id: int
    code: str
    name: str
    level: int

    class Config:
        from_attributes = True

# ----------------- Teachers & Assignments -----------------
class TeacherCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: bool = False

class TeacherUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: Optional[bool] = None

class TeacherResponse(BaseModel):
    id: int
    school_id: Optional[int] = None
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    staff_identifier: Optional[str] = None
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: bool = False
    is_active: bool = True

    class Config:
        from_attributes = True

class AssignmentCreate(BaseModel):
    teacher_id: int
    class_id: int
    subject_id: int

class AssignmentResponse(BaseModel):
    id: int
    school_id: int
    teacher_id: int
    class_id: int
    subject_id: int
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None
    subject_name: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- Timetable -----------------
class TimetableSlotCreate(BaseModel):
    class_id: int
    subject_id: int
    teacher_id: int
    day_of_week: int  # 0=Monday..6=Sunday
    period: int       # 1-8
    room: Optional[str] = None

class TimetableSlotResponse(BaseModel):
    id: int
    school_id: int
    class_id: int
    subject_id: int
    teacher_id: int
    day_of_week: int
    period: int
    room: Optional[str] = None
    subject_name: Optional[str] = None
    teacher_name: Optional[str] = None
    class_name: Optional[str] = None

    class Config:
        from_attributes = True

# ----------------- Attendance -----------------
class AttendanceRecordItem(BaseModel):
    student_id: uuid.UUID
    status: str  # present, absent, late, excused

class AttendanceMarkRequest(BaseModel):
    class_id: int
    subject_id: int
    date: date
    records: List[AttendanceRecordItem]

class SubjectAttendanceResponse(BaseModel):
    id: int
    student_id: uuid.UUID
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    subject_id: int
    class_id: int
    date: date
    status: str

    class Config:
        from_attributes = True

class LiveAttendanceMarkRequest(BaseModel):
    timetable_slot_id: int
    date: date
    records: List[AttendanceRecordItem]

class LiveAttendanceResponse(BaseModel):
    id: int
    student_id: uuid.UUID
    timetable_slot_id: int
    date: date
    status: str

    class Config:
        from_attributes = True

class AttendanceSubmitResponse(BaseModel):
    success: bool
    school_id: int
    date: str
    submitted_at: datetime
    message: str

# ----------------- Grades & Exams -----------------
class GradeEntryItem(BaseModel):
    student_id: uuid.UUID
    score: float
    grade: Optional[str] = None

class GradeBatchRequest(BaseModel):
    subject_id: int
    class_id: int
    term: str
    grades: List[GradeEntryItem]

class GradeResponse(BaseModel):
    id: int
    student_id: uuid.UUID
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    subject_id: int
    subject_name: Optional[str] = None
    term: str
    score: float
    grade: Optional[str] = None
    is_published: bool
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GradePublishRequest(BaseModel):
    subject_id: int
    class_id: int
    term: str

class ExamEventResponse(BaseModel):
    id: int
    school_id: int
    exam_id: int
    action: str
    performed_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Absences & Substitutions -----------------
class AbsenceCreate(BaseModel):
    teacher_id: int
    date: date
    reason: Optional[str] = None

class AbsenceResponse(BaseModel):
    id: int
    school_id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    date: date
    reason: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class CandidateTeacher(BaseModel):
    teacher_id: int
    teacher_name: str
    match_score: int
    is_same_department: bool
    is_free: bool
    current_load: int

class SubstitutionAssignRequest(BaseModel):
    absence_id: int
    substitute_teacher_id: int
    timetable_slot_id: int

class SubstitutionResponse(BaseModel):
    id: int
    school_id: int
    absence_id: int
    substitute_teacher_id: int
    substitute_name: Optional[str] = None
    timetable_slot_id: int
    slot_details: Optional[Dict[str, Any]] = None
    confirmed: bool
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Syllabus -----------------
class SyllabusPlanCreate(BaseModel):
    class_id: int
    subject_id: int
    total_units: int = 10
    midterm_target: float = 50.0
    final_target: float = 100.0

class SyllabusTopicCreate(BaseModel):
    plan_id: int
    unit_number: int
    title: str
    description: Optional[str] = None
    planned_completion_date: Optional[date] = None

class SyllabusProgressCreate(BaseModel):
    topic_id: int
    date_covered: date
    notes: Optional[str] = None

class SyllabusProgressResponse(BaseModel):
    id: int
    topic_id: int
    teacher_id: int
    teacher_name: Optional[str] = None
    date_covered: date
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SyllabusTopicResponse(BaseModel):
    id: int
    plan_id: int
    unit_number: int
    title: str
    description: Optional[str] = None
    planned_completion_date: Optional[date] = None
    is_completed: bool = False
    progress_entries: List[SyllabusProgressResponse] = []

    class Config:
        from_attributes = True

class SyllabusPlanResponse(BaseModel):
    id: int
    school_id: int
    class_id: int
    subject_id: int
    class_name: Optional[str] = None
    subject_name: Optional[str] = None
    total_units: int
    midterm_target: float
    final_target: float
    completed_units: int = 0
    progress_percentage: float = 0.0
    status: str = "on_track"  # on_track, behind, completed
    topics: List[SyllabusTopicResponse] = []

    class Config:
        from_attributes = True

# ----------------- Biometrics -----------------
class BiometricRegisterOptionsRequest(BaseModel):
    student_id: uuid.UUID

class BiometricRegisterVerifyRequest(BaseModel):
    student_id: uuid.UUID
    credential_id: str
    public_key: str
    transports: Optional[str] = "internal"

class BiometricVerifyRequest(BaseModel):
    credential_id: str
    verification_type: str = "exam_hall_entry"
    student_id: Optional[uuid.UUID] = None

class BiometricLogResponse(BaseModel):
    id: int
    student_id: Optional[uuid.UUID] = None
    student_name: Optional[str] = None
    credential_id: Optional[str] = None
    verification_type: str
    status: str
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Backups -----------------
class BackupResponse(BaseModel):
    id: int
    backup_type: str
    file_path: str
    checksum_sha256: Optional[str] = None
    checksum_md5: Optional[str] = None
    file_size_bytes: int
    encryption_algorithm: str
    created_at: datetime

    class Config:
        from_attributes = True

class BackupAuditEventResponse(BaseModel):
    id: int
    backup_id: Optional[int] = None
    action: str
    user_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# ----------------- Finance (Firewalled) -----------------
class TuitionRateCreate(BaseModel):
    class_level: int
    term: str
    amount: float

class TuitionRateResponse(BaseModel):
    id: int
    school_id: int
    class_level: int
    term: str
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    term: str
    amount: float
    due_date: Optional[date] = None

class InvoiceResponse(BaseModel):
    id: int
    school_id: int
    student_id: uuid.UUID
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    invoice_number: str
    term: str
    amount: float
    status: str
    due_date: Optional[date] = None
    created_at: datetime
    paid_amount: float = 0.0

    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    amount: float
    payment_method: str
    transaction_reference: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    school_id: int
    invoice_id: int
    amount: float
    payment_method: str
    transaction_reference: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class FinanceSummary(BaseModel):
    total_invoices: float
    collected_revenue: float
    pending_amount: float
    invoice_count: int
    paid_invoices_count: int
