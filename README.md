# NE-EMIS — Education Management Information System

Full-stack school management application: **FastAPI** (JWT auth, students, billing) + **React/Vite/Tailwind/Framer Motion** glassmorphism UI, containerized for **Docker** and **VS Code Dev Containers**.

## Folder hierarchy

```
NE-ES/
├── Dockerfile                       # Python 3.11 + Node 20 image; EXPOSE 8000, 5173
├── docker-compose.yml               # app (FastAPI) + web (Vite) + optional db (Postgres)
├── requirements.txt                 # Backend pinned dependencies
├── .env.example                     # Environment template (copy to .env)
├── .gitignore
├── .devcontainer/
│   ├── devcontainer.json            # Compose-targeted dev container, ports 8000/5173
│   └── post-create.sh               # Installs Python + npm deps on container create
│
├── app/                             # ── Backend (FastAPI) ─────────────────────
│   ├── __init__.py
│   ├── main.py                      # App factory, CORS, routers, lifespan, seed admin
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # pydantic-settings (NE_EMIS_* env vars)
│   │   ├── database.py              # SQLAlchemy engine/session, Base, get_db, init_db
│   │   └── security.py              # passlib bcrypt hashing + JWT create/decode
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                  # User + UserRole enum
│   │   ├── student.py               # Student (admission, grade, guardian…)
│   │   └── finance.py               # Invoice, Payment, FeeType, status enums
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                  # Token / UserRead / LoginRequest
│   │   ├── student.py               # Student CRUD + paginated list
│   │   └── finance.py               # Invoice/Payment + FinanceSummary
│   └── api/
│       ├── __init__.py
│       ├── deps.py                  # OAuth2PasswordBearer, get_current_user, role guard
│       ├── auth.py                  # /auth/login (form + JSON), /me, /register
│       ├── students.py              # /students CRUD, search, filters, pagination
│       └── finance.py               # /finance/invoices, /payments, /summary, charts
│
└── web/                             # ── Frontend (React + Vite) ────────────────
    ├── package.json                 # framer-motion, lucide-react, axios, router
    ├── vite.config.js               # host 0.0.0.0:5173, /api → :8000 proxy
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    ├── .eslintrc.cjs
    ├── .prettierrc
    ├── public/
    │   └── favicon.svg
    └── src/
        ├── main.jsx                 # React root + AuthProvider + BrowserRouter
        ├── App.jsx                  # Routes + ProtectedRoute
        ├── index.css                # Tailwind + glassmorphism component classes
        ├── api/
        │   └── client.js            # Axios instance: Bearer injection, 401 interceptor
        ├── context/
        │   └── AuthContext.jsx      # useAuth(): login/logout/user/token
        ├── components/
        │   ├── Layout.jsx           # Glass sidebar shell + responsive mobile drawer
        │   ├── ProtectedRoute.jsx   # Auth gate, redirects to /login
        │   └── ui.jsx               # KpiCard, Modal, Spinner, StatusBadge, EmptyState
        └── pages/
            ├── Login.jsx            # Glassmorphic JWT login
            ├── Dashboard.jsx        # Animated KPI cards + revenue bar chart
            ├── Students.jsx         # Directory table, filters, create/edit modal
            └── Finance.jsx          # Billing ledger, invoice + payment modals
```

## Quick start

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env          # optional: tweak secrets / DATABASE_URL
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs:  http://localhost:8000/docs
- Postgres (optional): `docker compose --profile db up -d db`, then switch
  `NE_EMIS_DATABASE_URL` to `postgresql+psycopg://neemis:neemis@db:5432/neemis`.

### Option B — VS Code Dev Container

1. Open the repo in VS Code with the **Dev Containers** extension.
2. **Reopen in Container** — the `app` service is used; ports **8000** and
   **5173** are forwarded automatically, Python/React/Tailwind extensions install,
   and `postCreateCommand` provisions both toolchains.
3. In the container terminal: `uvicorn app.main:app --reload --port 8000`
   and (in another terminal) `cd web && npm run dev`.

