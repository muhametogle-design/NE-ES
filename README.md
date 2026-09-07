# NE-EMIS - Private School Management & State Compliance Monitoring System

A multi-tenant SaaS for privately-owned schools in the North-East education network (Somaliland/Somalia) with a state-side oversight portal.

## System Architecture

NE-EMIS consists of two primary operational domains:
1. **School Tenant Operations**: Private school portal for enrollment, attendance, substitutions, syllabus pacing, student biometrics (WebAuthn/FIDO2), report cards, and private tuition billing.
2. **State Ministry Oversight**: Oversight center for institution directories, roll sequence control, national student registry lookup, real-time attendance compliance mapping, and automated 15:00 EAT RED ALARM auditing.

### Districts (Regional Education Offices)
Schools can be grouped into state-managed **districts** (`/api/v1/districts`). State roles may list/read
districts (`GET`, filterable by `region`, `is_active`, `q`, paginated); only `state_admin` may create or
update them (`POST`, `PATCH`). District codes are unique and case-insensitive (normalised to upper-case);
`private_schools.district_id` is an optional FK (`ON DELETE SET NULL`).

### Photos and teacher account binding

Student and teacher CRUD accept a nullable `photo_url` string (maximum **500 characters**).
Both absolute storage URLs and relative media paths are stored as supplied; omitting the field
in `PATCH`/partial `PUT` preserves the photo, and sending `null` clears it. Use an external
media/object-store URL or upload a local photo using the endpoint below.

Canonical endpoints are `/api/v1/students`, `/api/v1/teachers`, `/api/v1/subjects`, and
`/api/v1/classrooms`. The existing `/api/v1/school/students`, `/teachers`, `/subjects`, and
`/classes` routes remain available and share the **same handlers and authorization**.

A **Teacher** is now a staff profile with an optional one-to-one system **User** binding.
`Teacher.id` and `User.id` are independent; `user_id` is an indexed, nullable foreign key with
`ON DELETE SET NULL`. It deliberately uses **INTEGER**, matching this repository's existing
`users.id` (a UUID FK to that column would not work on PostgreSQL). Login and `/api/auth/me`
responses include `teacher_id` and `photo_url`; never use a User ID as a Teacher ID. Teaching
assignments, timetables, absences, and substitutions use Teacher IDs; attendance markers and
syllabus progress authors remain User IDs for audit attribution.

Only school managers can create, bind, update, or deactivate teacher profiles. Creation supports
three account modes, plus the existing flat `email`/`password` payload:

- **No account:** provide profile fields only. A teacher can be assigned courses before getting a login.
- **Manual binding:** include `user_id` for an active, teacher-role User in the same school that is
  not already linked to another profile.
- **Provision a login atomically:** include `create_user` credentials. The server fixes the role to
  `teacher` and the tenant to the manager's school. Passwords are hashed and never in profile responses.

```json
{
  "first_name": "Amina",
  "last_name": "Nur",
  "photo_url": "/media/teachers/amina.jpg",
  "create_user": {
    "email": "amina@example.org",
    "password": "Use-a-strong-unique-password"
  }
}
```

Account modes cannot be combined. `PATCH /api/v1/teachers/{id}` with `user_id: null` unlinks
an account; rebinding transfers permissions immediately without changing the profile's assignments.
Deleting a User also unlinks the profile without deleting its photos or academic history. Deactivating
a teacher revokes their academic scope without deleting the login. Profile contact email is not a
login-email change; linked account passwords, roles, and tenants cannot be changed through profile updates.

**Teacher scope:** subject/class lists contain only explicit `TeachingAssignment` grants through
an active `Teacher.user_id` binding. Detail reads and updates of another teacher's resources in the
same school return **403**; unknown/foreign-school resources return **404**. An unbound or inactive
profile gets empty lists and no academic write authority. Nested classroom subjects, student rosters,
timetables, grade/attendance reads, syllabus progress, and academic summaries use the same scope.
Grade and attendance writes require the **exact class–subject pair**, and every student in a batch
must belong to that class and school before any record changes. Manager-confirmed substitutions
permit live attendance only for their specific date and timetable slot, not general subject access.
Teachers cannot self-grant assignments, provision accounts, create/delete subjects, create classes,
or manage timetables/substitutions. Managers retain school-wide administrative access.

