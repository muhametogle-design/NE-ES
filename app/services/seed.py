from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import hash_password
from app.models.tenancy import PrivateSchool, User
from app.models.compliance import DailySubmissionLog, CommunicationLog
from app.services.tenant_service import TenantService

def seed_demo_data(db: Session):
    # 1. Clean legacy placeholders if present
    for name in ["Greenfield Academy", "Horizon Preparatory School", "Crescent International School"]:
        legacy = db.query(PrivateSchool).filter(PrivateSchool.school_name == name).first()
        if legacy:
            db.delete(legacy)
    db.commit()

    # 2. State Admin & Inspector
    state_admin = db.query(User).filter(User.email == "stateadmin@education.gov").first()
    if not state_admin:
        state_admin = User(
            school_id=None,
            email="stateadmin@education.gov",
            password_hash=hash_password("StateAdmin@2026"),
            role="state_admin",
            first_name="State",
            last_name="Administrator",
            staff_identifier="NE-ADM-2026-HQ001",
            designation="Director General, Ministry of Education",
            is_active=True
        )
        db.add(state_admin)

    inspector = db.query(User).filter(User.email == "inspector@education.gov").first()
    if not inspector:
        inspector = User(
            school_id=None,
            email="inspector@education.gov",
            password_hash=hash_password("State@2026"),
            role="inspector",
            first_name="Chief",
            last_name="Inspector",
            staff_identifier="NE-INS-2026-HQ002",
            designation="Regional Quality Assurance Inspector",
            is_active=True
        )
        db.add(inspector)
    db.commit()

    # 3. Provision all 5 official private schools
    for tenant_data in TenantService.TENANTS:
        TenantService.provision_school_template(db, tenant_data, state_admin_id=state_admin.id)

    # 4. Set up realistic compliance state
    try:
        tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
    except Exception:
        tz = ZoneInfo("UTC")

    today = datetime.now(tz).date()
    submission_times = {
        "IL": "09:42",
        "NG": "10:17",
        "AQ": "10:48",
        "LB": "11:17"
    }

    for code, time_str in submission_times.items():
        school = db.query(PrivateSchool).filter(PrivateSchool.school_code == code).first()
        if school:
            t_obj = datetime.strptime(time_str, "%H:%M").time()
            sub_dt = datetime.combine(today, t_obj, tzinfo=tz)

            log = db.query(DailySubmissionLog).filter_by(school_id=school.id, log_date=today).first()
            if not log:
                log = DailySubmissionLog(
                    school_id=school.id,
                    log_date=today,
                    attendance_submitted=True,
                    submitted_at=sub_dt,
                    alarm_triggered=False
                )
                db.add(log)
            else:
                log.attendance_submitted = True
                log.submitted_at = sub_dt
                log.alarm_triggered = False

    # 5. Muse Yusuf (MY) missed today -> Alarm triggered
    my_school = db.query(PrivateSchool).filter(PrivateSchool.school_code == "MY").first()
    if my_school:
        my_log = db.query(DailySubmissionLog).filter_by(school_id=my_school.id, log_date=today).first()
        if not my_log:
            my_log = DailySubmissionLog(
                school_id=my_school.id,
                log_date=today,
                attendance_submitted=False,
                alarm_triggered=True,
                alarm_raised_at=datetime.combine(today, time(15, 0), tzinfo=tz)
            )
            db.add(my_log)

            comm = CommunicationLog(
                school_id=my_school.id,
                type="Red_Alarm",
                status="Delivered",
                content=f"CRITICAL COMPLIANCE BREACH: {my_school.school_name} (MY) missed daily attendance deadline."
            )
            db.add(comm)

        # Historic breach 2 days ago
        hist_date = today - timedelta(days=2)
        hist_log = db.query(DailySubmissionLog).filter_by(school_id=my_school.id, log_date=hist_date).first()
        if not hist_log:
            hist_log = DailySubmissionLog(
                school_id=my_school.id,
                log_date=hist_date,
                attendance_submitted=False,
                alarm_triggered=True,
                alarm_raised_at=datetime.combine(hist_date, time(15, 0), tzinfo=tz)
            )
            db.add(hist_log)

            hist_comm = CommunicationLog(
                school_id=my_school.id,
                type="Red_Alarm",
                status="Delivered",
                content=f"CRITICAL COMPLIANCE BREACH: {my_school.school_name} (MY) missed daily attendance deadline on {hist_date}."
            )
            db.add(hist_comm)

    db.commit()