### Option C — Local run

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd web
npm install
npm run dev      # http://localhost:5173 (proxies /api → http://127.0.0.1:8000)
```

## Default credentials

Seeded automatically on first boot (override via env vars):

| Email              | Password   | Role  |
| ------------------ | ---------- | ----- |
| `admin@neemis.edu` | `admin1234`| admin |

> Change the password and `NE_EMIS_SECRET_KEY` before deploying.

## API overview (all under `/api`)

| Method   | Path                        | Description                          |
| -------- | --------------------------- | ------------------------------------ |
| POST     | `/auth/login`               | OAuth2 form login → JWT              |
| POST     | `/auth/login/json`          | JSON login                           |
| GET      | `/auth/me`                  | Current user                         |
| POST     | `/auth/register`            | Create staff user (admin)            |
| GET/POST | `/students`                 | List (search/grade/status/paginate) / create |
| GET/PATCH/DELETE | `/students/{id}`   | Read / update / delete               |
| GET      | `/finance/summary`          | Billing KPIs                         |
| GET      | `/finance/revenue/monthly`  | 6-month billed vs collected          |
| GET/POST | `/finance/invoices`         | List / create invoices               |
| PATCH/DELETE | `/finance/invoices/{id}` | Update / void                        |
| GET/POST | `/finance/payments`         | Recent payments / record payment     |

## Database migrations (Alembic)

Schema changes are managed by Alembic. `alembic/env.py` imports
`Base.metadata` from `app.core.database` plus all model modules
(`app.models.user`, `app.models.student`, `app.models.finance`) and resolves the
database URL from `NE_EMIS_DATABASE_URL`/`DATABASE_URL` or
`app.core.config.settings` — nothing is hard-coded in `alembic.ini`.

```bash
alembic upgrade head                          # apply migrations
alembic revision --autogenerate -m "change"   # generate a new migration
alembic downgrade -1                          # roll back one step
alembic current / alembic history
```

The baseline migration (`alembic/versions/0001_baseline_schema.py`) creates the
`users`, `students`, `invoices` and `payments` tables with indexes, foreign keys
and enums. The dev container runs `alembic upgrade head` automatically in
`postCreateCommand`; production deployments must run it before the first boot
(the app skips `create_all` when `NE_EMIS_ENV=production` and refuses to serve
an un-migrated database).

## Production security hardening

| Control | Behavior |
| --- | --- |
| Secret-key validation | With `NE_EMIS_ENV=production`, startup fails unless `NE_EMIS_SECRET_KEY` is ≥32 chars and not a known weak/placeholder value (`admin1234`, `change-me`, `insecure`, …). Generate with `openssl rand -hex 32`. |
| CORS lockdown | Production rejects wildcard (`*`) and non-`https` origins; only origins in `NE_EMIS_CORS_ORIGINS` are reflected in `Access-Control-Allow-Origin`. |
| Security headers | Every response carries `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `Content-Security-Policy: default-src 'self'` (dev uses an HMR/fonts-tolerant CSP) and `Referrer-Policy`. |
| Login rate limiting | `/api/auth/login` and `/api/auth/login/json` are limited to **5 attempts/minute/IP** via slowapi (`NE_EMIS_LOGIN_RATE_LIMIT`); breaches return HTTP 429 with `Retry-After` + `X-RateLimit-*` headers. Run uvicorn with `--proxy-headers` behind a reverse proxy so client IPs are read from `X-Forwarded-For`. |
| Schema discipline | Production disables auto-`create_all`; Alembic is the single source of truth for the schema. |

Minimal production environment:

```bash
NE_EMIS_ENV=production
NE_EMIS_SECRET_KEY=$(openssl rand -hex 32)
NE_EMIS_DATABASE_URL=postgresql+psycopg://neemis:***@db:5432/neemis
NE_EMIS_CORS_ORIGINS='["https://emis.yourschool.edu"]'
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
```

## Architecture notes

- **Auth**: `OAuth2PasswordBearer` issues HS256 JWTs (`python-jose`); passwords
  hashed with bcrypt via `passlib`. The Axios client auto-attaches
  `Authorization: Bearer <token>` and redirects to `/login` on 401.
- **Database**: SQLAlchemy 2.0 ORM, SQLite by default (zero config) — swap
  `NE_EMIS_DATABASE_URL` to PostgreSQL without code changes.
- **CORS**: enabled for `http://localhost:5173` (configurable via
  `NE_EMIS_CORS_ORIGINS` JSON array).
- **UI design system**: glassmorphism panels (`backdrop-blur-md bg-white/80`),
  `lucide-react` icons, Framer Motion `whileHover={{ scale: 1.02, y: -4 }}`
  micro-interactions on KPI cards/buttons, spring modals and staggered tables.
