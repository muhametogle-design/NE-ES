# NE-EMIS — Local Runbook (Docker + Native, VS Code)

> Every command in this runbook was executed and verified against this repository.
> Stack: **FastAPI (Uvicorn, :8000)** · **React 18 + Vite 5 (:5173)** · **PostgreSQL 16 / SQLite** · **Alembic**.

---

## ⚠️ Read first — corrections vs. common assumptions

| Assumption | Reality in this repo (verified) |
|---|---|
| Login `admin@neemis.edu` / `admin1234` | ❌ **Does not exist.** `POST /api/auth/login` returns *"Invalid credentials"*. Use **`stateadmin@education.gov` / `StateAdmin@2026`** (see [§4](#4-endpoints--credentials)). |
| Vite dev server runs on 5173 by default | Repo pins **port 3000** in `web/vite.config.js`. Run `npm run dev -- --port 5173` to get 5173 (used throughout this runbook). |
| Docker Compose has a frontend service on 5173 | Compose runs only `postgres` + `api`. The API container **builds the React app and serves it on :8000** (`http://localhost:8000`). Port 5173 exists only in the native dev workflow. |
| `alembic upgrade head` works on a fresh clone | Fails with `unable to open database file` — the SQLite `data/` dir doesn't exist yet. **Run `mkdir -p data` first.** |
| Run Alembic any time | If the API booted first (it auto-creates all tables via `create_all`), `upgrade head` fails with *"table already exists"*. Use **`alembic stamp head`** instead, or run migrations **before** first boot. |

---

## 0. Prerequisites

| Tool | Version verified |
|---|---|
| Python | 3.11.x |
| Node.js | 20.x / 22.x |
| Docker Engine + Compose v2 | `docker compose version` |
| VS Code | with **Python**, **Pylance**, **Docker** extensions (repo ships `.vscode/extensions.json` — VS Code will prompt to install them) |

---

## 1A. Path A — Full stack with Docker Compose (background)

```bash
cd NE-ES

# Build images and start the whole stack detached (postgres + api)
docker compose up --build -d

# Watch the API until you see "Application startup complete."
docker compose logs -f api          # Ctrl+C to stop following (stack keeps running)

# Confirm both services are Up
docker compose ps
```

What happens inside: the `api` image installs Python deps + Node 20, builds the React app (`web/dist`), starts Uvicorn on 8000; on boot it creates the schema (`create_all`), **auto-seeds demo data** (`AUTO_SEED_DEMO=true`), and serves the SPA.

**Verify:**

```bash
curl http://localhost:8000/api/health     # → {"status":"healthy","service":"NE-EMIS",...}
curl -I http://localhost:8000/docs        # → 200 (Swagger UI)
curl -I http://localhost:8000/            # → 200 (React SPA served by FastAPI)
```

**Endpoints (Docker mode):**

| What | URL |
|---|---|
| Web application (SPA) | <http://localhost:8000> |
| Swagger docs | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Postgres | `localhost:5432` — user/pass/db `schoolsystem` |

**Teardown / reset:**

```bash
docker compose down                  # stop, keep data
docker compose down -v               # stop and wipe the postgres volume (full reset)
```

---

## 1B. Path B — Native dev in VS Code (Uvicorn :8000 + Vite :5173 side-by-side)

Open the repo in VS Code: `code NE-ES`, then the integrated terminal (Ctrl+`).

### Terminal 1 — Backend

```bash
cd NE-ES

python -m venv .venv
source .venv/bin/activate            # Windows PS: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Migrations (SQLite default: ./data/schoolsystem.db) — mkdir is REQUIRED on a fresh clone
mkdir -p data
alembic upgrade head

# Start the API with hot-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 — Frontend (click the ⊕ split-terminal icon)

```bash
cd NE-ES/web
npm install
npm run dev -- --port 5173 --host      # repo default is 3000; this forces 5173
```

Vite serves the dev UI on **http://localhost:5173** and proxies `/api` → `127.0.0.1:8000` and `/ws` → websocket (already configured in `web/vite.config.js`).

> **One-keystroke alternative:** this repo ships `.vscode/tasks.json` — press **Ctrl/Cmd+Shift+B** → *dev:all (api + web)*, or F5 to debug the backend with breakpoints (`.vscode/launch.json`).

### Optional — native dev against Postgres instead of SQLite

```bash
docker compose up -d postgres                     # just the database
export DATABASE_URL=postgresql+psycopg2://schoolsystem:schoolsystem@localhost:5432/schoolsystem
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 2. Database initialization & verification

### Alembic migrations

```bash
# Native (SQLite)
mkdir -p data
alembic upgrade head          # applies alembic/versions/0001_baseline_schema.py → 30 tables
alembic current               # → 6017c4a7f9d5 (head)

# Against the compose Postgres (run BEFORE the api service boots on a fresh volume)
docker compose up -d postgres
docker compose run --rm api alembic upgrade head
docker compose up -d api

# If the API already booted once (tables exist from create_all), just stamp the revision:
docker compose exec api alembic stamp head
```

### Verify tables

```bash
# PostgreSQL (compose)
docker compose exec postgres psql -U schoolsystem -d schoolsystem -c '\dt'
docker compose exec postgres psql -U schoolsystem -d schoolsystem -c 'select version_num from alembic_version;'

# SQLite (native)
sqlite3 data/schoolsystem.db '.tables'            # or: python -c "import sqlite3;print(*sqlite3.connect('data/schoolsystem.db').execute(\"select name from sqlite_master where type='table'\"))"
```

Expected: **30 tables** (users, private_schools, students, courses, invoices, security_audit_log, …) plus `alembic_version`.

### Seed / reset demo data

```bash
python -m scripts.seed_data            # idempotent — safe to re-run
python -m scripts.seed_data --reset    # deletes the SQLite file and reseeds from scratch
```

The API also **auto-seeds on first boot** when the DB is empty (`AUTO_SEED_DEMO=true` by default).

---

## 3. Endpoints

| What | URL |
|---|---|
| Frontend (native dev) | <http://localhost:5173> |
| Frontend (Docker / built SPA) | <http://localhost:8000> |
| Swagger UI | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Health | <http://localhost:8000/api/health> |

## 4. Endpoints & credentials

> `admin@neemis.edu / admin1234` **does not exist** in this codebase — verified against `POST /api/auth/login`. These are the real seeded accounts (from `app/services/seed.py`):

| Role | Email | Password | PIN |
|---|---|---|---|
| **State Admin** (ministry oversight) | `stateadmin@education.gov` | `StateAdmin@2026` | `1234` |
| Inspector | `inspector@education.gov` | `State@2026` | `1234` |
| School Manager (Ilays) | `manager@ilays.edu.so` | `School@2026` | `1234` |
| Teacher (Ilays) | `ayaan.hassan@ilays.edu.so` | `Teach@2026` | `1234` |
| School Manager (Nugaal) | `manager@nugaal.edu.so` | `School@2026` | `1234` |
| Teacher (Nugaal) | `ayaan.hassan@nugaal.edu.so` | `Teach@2026` | `1234` |

Smoke-test a login from the terminal:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"stateadmin@education.gov","password":"StateAdmin@2026"}'
# → {"access_token":"eyJhbGciOi...","token_type":"bearer",...}
```

⚠️ Login is rate-limited: **5 failed attempts per 5 minutes** (`LOGIN_RATE_LIMIT=5`).

---

## 5. VS Code port forwarding (attached to a container)

The repo ships `.devcontainer/devcontainer.json` (service `api`, `forwardPorts: [8000, 5432]`, runs `alembic upgrade head` + seed on create). When you **Reopen in Container** (or Remote-SSH into a host / attach to the `api` container):

1. In the integrated terminal, start the servers (they must **listen on 0.0.0.0**, not 127.0.0.1 — both this repo's Uvicorn and Vite commands already do).
2. Open the **Ports** panel: Terminal ▸ **Ports** tab (next to Terminal/Output/Problems), or Command Palette (**Ctrl/Cmd+Shift+P**) → **“Ports: Focus on Ports View”**.
3. VS Code auto-detects listening ports and lists them with a `localhost:<port>` forwarding address. Confirm **8000** (API/Swagger/SPA) appears.
4. **Add 5173 manually** — it is not in `forwardPorts` and Vite only registers it once started:
   - In the Ports panel hover the row → **“Forward a Port”** (+), type `5173`, Enter; or
   - Command Palette → **“Forward a Port…”** → `5173`; or
   - Run Vite on 5173 and pick **“Forwarded Ports ▸ Forward Port”** when VS Code detects it; or make it permanent by adding `5173` to `forwardPorts` in `.devcontainer/devcontainer.json`.
5. Hover a forwarded port → click the **🌐 globe icon** to open it in your host browser (`http://localhost:8000/docs`, `http://localhost:5173`). Right-click a port to set **Label**, **Visibility (Private)**, or to **Stop Forwarding**.
6. If a port doesn't appear: make sure the process binds `0.0.0.0` (Vite: pass `--host`; Uvicorn: `--host 0.0.0.0`), and check setting **`remote.autoForwardPorts: true`**.

**Forwarded-port URLs inside the devcontainer:**

| Port | Serves |
|---|---|
| 8000 | API + Swagger (`/docs`) + built SPA |
| 5173 | Vite React dev server (run `npm run dev -- --port 5173` in `/app/web`) |
| 5432 | Postgres (DB tools / psql) |

---

## 6. Troubleshooting quick table

| Symptom | Fix |
|---|---|
| `sqlite3.OperationalError: unable to open database file` during `alembic upgrade head` | `mkdir -p data` first (SQLite dir must exist). |
| Alembic: `table … already exists` | App already ran `create_all`; run `alembic stamp head`. |
| Login fails with the "documented" creds | You're using `admin@neemis.edu` — see §4 for the real ones; mind the 5-attempt rate limit. |
| Vite opens on 3000, not 5173 | `npm run dev -- --port 5173` (config default is 3000). |
| Port already in use | `lsof -i :8000` / `lsof -i :5173` → kill, or choose other ports. |
| `ECONNREFUSED 127.0.0.1:8000` from the browser | In devcontainer/remote contexts, browser-facing code must call the Vite proxy (relative `/api`), never `localhost:8000` directly. |
| Stale demo data | `python -m scripts.seed_data --reset` (SQLite) or `docker compose down -v` (Postgres). |