Run `alembic upgrade head` **before starting an existing deployment**. Revision `83dda6195453`
backfills legacy staff profiles, preserves public teacher IDs and operational records, and names all
new/replaced constraints explicitly. SQLite uses batch table rebuilds; live application and test
connections enforce foreign keys. Downgrading requires linking any assigned, unbound teachers first,
because the old schema cannot represent them. If using the optional SQL analytics views, reapply
`sql/003_analytics_views.sql` after upgrading so workload reporting uses teacher profiles.

### Local photo uploads

`POST /api/v1/media/upload` accepts a multipart `file` from an authenticated school manager
or teacher. Allowed declared MIME types are `image/jpeg`, `image/png`, and `image/webp`.
The file must be non-empty and at most **5 MB (5 × 1024 × 1024 bytes)**; unsupported types,
empty files, and oversized payloads return **400** without saving a photo. Missing `file`
returns **422**; unauthenticated uploads return **401**.

Successful uploads return **201 Created** with a URL that can be sent directly to student
or teacher CRUD as `photo_url`:

```json
{"photo_url": "/static/photos/9de7b18f2f1f4dd8b8e438708083a225.jpg"}
```

Files are saved under `uploads/photos/` (relative to the backend's working directory),
created automatically at startup. UUID filenames and MIME-derived extensions avoid exposing
or trusting client filenames. `/static` serves the `uploads` directory before the SPA catch-all;
the frontend's Vite development server proxies `/static` to the API as well.
**Static URLs are public to anyone with the link**, not subject to student/teacher read scoping;
store only intended public photos there, never private records or other sensitive files. Uploading
does not itself attach a photo to a profile or bypass the profile's existing write permissions.
The handler checks MIME and size, but does not decode, re-encode, or scan image contents.

`uploads/` is excluded from Git and Docker build contexts. Docker Compose persists it in the
`photo_uploads` volume; other deployments should provision persistent storage and backups for it.
Configure an appropriate reverse-proxy request-body limit as well: multipart parsing may spool
large requests to temporary disk before the endpoint can validate their payload size.

### Fingerprint templates
The fingerprint API is separate from the existing `/api/v1/school/biometrics` WebAuthn flow:

- `POST /api/v1/biometrics/enroll` accepts an integer `student_id`, Base64 `template_data`, and
  optional `finger_position` (default `RIGHT_INDEX`), `template_format` (default `ISO_19794_2`),
  `quality_score` (0–100), and `device_model`. It returns **201** with a UUID enrollment ID,
  metadata, and timestamps, but **never returns the stored template**.
- `POST /api/v1/biometrics/verify` accepts an integer `school_id`, `template_data`, and optional
  `template_format` and `finger_position`. It returns **200** with `verified`, `message`, and
  `student_id`, `student_name`, and `roll_number` (null unless a unique active student matches).
- Both endpoints require an authenticated school manager or teacher. Enrollment is limited to
  students in that user's school (unknown and foreign-school students both return **404**).
  Verification against another school is rejected with **403**; state roles cannot use these endpoints.

**Matching limitation:** this version performs exact-template 1:N lookup using canonical Base64
and the same template format, not fingerprint similarity matching. Duplicate matches for different
active students fail closed. Fresh scans, ISO/ANSI structure validation, and liveness detection
require a compatible fingerprint-matcher SDK; this API is not proof of a live fingerprint scan.
Templates must be non-empty standard Base64, at most 64 KiB encoded, and are sensitive data stored
in the database—apply appropriate database access and encryption controls in deployment.

### Key Business Constraints Enforced
- **Strict Financial Firewall**: State roles (`state_admin`, `inspector`) are blocked from accessing private tuition rates, invoices, or payment transactions. Every blocked attempt is recorded in the append-only `security_audit_log`.
- **Immutable National Roll Numbers**: Student roll numbers format (`{school_code}-{next_value}`) are immutable upon creation.
- **Roll Sequence Counter**: State Admins can advance the next sequence value, but decrementing or reusing issued roll numbers is prohibited.
- **Attendance Authority & RBAC**: Teachers can only mark attendance and submit grades for explicitly assigned class–subject pairs. Confirmed substitutions grant date/slot-limited live attendance access; School Managers retain administrative override.
- **Encrypted Disaster Recovery**: Snapshot backups are encrypted via AES-256-GCM with SHA-256/MD5 cryptographic digests.
- **Data Saver Mode**: Network-aware UI mode (off/auto/on) that strips heavy animations and replaces complex visual charts with raw text metrics.

---

## Quick Start

### 1. Backend Setup
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .\.venv\Scripts\Activate.ps1 on Windows

# Install dependencies
pip install -r requirements-dev.txt

# Configure the database (optional — defaults to SQLite at ./data/schoolsystem.db)
cp .env.example .env
# For a local PostgreSQL instance, set in .env:
#   DATABASE_URL=postgresql+psycopg2://postgres:12345@localhost:5432/ne_es_dev
# and create the database once:
#   psql -U postgres -h localhost -c "CREATE DATABASE ne_es_dev;"

# Apply schema migrations (alembic/env.py loads DATABASE_URL from .env)
alembic upgrade head

# Seed default records (state admins, 5 school tenants, managers/teachers, demo data)
python -m scripts.seed          # idempotent; add --reset to wipe a local SQLite file first

# Start Backend Server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup (React)
```bash
cd web
npm install
npm run build
# For local dev:
npm run dev
```

### 3. Running Automated Tests
```bash
pytest
```
The suite runs against an isolated in-memory SQLite database. `tests/conftest.py` sets
`APP_ENV=test`, which makes the API lifespan skip schema initialisation and demo seeding,
so `pytest` never touches the database configured in `.env` (e.g. `ne_es_dev`).
`tests/test_teacher_scoping.py` covers photo CRUD, account provisioning/binding, permission
revocation and subject/class isolation using intentionally different User/Teacher IDs.
Migration tests exercise SQLite upgrade/downgrade with existing academic history and verify
PostgreSQL upgrade/downgrade SQL generation without requiring a PostgreSQL server.

---

## Default Credentials

| Role | Email | Password | Staff Identifier | Default PIN |
|---|---|---|---|---|
| **State Admin** | `stateadmin@education.gov` | `StateAdmin@2026` | `NE-ADM-2026-HQ001` | `1234` |
| **Inspector** | `inspector@education.gov` | `State@2026` | `NE-INS-2026-HQ002` | `1234` |
| **Ilays Manager** | `manager@ilays.edu.so` | `School@2026` | `NE-MID-2026-...` | `1234` |
| **Ilays Teacher** | `ayaan.hassan@ilays.edu.so` | `Teach@2026` | `NE-TID-2026-...` | `1234` |
| **Nugaal Manager** | `manager@nugaal.edu.so` | `School@2026` | `NE-MID-2026-...` | `1234` |
| **Nugaal Teacher** | `ayaan.hassan@nugaal.edu.so` | `Teach@2026` | `NE-TID-2026-...` | `1234` |

---

## Pre-provisioned Private School Tenants

| Code | School Name | License | Proprietor | Address |
|---|---|---|---|---|
| **IL** | Ilays Educational Academy | `SOL/PS/2026/IL01` | Halima Farah | Masalaha Quarter, Laascaanood |
| **MY** | Muse Yusuf Secondary School | `SOL/PS/2026/MY02` | Abdisalam Nur | Boameh Street, Laascaanood |
| **NG** | Nugaal High School | `SOL/PS/2026/NG03` | Deqa Hersi | Airport Road, Laascaanood |
| **AQ** | ALQALAM SCHOOLS | `SOL/PS/2026/AQ04` | Muna Jama | Xero Awr, Laascaanood |
| **LB** | Las Anod Boarding Secondary School (LBSS) | `SOL/PS/2026/LB05` | Warsame Adan | Jireeye Road, Laascaanood |

---

## Docker Deployment

```bash
docker-compose up --build
```
The application will bind to `http://0.0.0.0:8000`.
