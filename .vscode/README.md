# Running NE-EMIS from VS Code

This folder holds the **shared** VS Code configuration for the NE-EMIS system
(FastAPI backend + React/Vite frontend + SQLite/PostgreSQL). It is committed on
purpose so every developer gets the same launchers, tasks, and settings.

| File | Purpose |
|---|---|
| `launch.json` | F5 run/debug configurations (backend, frontend, tests, seeding) |
| `tasks.json` | Build/run/setup tasks (Terminal → Run Task…) |
| `settings.json` | Interpreter, pytest discovery, Tailwind/Prettier, file watchers |
| `extensions.json` | Recommended extensions (VS Code prompts on first open) |

---

## 0. Prerequisites

- **Python 3.11+** (`python --version`)
- **Node.js 20+** with npm (`node --version`) — used to build the React frontend
- VS Code extensions: `ms-python.python`, `ms-python.debugpy`,
  `ms-python.vscode-pylance` (VS Code will offer to install the rest)

## 1. One-time bootstrap

Open the repo root in VS Code, then either:

**A. Task runner (recommended)** — `Terminal → Run Task… → ne-emis: bootstrap`

This runs, in order: create `.venv` → copy `.env.example` to `.env` → install
`requirements-dev.txt` → `npm install` + `npm run build` in `web/` → seed the
demo database (`python -m scripts.seed_data --reset`).

**B. Command line** — same steps by hand:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env               # Windows: copy .env.example .env
cd web && npm install && npm run build && cd ..
python -m scripts.seed_data --reset
```

> On Windows, `settings.json` points the interpreter at
> `${workspaceFolder}/.venv/bin/python`. Select the correct interpreter once via
> `Ctrl+Shift+P → Python: Select Interpreter → .\.venv\Scripts\python.exe`.

## 2. Run the system (F5)

Open **Run and Debug** (`Ctrl+Shift+D`) and pick a configuration:

| Configuration | What it does | URL |
|---|---|---|
| **NE-EMIS: Backend (uvicorn, debug)** | Backend with `--reload`, serving the built SPA and the REST API | http://localhost:8000 |
| NE-EMIS: Backend (no reload) | Same, without the reload watcher — cleanest for breakpoints | http://localhost:8000 |
| **NE-EMIS: Frontend (Vite dev server)** | React dev server with HMR; proxies `/api` and `/ws` to :8000 | http://localhost:3000 |
| **NE-EMIS: Backend + Frontend (compound)** | Bootstraps, then starts both together (`stopAll` kills both) | :8000 and :3000 |
| NE-EMIS: Pytest (tests/) | Debugs the full test suite | — |
| NE-EMIS: Seed demo database (reset) | Wipes + reseeds SQLite demo data | — |
| NE-EMIS: Current Python file | Runs/debugs the active editor file | — |

**Two ways to work:**

- **Production-like** → run *Backend* only and open **http://localhost:8000**.
  FastAPI serves the compiled React bundle from `web/dist` at `/`. Re-run
  `ne-emis: build frontend` after editing anything under `web/src`.
- **Hot-reload frontend dev** → run the *compound* (or both configs) and open
  **http://localhost:3000**. Vite proxies API and WebSocket traffic to the
  backend, so `web/src` changes apply instantly without a rebuild.

Other useful routes:

- Interactive API docs (Swagger): http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health
- Legacy static admin page: http://localhost:8000/admin

## 3. Handy tasks

`Terminal → Run Task…`

| Task | Use |
|---|---|
| `ne-emis: bootstrap` | Fresh clone / after dependency changes |
| `ne-emis: run server (uvicorn)` | Start backend without the debugger |
| `ne-emis: run frontend dev (vite)` | Start Vite dev server only |
| `ne-emis: build frontend` | Rebuild `web/dist` (default **build** task, `Ctrl+Shift+B`) |
| `ne-emis: pytest` | Run the test suite (default **test** task) |
| `ne-emis: seed database (reset)` | Re-create demo tenants, staff, students |
| `ne-emis: alembic upgrade head` | Apply schema migrations |

## 4. Tests

pytest is pre-wired (`python.testing.pytestEnabled`, args `tests`). Test
discoveries show up in the **Testing** view — run or debug individual tests from
there, or use `Ctrl+; Ctrl+A` to run everything.

```bash
.venv/bin/python -m pytest -q
```

## 5. Login credentials (seeded demo data)

| Role | Email | Password |
|---|---|---|
| State Admin | `stateadmin@education.gov` | `StateAdmin@2026` |
| Inspector | `inspector@education.gov` | `State@2026` |
| Ilays Manager | `manager@ilays.edu.so` | `School@2026` |
| Ilays Teacher | `ayaan.hassan@ilays.edu.so` | `Teach@2026` |
| Nugaal Manager | `manager@nugaal.edu.so` | `School@2026` |
| Nugaal Teacher | `ayaan.hassan@nugaal.edu.so` | `Teach@2026` |

Staff PIN for the kiosk/biometric flows: `1234`.

> **Financial firewall:** state roles (`state_admin`, `inspector`) get HTTP 403 on
> tuition/invoice/payment endpoints, and each blocked attempt is appended to
> `security_audit_log`. Log in as a school manager to see Finance.

## 6. Docker / Dev Containers (alternative)

A `.devcontainer` is included for the "Reopen in Container" flow, but it builds on
`docker-compose.yml` and therefore needs **Docker Desktop** running:

```bash
docker compose up --build      # API + Postgres on http://localhost:8000
```

If Docker is unavailable, use the local venv flow in sections 1–2 above — it needs
no containers and is what the tasks in this folder are written for.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'app'` | Wrong interpreter — select `.venv` (see §1). `pytest.ini` sets `pythonpath = .` for tests. |
| Backend serves a blank page at `/` | `web/dist` is missing — run `ne-emis: build frontend`. |
| Port 8000/3000 already in use | Change `--port` in `launch.json`, or kill the stale process. |
| Login fails immediately after start | DB not seeded — run `ne-emis: seed database (reset)`. |
| WebAuthn/biometric enrollment errors | It needs a secure context (`localhost` qualifies; raw LAN IPs do not). Check `WEBAUTHN_RP_ID` / `WEBAUTHN_EXPECTED_ORIGINS` in `.env`. |
| `alembic current` shows nothing | Tables came from `init_db()`; run `alembic stamp head`, then `alembic upgrade head` for future migrations. |
| Vite: `Blocked request. This host (…) is not allowed` | The dev server is behind a proxy/tunnel. `web/vite.config.js` already allows any host in dev; to restrict it set `VITE_ALLOWED_HOSTS=".your-domain.dev,exact.host"` in `.env`. |
| Preview/tunnel shows the Vite server but API calls fail | Vite proxies `/api` and `/ws` to `http://127.0.0.1:8000`, so the **backend must be running too**. Override the target with `VITE_API_PROXY_TARGET` in `.env`. |

### Frontend environment variables (`web/.env` or repo-root `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `VITE_PORT` | `3000` | Vite dev server port |
| `VITE_ALLOWED_HOSTS` | any host | Comma-separated allowlist; `*`/`true`/empty = allow all. Restrict this outside development. |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Where `/api` + `/ws` are proxied (server-side only) |
