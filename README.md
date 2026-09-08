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

### Photos, teacher profiles & subject-level scoping
Portraits and staff identity are handled by three cooperating pieces:

- **Photo storage** — `students.photo_url`, `teachers.photo_url` and `users.photo_url`
  (`VARCHAR(500)`, nullable) store a *location*, never image bytes: either an absolute
  `https://` URL or a local `/media/...` path. Values are validated by
  `app/schemas/media.py` (http(s) or root-relative only — `data:` URIs, protocol-relative
  `//host` URLs, traversal segments and over-long strings are rejected with `422`).
  `POST /api/v1/media/upload` (multipart `file`, JPEG/PNG/WEBP/GIF, ≤ `MAX_UPLOAD_SIZE_MB`,
  magic-byte sniffed, stored under a UUID filename) returns the `photo_url` to attach;
  files are served back from `/media/...`. Uploads require a school-tenant login, reads are
  unauthenticated so plain `<img>` tags work. The portrait of a staff profile and of its
  bound login account are kept in sync by `TeacherService.sync_photo`.
- **Teacher ↔ user binding** — `teachers` is the staff profile; `teachers.user_id`
  (unique, indexed, `ON DELETE SET NULL`) binds it to the login account
  (`users.role = "teacher"`). `POST /api/v1/teachers` provisions the account **and** the
  profile in one call (`auto_provision_user`, default true, always `role="teacher"`),
  `link_user_id` / `POST /api/v1/teachers/{id}/link-user` bind an existing account,
  `auto_provision_user=false` records staff before any account exists, and
  `POST /api/v1/teachers/me` auto-links a profile to the caller's own account.
  Deleting a login leaves the staff record (and its photo) intact with `user_id = NULL`.
- **Subject-level scoping** — `teacher_subjects` (many-to-many `teachers` ↔ `subjects`)
  records which subjects a teacher owns. A teacher's visible scope is the union of those
  rows and their class-level `teaching_assignments`, resolved through
  `Teacher.user_id == current_user.id` by `app/services/teacher_scope.py`.

| Endpoint | Manager | Teacher |
|---|---|---|
| `GET /api/v1/subjects` | all subjects of the tenant | **only assigned subjects** |
| `GET /api/v1/subjects/{id}`, `/mine`, `/{id}/teachers` | tenant-wide | assigned only, otherwise **403** |
| `PATCH /api/v1/subjects/{id}` | any subject | only subjects they own |
| `POST`/`DELETE /api/v1/subjects`, roster writes | ✅ | **403** |
| `GET /api/v1/classrooms` (+ `/{id}`, `/subjects`, `/students`) | all classrooms | **only assigned classrooms** (incl. confirmed substitutions) |
| `POST`/`PATCH`/`DELETE /api/v1/classrooms` | ✅ | **403** |
| `GET /api/v1/teachers` | all staff profiles | own profile only |
| `PATCH /api/v1/teachers/{id}` | any field | own `photo_url`, `phone`, `bio` only |
| `POST /api/v1/teachers`, `/{id}/link-user`, `PUT /{id}/subjects`, `DELETE /{id}` | ✅ | **403** |

Another teacher's subject/classroom inside the same tenant answers **403**; another tenant's
answers **404**. The legacy `/api/v1/school/subjects`, `/api/v1/school/classes` and
`/api/v1/school/teachers` endpoints apply the same scoping, and teacher writes there are now
limited to their own record. Grade entry and attendance marking keep using
`AcademicService.check_teacher_authority` (class + subject assignment or a confirmed
substitution).

Migration `0a3d991221bb` (`add_photos_and_teacher_user_scoping`) adds the columns/tables with
`batch_alter_table` and explicit constraint names for SQLite/PostgreSQL parity, and backfills
a profile plus subject mappings for every existing teacher account (idempotent — also run by
`python -m scripts.seed`).

### Key Business Constraints Enforced
- **Strict Financial Firewall**: State roles (`state_admin`, `inspector`) are blocked from accessing private tuition rates, invoices, or payment transactions. Every blocked attempt is recorded in the append-only `security_audit_log`.
- **Immutable National Roll Numbers**: Student roll numbers format (`{school_code}-{next_value}`) are immutable upon creation.
- **Roll Sequence Counter**: State Admins can advance the next sequence value, but decrementing or reusing issued roll numbers is prohibited.
- **Attendance Authority & RBAC**: Teachers can only mark attendance and submit grades for assigned courses or confirmed substitutions; `/api/v1/subjects` and `/api/v1/classrooms` are filtered to the same assignments, teacher writes are limited to the subjects they own, and School Managers retain administrative override.
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
