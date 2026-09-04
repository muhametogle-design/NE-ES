import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.db import init_db, SessionLocal, set_rls_context
from app.core.ws import ws_manager
from app.api.auth import router as auth_router
from app.api.school import router as school_router
from app.api.state import router as state_router
from app.api.ws import router as ws_router
from app.services.scheduler import compliance_scheduler, backup_scheduler
from app.services.seed import seed_demo_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ne_emis")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize DB
    init_db()
    logger.info("Database schema verified and initialized.")

    # 2. Bind event loop to WebSocket Manager
    try:
        loop = asyncio.get_running_loop()
        ws_manager.set_loop(loop)
    except Exception as e:
        logger.warning(f"Could not bind loop to ws_manager: {e}")

    # 3. Seed demo data if database is empty
    if settings.AUTO_SEED_DEMO:
        db = SessionLocal()
        try:
            from app.models.tenancy import PrivateSchool
            count = db.query(PrivateSchool).count()
            if count == 0:
                set_rls_context(db, None, "state_admin")
                seed_demo_data(db)
                logger.info("Demo data automatically seeded for NE-EMIS network.")
        except Exception as e:
            logger.error(f"Seeding demo data failed: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

    # 4. Start compliance audit scheduler
    if settings.ENABLE_SCHEDULER:
        compliance_scheduler.start()
        logger.info("Compliance Audit Scheduler armed (15:00 EAT).")

    # 5. Start backup scheduler
    if settings.ENABLE_BACKUP_SCHEDULER:
        backup_scheduler.start()
        logger.info("Automated Backup Scheduler armed (00:00 EAT).")

    # 6. Production configuration sanity check
    if settings.APP_ENV == "production" and settings.JWT_SECRET_KEY.startswith("dev-"):
        logger.warning("SECURITY ALERT: Production environment running with default JWT_SECRET_KEY!")

    yield

    # Shutdown hooks
    if settings.ENABLE_SCHEDULER:
        compliance_scheduler.stop()
    if settings.ENABLE_BACKUP_SCHEDULER:
        backup_scheduler.stop()
    logger.info("Application shutdown completed.")

app = FastAPI(
    title="NE-EMIS API",
    description="Private School Management & State Compliance Monitoring System",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# --- CORS -------------------------------------------------------------------
# Browsers reject allow_origins=["*"] combined with allow_credentials=True, so we
# always ship an explicit dev allow-list and fall back to a regex for LAN/dev hosts.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.0.139:5173",
    "http://172.31.80.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

configured = [
    o.strip()
    for o in settings.CORS_ORIGINS_RAW.split(",")
    if o.strip() and o.strip() != "*"
]

# Preserve order, drop duplicates.
cors_origins = list(dict.fromkeys(DEV_ORIGINS + configured))

# Any private-LAN address on the Vite/API dev ports (covers changing DHCP IPs).
cors_origin_regex = (
    r"^http://(localhost|127\.0\.0\.1|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})"
    r"(:(5173|3000|8000))?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
    max_age=600,
)
logger.info("CORS allow-list active for %d explicit origins.", len(cors_origins))

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Include Routers
app.include_router(auth_router, prefix="/api")
app.include_router(school_router, prefix="/api")
app.include_router(state_router, prefix="/api")
app.include_router(ws_router, prefix="/ws")

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "NE-EMIS", "version": "1.0.0"}

# Static / SPA Mounting
web_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist")
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(os.path.join(web_dist, "index.html")):
    assets_dir = os.path.join(web_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    if os.path.exists(frontend_dir):
        app.mount("/admin", StaticFiles(directory=frontend_dir, html=True), name="admin")
        
        @app.get("/admin")
        async def admin_root():
            return FileResponse(os.path.join(frontend_dir, "index.html"))

    @app.get("/{full_path:path}")
    async def serve_react_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("ws"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return FileResponse(os.path.join(web_dist, "index.html"))
elif os.path.exists(frontend_dir):
    app.mount("/admin", StaticFiles(directory=frontend_dir, html=True), name="admin")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(frontend_dir, "index.html"))
