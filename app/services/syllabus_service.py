from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.syllabus import SyllabusPlan, SyllabusTopic, SyllabusProgressEntry
from app.models.academic import SchoolClass, Subject

class SyllabusService:
    @staticmethod
    def create_or_get_plan(
        db: Session,
        school_id: int,
        class_id: int,
        subject_id: int,
        total_units: int = 10,
        midterm_target: float = 50.0,
        final_target: float = 100.0
    ) -> SyllabusPlan:
        plan = db.query(SyllabusPlan).filter_by(
            school_id=school_id,
            class_id=class_id,
            subject_id=subject_id
        ).first()

        if not plan:
            plan = SyllabusPlan(
                school_id=school_id,
                class_id=class_id,
                subject_id=subject_id,
                total_units=total_units,
                midterm_target=midterm_target,
                final_target=final_target
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
        return plan

    @staticmethod
    def add_topic(
        db: Session,
        plan_id: int,
        unit_number: int,
        title: str,
        description: Optional[str] = None,
        planned_completion_date: Optional[date] = None
    ) -> SyllabusTopic:
        topic = SyllabusTopic(
            plan_id=plan_id,
            unit_number=unit_number,
            title=title,
            description=description,
            planned_completion_date=planned_completion_date
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
        return topic

    @staticmethod
    def record_progress(
        db: Session,
        topic_id: int,
        teacher_id: int,
        date_covered: date,
        notes: Optional[str] = None
    ) -> SyllabusProgressEntry:
        topic = db.query(SyllabusTopic).filter_by(id=topic_id).first()
        if not topic:
            raise HTTPException(status_code=404, detail="Syllabus topic not found")

        entry = SyllabusProgressEntry(
            topic_id=topic_id,
            teacher_id=teacher_id,
            date_covered=date_covered,
            notes=notes
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get_plan_summary(db: Session, plan_id: int) -> Dict[str, Any]:
        plan = db.query(SyllabusPlan).filter_by(id=plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Syllabus plan not found")

        topics = db.query(SyllabusTopic).filter_by(plan_id=plan_id).order_by(SyllabusTopic.unit_number).all()
        topic_data = []
        completed_units = 0

        for t in topics:
            entries = db.query(SyllabusProgressEntry).filter_by(topic_id=t.id).order_by(SyllabusProgressEntry.date_covered.desc()).all()
            is_done = len(entries) > 0
            if is_done:
                completed_units += 1
            
            topic_data.append({
                "id": t.id,
                "plan_id": t.plan_id,
                "unit_number": t.unit_number,
                "title": t.title,
                "description": t.description,
                "planned_completion_date": t.planned_completion_date,
                "is_completed": is_done,
                "progress_entries": [
                    {
                        "id": pe.id,
                        "topic_id": pe.topic_id,
                        "teacher_id": pe.teacher_id,
                        "teacher_name": f"{pe.teacher.first_name} {pe.teacher.last_name}" if pe.teacher else None,
                        "date_covered": pe.date_covered,
                        "notes": pe.notes,
                        "created_at": pe.created_at
                    } for pe in entries
                ]
            })

        total = max(1, plan.total_units)
        pct = round((completed_units / total) * 100.0, 1)

        if pct >= 100.0:
            status = "completed"
        elif pct >= plan.midterm_target:
            status = "on_track"
        else:
            status = "behind"

        return {
            "id": plan.id,
            "school_id": plan.school_id,
            "class_id": plan.class_id,
            "subject_id": plan.subject_id,
            "class_name": f"Class {plan.class_ref.class_level}{plan.class_ref.stream}" if plan.class_ref else f"Class #{plan.class_id}",
            "subject_name": plan.subject.name if plan.subject else f"Subject #{plan.subject_id}",
            "total_units": plan.total_units,
            "midterm_target": plan.midterm_target,
            "final_target": plan.final_target,
            "completed_units": completed_units,
            "progress_percentage": pct,
            "status": status,
            "topics": topic_data
        }
