# NE-EMIS - Private School Management & State Compliance Monitoring System

A multi-tenant SaaS for privately-owned schools in the North-East education network (Somaliland/Somalia) with a state-side oversight portal.

## System Architecture

NE-EMIS consists of two primary operational domains:
1. **School Tenant Operations**: Private school portal for enrollment, attendance, substitutions, syllabus pacing, student biometrics (WebAuthn/FIDO2), report cards, and private tuition billing.
2. **State Ministry Oversight**: Oversight center for institution directories, roll sequence control, national student registry lookup, real-time attendance compliance mapping, and automated 15:00 EAT RED ALARM auditing.

### Key Business Constraints Enforced
- **Strict Financial Firewall**: State roles (`state_admin`, `inspector`) are blocked from accessing private tuition rates, invoices, or payment transactions. Every blocked attempt is recorded in the append-only `security_audit_log`.
- **Immutable National Roll Numbers**: Student roll numbers format (`{school_code}-{next_value}`) are immutable upon creation.
- **Roll Sequence Counter**: State Admins can advance the next sequence value, but decrementing or reusing issued roll numbers is prohibited.
- **Attendance Authority & RBAC**: Teachers can only mark attendance and submit grades for assigned courses or confirmed substitutions; School Managers retain administrative override.
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

# Initialize & Seed Demo Database
python -m scripts.seed_data --reset

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

---

## Database (PostgreSQL 16)

The application talks to PostgreSQL 16 through **psycopg2**. Copy the template
and point it at your server:

```bash
cp .env.example .env
```

```dotenv
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ne_es_dev
```

`postgres://…` and `postgresql://…` (Heroku/Render/Fly/Supabase style) are
accepted and rewritten to `postgresql+psycopg2://…` automatically. If you prefer
discrete parts, leave `DATABASE_URL` unset and fill in `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and
`POSTGRES_SSLMODE` — the URL is composed for you. When nothing is configured at
all, development/test environments fall back to
`sqlite:///./data/schoolsystem.db`; `APP_ENV=production` refuses SQLite.

**Passwords must be percent-encoded** (`%40` for `@`, `%25` for `%`).

### Connection layout

| Concern | Where |
|---|---|
| URL resolution, validation, environment rules | `app/core/config.py` |
| Engine, pooling, `SessionLocal`, `get_db()` | `app/db/session.py` |
| Compatibility shims for older imports | `app/core/db.py`, `app/core/database.py` |
| Migration target URL + metadata registry | `alembic/env.py` |

Runtime pooling (PostgreSQL only): `pool_size=10`, `max_overflow=20`,
`pool_pre_ping=True`, `pool_recycle=1800`, `pool_timeout=30` — all overridable
via `DB_*` environment variables. Migrations use `NullPool` (short-lived).

### Migrations

```bash
alembic upgrade head          # apply
alembic revision --autogenerate -m "add foo"   # generate from ORM models
alembic downgrade -1
alembic upgrade head --sql    # offline SQL (no connection needed)
```

`alembic/env.py` reads the URL from `app.core.config.settings` at runtime and
registers **every** model on the single declarative base
(`app.models.base.Base`), so autogenerate sees the whole schema.

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
