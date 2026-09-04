from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.ws import ws_manager
from app.models.compliance import DailySubmissionLog, CommunicationLog
from app.models.tenancy import PrivateSchool

def run_attendance_audit(db: Session):
    tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
    now_dt = datetime.now(tz)
    today = now_dt.date()

    schools = db.query(PrivateSchool).all()
    alarms_raised = 0

    for school in schools:
        log = db.query(DailySubmissionLog).filter_by(
            school_id=school.id,
            log_date=today
        ).first()

        if not log:
            # School did not submit anything today
            log = DailySubmissionLog(
                school_id=school.id,
                log_date=today,
                attendance_submitted=False,
                alarm_triggered=True,
                alarm_raised_at=now_dt
            )
            db.add(log)
            db.flush()

            comm = CommunicationLog(
                school_id=school.id,
                type="Red_Alarm",
                status="Delivered",
                content=f"CRITICAL COMPLIANCE BREACH: {school.school_name} (Code: {school.school_code}) missed the attendance submission deadline (12:00 EAT)."
            )
            db.add(comm)
            alarms_raised += 1

            # Broadcast Red Alarm via WebSocket
            ws_manager.broadcast_sync(school.id, {
                "type": "red_alarm",
                "school_id": school.id,
                "school_code": school.school_code,
                "school_name": school.school_name,
                "message": f"CRITICAL COMPLIANCE BREACH: Daily attendance deadline passed without submission.",
                "timestamp": now_dt.isoformat()
            })
        elif not log.attendance_submitted and not log.alarm_triggered:
            # Entry exists but not submitted, alarm not yet raised
            log.alarm_triggered = True
            log.alarm_raised_at = now_dt

            comm = CommunicationLog(
                school_id=school.id,
                type="Red_Alarm",
                status="Delivered",
                content=f"CRITICAL COMPLIANCE BREACH: {school.school_name} (Code: {school.school_code}) missed the attendance submission deadline (12:00 EAT)."
            )
            db.add(comm)
            alarms_raised += 1

            ws_manager.broadcast_sync(school.id, {
                "type": "red_alarm",
                "school_id": school.id,
                "school_code": school.school_code,
                "school_name": school.school_name,
                "message": f"CRITICAL COMPLIANCE BREACH: Daily attendance deadline passed without submission.",
                "timestamp": now_dt.isoformat()
            })

    db.commit()
    return {"date": today.isoformat(), "alarms_raised": alarms_raised}
