from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class StateSchoolView(BaseModel):
    id: int
    school_code: str
    school_name: str
    state_license_number: Optional[str] = None
    proprietor_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    physical_address: Optional[str] = None
    accreditation_status: str = "Active"
    student_count: int = 0
    teacher_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True

class StateSchoolCreate(BaseModel):
    state_license_number: str
    school_code: str
    school_name: str
    proprietor_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    physical_address: Optional[str] = None
    accreditation_status: str = "Active"

class StateSchoolDetailView(StateSchoolView):
    classes: List[Dict[str, Any]] = []
    teachers: List[Dict[str, Any]] = []

class StateStudentView(BaseModel):
    roll_number: str
    national_student_id: str
    first_name: str
    last_name: str
    gender: str
    school_code: str
    school_name: str
    class_level: Optional[int] = None
    stream: Optional[str] = None
    is_active: bool = True

class ComplianceMapItem(BaseModel):
    school_id: int
    school_code: str
    school_name: str
    submitted: bool
    submitted_at: Optional[datetime] = None
    alarm: bool
    alarm_raised_at: Optional[datetime] = None

class AlarmItem(BaseModel):
    id: int
    school_id: Optional[int] = None
    school_code: Optional[str] = None
    school_name: Optional[str] = None
    type: str
    status: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class RollSequenceResponse(BaseModel):
    school_id: int
    school_code: str
    next_value: int

class RollSequenceUpdate(BaseModel):
    next_value: int

class StateAnalyticsSummary(BaseModel):
    total_schools: int
    total_students: int
    total_teachers: int
    active_alarms_today: int
    compliance_rate: float
