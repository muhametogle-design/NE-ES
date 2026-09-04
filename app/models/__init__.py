from app.models.base import Base
from app.models.tenancy import PrivateSchool, SchoolRollSequence, User, AcademicYear
from app.models.academic import (
    SchoolClass, Subject, TeachingAssignment, TimetableSlot,
    Student, StudentGrade, SubjectAttendance, LiveAttendance
)
from app.models.finance import TuitionRate, StudentInvoice, PaymentTransaction
from app.models.compliance import (
    DailySubmissionLog, ExamSubmissionEvent, CommunicationLog,
    SecurityAuditLog, DataChangeLog
)
from app.models.backups import BackupRecord, BackupAuditEvent
from app.models.biometrics import BiometricCredential, BiometricVerificationLog
from app.models.absence import TeacherAbsence, SubstitutionAssignment
from app.models.syllabus import SyllabusPlan, SyllabusTopic, SyllabusProgressEntry

all_models = [
    PrivateSchool,
    SchoolRollSequence,
    User,
    AcademicYear,
    SchoolClass,
    Subject,
    TeachingAssignment,
    TimetableSlot,
    Student,
    StudentGrade,
    SubjectAttendance,
    LiveAttendance,
    TuitionRate,
    StudentInvoice,
    PaymentTransaction,
    DailySubmissionLog,
    ExamSubmissionEvent,
    CommunicationLog,
    SecurityAuditLog,
    DataChangeLog,
    BackupRecord,
    BackupAuditEvent,
    BiometricCredential,
    BiometricVerificationLog,
    TeacherAbsence,
    SubstitutionAssignment,
    SyllabusPlan,
    SyllabusTopic,
    SyllabusProgressEntry,
]

__all__ = [
    "Base",
    "PrivateSchool",
    "SchoolRollSequence",
    "User",
    "AcademicYear",
    "SchoolClass",
    "Subject",
    "TeachingAssignment",
    "TimetableSlot",
    "Student",
    "StudentGrade",
    "SubjectAttendance",
    "LiveAttendance",
    "TuitionRate",
    "StudentInvoice",
    "PaymentTransaction",
    "DailySubmissionLog",
    "ExamSubmissionEvent",
    "CommunicationLog",
    "SecurityAuditLog",
    "DataChangeLog",
    "BackupRecord",
    "BackupAuditEvent",
    "BiometricCredential",
    "BiometricVerificationLog",
    "TeacherAbsence",
    "SubstitutionAssignment",
    "SyllabusPlan",
    "SyllabusTopic",
    "SyllabusProgressEntry",
    "all_models",
]
