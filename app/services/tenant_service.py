import random
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from fastapi import HTTPException
from app.models.tenancy import PrivateSchool, SchoolRollSequence, User, AcademicYear
from app.models.academic import SchoolClass, Subject, TeachingAssignment, Student
from app.models.finance import TuitionRate
from app.core.security import hash_password

class TenantService:
    CORE_SUBJECTS = [
        ("SOM", "Somali (Af-Somali)"),
        ("ARB", "Arabic"),
        ("ENG", "English"),
        ("MAT", "Mathematics"),
        ("ISL", "Islamic Studies"),
        ("PHY", "Physics"),
        ("CHE", "Chemistry"),
        ("BIO", "Biology"),
        ("HIS", "History"),
        ("GEO", "Geography"),
    ]

    TENANTS = [
        {
            "code": "IL",
            "name": "Ilays Educational Academy",
            "license": "SOL/PS/2026/IL01",
            "proprietor": "Halima Farah",
            "address": "Masalaha Quarter, Laascaanood",
            "domain": "ilays.edu.so",
            "streams": ["A", "B"],
            "phone": "+252-63-400-1101",
            "email": "info@ilays.edu.so",
        },
        {
            "code": "MY",
            "name": "Muse Yusuf Secondary School",
            "license": "SOL/PS/2026/MY02",
            "proprietor": "Abdisalam Nur",
            "address": "Boameh Street, Laascaanood",
            "domain": "museyusuf.edu.so",
            "streams": ["A"],
            "phone": "+252-63-400-1102",
            "email": "admin@museyusuf.edu.so",
        },
        {
            "code": "NG",
            "name": "Nugaal High School",
            "license": "SOL/PS/2026/NG03",
            "proprietor": "Deqa Hersi",
            "address": "Airport Road, Laascaanood",
            "domain": "nugaal.edu.so",
            "streams": ["A", "B"],
            "phone": "+252-63-400-1103",
            "email": "contact@nugaal.edu.so",
        },
        {
            "code": "AQ",
            "name": "ALQALAM SCHOOLS",
            "license": "SOL/PS/2026/AQ04",
            "proprietor": "Muna Jama",
            "address": "Xero Awr, Laascaanood",
            "domain": "alqalam.edu.so",
            "streams": ["A"],
            "phone": "+252-63-400-1104",
            "email": "info@alqalam.edu.so",
        },
        {
            "code": "LB",
            "name": "Las Anod Boarding Secondary School (LBSS)",
            "license": "SOL/PS/2026/LB05",
            "proprietor": "Warsame Adan",
            "address": "Jireeye Road, Laascaanood",
            "domain": "lbss.edu.so",
            "streams": ["A", "B"],
            "phone": "+252-63-400-1105",
            "email": "admin@lbss.edu.so",
        },
    ]

    @staticmethod
    def provision_school_template(db: Session, tenant_data: Dict[str, Any], state_admin_id: Optional[int] = None) -> PrivateSchool:
        existing = db.query(PrivateSchool).filter(
            (PrivateSchool.school_code == tenant_data["code"]) |
            (PrivateSchool.state_license_number == tenant_data["license"])
        ).first()
        if existing:
            return existing

        school = PrivateSchool(
            state_license_number=tenant_data["license"],
            school_code=tenant_data["code"].upper(),
            school_name=tenant_data["name"],
            proprietor_name=tenant_data.get("proprietor"),
            contact_phone=tenant_data.get("phone"),
            contact_email=tenant_data.get("email"),
            physical_address=tenant_data.get("address"),
            accreditation_status="Active",
            billing_contact_name=f"{tenant_data.get('proprietor', 'School Admin')} (Accounts)",
            billing_phone=tenant_data.get("phone"),
            billing_email=f"finance@{tenant_data.get('domain', 'school.edu.so')}",
            billing_address=tenant_data.get("address"),
            billing_notes="Standard tenant account provisioned under NE-EMIS network.",
        )
        db.add(school)
        db.flush()

        # Roll sequence
        roll_seq = SchoolRollSequence(school_id=school.id, next_value=10000)
        db.add(roll_seq)

        # Academic Year
        acad_year = AcademicYear(
            school_id=school.id,
            year_name="2025/2026",
            is_current=True,
        )
        db.add(acad_year)
        db.flush()

        # Manager user
        manager = User(
            school_id=school.id,
            email=f"manager@{tenant_data['domain']}",
            password_hash=hash_password("School@2026"),
            role="school_manager",
            first_name="School",
            last_name="Manager",
            staff_identifier=TenantService.generate_staff_id("NE-MID"),
            phone=tenant_data.get("phone"),
            designation="Principal / School Manager",
            is_department_head=True,
        )
        db.add(manager)

        # Classes
        streams = tenant_data.get("streams", ["A", "B"])
        classes = []
        for level in range(1, 13):
            for stream in streams:
                school_class = SchoolClass(
                    school_id=school.id,
                    class_level=level,
                    stream=stream,
                    academic_year_id=acad_year.id,
                )
                db.add(school_class)
                classes.append(school_class)
        db.flush()

        # Core subjects for all 12 levels
        subjects = []
        for level in range(1, 13):
            for code, name in TenantService.CORE_SUBJECTS:
                subject = Subject(
                    school_id=school.id,
                    code=f"{code}-{level:02d}",
                    name=name,
                    level=level,
                )
                db.add(subject)
                subjects.append(subject)
        db.flush()

        # Teachers
        teachers = TenantService.create_setup_teachers(db, school.id, tenant_data.get("domain", f"{school.school_code.lower()}.edu.so"))

        # Assignments
        TenantService.create_full_assignments(db, school.id, classes, subjects, teachers)

        # Students
        TenantService.create_students(db, school.id, classes, school.school_code)

        # Tuition Scaffold
        TenantService.create_tuition_scaffold(db, school.id)

        db.commit()
        db.refresh(school)
        return school

    @staticmethod
    def create_setup_teachers(db: Session, school_id: int, domain: str) -> List[User]:
        teacher_data = [
            {"first": "Ayaan", "last": "Hassan", "qual": "B.Ed Languages, University of Hargeisa", "subjects": ["SOM", "HIS"], "dept_head": True},
            {"first": "Mohamed", "last": "Ali", "qual": "B.Sc Mathematics, University of Somalia", "subjects": ["MAT"], "dept_head": True},
            {"first": "Fatima", "last": "Yusuf", "qual": "B.Ed Islamic Studies, Mogadishu University", "subjects": ["ISL"], "dept_head": False},
            {"first": "Ahmed", "last": "Nur", "qual": "B.Sc Physics, University of Hargeisa", "subjects": ["PHY"], "dept_head": False},
            {"first": "Khadija", "last": "Omar", "qual": "B.Sc Chemistry, Amoud University", "subjects": ["CHE"], "dept_head": False},
            {"first": "Yusuf", "last": "Ismail", "qual": "B.Sc Biology, University of Somalia", "subjects": ["BIO"], "dept_head": False},
            {"first": "Hassan", "last": "Adan", "qual": "B.Ed English, University of Hargeisa", "subjects": ["ENG"], "dept_head": False},
            {"first": "Maryam", "last": "Farah", "qual": "B.Ed Arabic, Mogadishu University", "subjects": ["ARB"], "dept_head": False},
        ]

        teachers = []
        for data in teacher_data:
            email = f"{data['first'].lower()}.{data['last'].lower()}@{domain}"
            # Check if teacher exists
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                teachers.append(existing)
                continue

            teacher = User(
                school_id=school_id,
                email=email,
                password_hash=hash_password("Teach@2026"),
                role="teacher",
                first_name=data["first"],
                last_name=data["last"],
                qualifications=data["qual"],
                designation=f"Senior Teacher ({', '.join(data['subjects'])})",
                is_department_head=data["dept_head"],
                staff_identifier=TenantService.generate_staff_id("NE-TID"),
            )
            db.add(teacher)
            teachers.append(teacher)

        db.flush()
        return teachers

    @staticmethod
    def create_full_assignments(db: Session, school_id: int, classes: List[SchoolClass],
                                subjects: List[Subject], teachers: List[User]):
        for school_class in classes:
            for subject in subjects:
                if subject.level == school_class.class_level:
                    code = subject.code.split("-")[0]
                    teacher = None
                    for t in teachers:
                        if code in ["SOM", "HIS"] and t.first_name == "Ayaan":
                            teacher = t
                            break
                        elif code == "MAT" and t.first_name == "Mohamed":
                            teacher = t
                            break
                        elif code == "ISL" and t.first_name == "Fatima":
                            teacher = t
                            break
                        elif code == "PHY" and t.first_name == "Ahmed":
                            teacher = t
                            break
                        elif code == "CHE" and t.first_name == "Khadija":
                            teacher = t
                            break
                        elif code == "BIO" and t.first_name == "Yusuf":
                            teacher = t
                            break
                        elif code == "ENG" and t.first_name == "Hassan":
                            teacher = t
                            break
                        elif code == "ARB" and t.first_name == "Maryam":
                            teacher = t
                            break
                    if not teacher:
                        teacher = teachers[0]

                    existing_assign = db.query(TeachingAssignment).filter_by(
                        school_id=school_id,
                        teacher_id=teacher.id,
                        class_id=school_class.id,
                        subject_id=subject.id
                    ).first()
                    if not existing_assign:
                        assignment = TeachingAssignment(
                            school_id=school_id,
                            teacher_id=teacher.id,
                            class_id=school_class.id,
                            subject_id=subject.id,
                        )
                        db.add(assignment)

    @staticmethod
    def create_students(db: Session, school_id: int, classes: List[SchoolClass], school_code: str):
        rng = random.Random(20260830 + school_id)
        male_names = ["Ahmed", "Mohamed", "Yusuf", "Omar", "Hassan", "Ali", "Abdullahi", "Mustafa", "Guled", "Khadar"]
        female_names = ["Amina", "Fatima", "Khadija", "Maryam", "Hodan", "Sagal", "Ubax", "Filsan", "Nasra", "Sumaya"]
        last_names = ["Nur", "Hassan", "Ali", "Hussein", "Adan", "Farah", "Ismail", "Warsame", "Osman", "Jama", "Dahir"]

        for school_class in classes:
            roster_size = 6 + (school_class.class_level % 4)
            for _ in range(roster_size):
                if rng.random() > 0.5:
                    first_name = rng.choice(male_names)
                    gender = "Male"
                else:
                    first_name = rng.choice(female_names)
                    gender = "Female"
                last_name = rng.choice(last_names)

                next_seq = TenantService.get_next_roll_number(db, school_id)
                roll_number = f"{school_code}-{next_seq}"
                
                student = Student(
                    school_id=school_id,
                    national_student_id=roll_number,
                    roll_number=roll_number,
                    first_name=first_name,
                    last_name=last_name,
                    gender=gender,
                    class_id=school_class.id,
                    is_active=True,
                )
                db.add(student)

    @staticmethod
    def get_next_roll_number(db: Session, school_id: int) -> int:
        # Transaction-safe sequence counter
        seq = db.query(SchoolRollSequence).filter(
            SchoolRollSequence.school_id == school_id
        ).with_for_update().first() if "sqlite" not in str(db.bind.url) else db.query(SchoolRollSequence).filter(
            SchoolRollSequence.school_id == school_id
        ).first()

        if not seq:
            seq = SchoolRollSequence(school_id=school_id, next_value=10000)
            db.add(seq)
            db.flush()

        current = seq.next_value
        seq.next_value += 1
        db.flush()
        return current

    @staticmethod
    def update_roll_sequence(db: Session, school_id: int, new_next_value: int) -> SchoolRollSequence:
        seq = db.query(SchoolRollSequence).filter(SchoolRollSequence.school_id == school_id).first()
        if not seq:
            raise HTTPException(status_code=404, detail="School roll sequence record not found")
        
        if new_next_value < seq.next_value:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot decrement roll number sequence. Current value is {seq.next_value}, requested {new_next_value}"
            )
        
        seq.next_value = new_next_value
        db.commit()
        db.refresh(seq)
        return seq

    @staticmethod
    def create_tuition_scaffold(db: Session, school_id: int):
        for level in range(1, 13):
            existing = db.query(TuitionRate).filter_by(
                school_id=school_id,
                class_level=level,
                term="Term 1"
            ).first()
            if not existing:
                base_fee = 80.0 + (level * 5.0)
                rate = TuitionRate(
                    school_id=school_id,
                    class_level=level,
                    term="Term 1",
                    amount=base_fee,
                )
                db.add(rate)

    @staticmethod
    def generate_staff_id(prefix: str) -> str:
        rng = random.SystemRandom()
        year = "2026"
        letters = "".join(rng.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=2))
        digits = "".join(rng.choices("0123456789", k=3))
        return f"{prefix}-{year}-{letters}{digits}"
