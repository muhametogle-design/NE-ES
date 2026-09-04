import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from app.core.config import settings
from app.core.db import SessionLocal
from app.services.compliance_service import run_attendance_audit
from app.services.backup_service import BackupService

logger = logging.getLogger(__name__)

class ComplianceScheduler:
    def __init__(self):
        self.task: asyncio.Task | None = None

    def start(self):
        if self.task is None:
            self.task = asyncio.create_task(self._run())
            logger.info("Compliance scheduler task started")

    def stop(self):
        if self.task:
            self.task.cancel()
            self.task = None
            logger.info("Compliance scheduler task stopped")

    async def _run(self):
        try:
            tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
        except Exception:
            tz = ZoneInfo("UTC")

        audit_hour, audit_min = map(int, settings.ALARM_AUDIT_TIME.split(":"))

        while True:
            try:
                now = datetime.now(tz)
                target = now.replace(hour=audit_hour, minute=audit_min, second=0, microsecond=0)
                if now >= target:
                    # Move to next day
                    target = target.replace(day=now.day + 1)
                
                sleep_seconds = max(1.0, (target - now).total_seconds())
                logger.info(f"Compliance scheduler sleeping for {sleep_seconds:.1f}s until {target}")
                await asyncio.sleep(sleep_seconds)

                db = SessionLocal()
                try:
                    result = run_attendance_audit(db)
                    logger.info(f"Compliance audit executed: {result}")
                except Exception as e:
                    logger.error(f"Compliance audit failed: {e}", exc_info=True)
                    db.rollback()
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in compliance scheduler loop: {e}")
                await asyncio.sleep(60)

class BackupScheduler:
    def __init__(self):
        self.task: asyncio.Task | None = None

    def start(self):
        if self.task is None:
            self.task = asyncio.create_task(self._run())
            logger.info("Backup scheduler task started")

    def stop(self):
        if self.task:
            self.task.cancel()
            self.task = None
            logger.info("Backup scheduler task stopped")

    async def _run(self):
        try:
            tz = ZoneInfo(settings.PLATFORM_TIMEZONE)
        except Exception:
            tz = ZoneInfo("UTC")

        backup_hour, backup_min = map(int, settings.BACKUP_TIME.split(":"))

        while True:
            try:
                now = datetime.now(tz)
                target = now.replace(hour=backup_hour, minute=backup_min, second=0, microsecond=0)
                if now >= target:
                    target = target.replace(day=now.day + 1)

                sleep_seconds = max(1.0, (target - now).total_seconds())
                logger.info(f"Backup scheduler sleeping for {sleep_seconds:.1f}s until {target}")
                await asyncio.sleep(sleep_seconds)

                db = SessionLocal()
                try:
                    rec = BackupService.create_encrypted_backup(db, backup_type="full")
                    logger.info(f"Scheduled encrypted backup completed: record_id={rec.id}")
                except Exception as e:
                    logger.error(f"Backup scheduler failed: {e}", exc_info=True)
                    db.rollback()
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in backup scheduler loop: {e}")
                await asyncio.sleep(60)

compliance_scheduler = ComplianceScheduler()
backup_scheduler = BackupScheduler()
