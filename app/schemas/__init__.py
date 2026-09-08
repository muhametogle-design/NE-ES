"""Pydantic schemas for the NE-EMIS API.

Students, classrooms, subjects and teachers live in dedicated modules; the
historical ``app.schemas.school`` module re-exports them (under the legacy
``ClassCreate`` / ``TeacherCreate`` / ... names) so existing imports keep
working. Importing from the canonical modules below is preferred in new code.
"""
from app.schemas.common import MessageResponse, StatusResponse, PaginatedResponse
from app.schemas.media import (
    PHOTO_URL_MAX_LENGTH, MediaUploadResponse, PhotoUrl, PhotoUrlUpdate, normalize_photo_url
)
from app.schemas.student import StudentBase, StudentCreate, StudentUpdate, StudentResponse
from app.schemas.classroom import (
    ClassroomBase, ClassroomCreate, ClassroomUpdate,
    ClassroomResponse, ClassroomDetailResponse,
)
from app.schemas.subject import (
    SubjectBase, SubjectCreate, SubjectUpdate, SubjectResponse,
    SubjectBrief, SubjectTeacherSummary, SubjectTeacherAssignRequest, SubjectTeacherRosterRequest,
)
from app.schemas.teacher import (
    TeacherBase, TeacherCreate, TeacherUpdate, TeacherResponse,
    TeacherUserProvision, TeacherAccountBrief, TeacherSubjectSetRequest, TeacherLinkUserRequest,
    TeacherAccountCreate, TeacherAccountUpdate, TeacherAccountResponse,
)
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, ChangePasswordRequest, SetPinRequest
from app.schemas.school import (
    AssignmentCreate, AssignmentResponse,
    TimetableSlotCreate, TimetableSlotResponse,
    AttendanceMarkRequest, SubjectAttendanceResponse, LiveAttendanceResponse, AttendanceSubmitResponse,
    GradeBatchRequest, GradeResponse, GradePublishRequest, ExamEventResponse,
    AbsenceCreate, AbsenceResponse, SubstitutionAssignRequest, SubstitutionResponse,
    SyllabusPlanCreate, SyllabusPlanResponse, SyllabusTopicCreate, SyllabusTopicResponse,
    SyllabusProgressCreate, SyllabusProgressResponse,
    BiometricRegisterVerifyRequest, BiometricVerifyRequest, BiometricLogResponse,
    BackupResponse, BackupAuditEventResponse,
    TuitionRateCreate, TuitionRateResponse, InvoiceCreate, InvoiceResponse, PaymentCreate, PaymentResponse,
    FinanceSummary
)
from app.schemas.state import (
    StateSchoolView, StateSchoolDetailView, StateSchoolCreate,
    StateStudentView, ComplianceMapItem, AlarmItem,
    RollSequenceResponse, RollSequenceUpdate, StateAnalyticsSummary
)
