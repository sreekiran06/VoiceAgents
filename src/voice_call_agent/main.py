import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from voice_call_agent.api.analytics import router as analytics_router
from voice_call_agent.api.auth_routes import router as auth_router
from voice_call_agent.api.businesses import router as businesses_router
from voice_call_agent.api.clients import calls_router, router as clients_router
from voice_call_agent.api.knowledge import router as knowledge_router
from voice_call_agent.api.routes import router
from voice_call_agent.api.telephony import router as telephony_router
from voice_call_agent.api.vapi import router as vapi_router
from voice_call_agent.core.config import settings
from voice_call_agent.core.database import close_db, init_db
from voice_call_agent.core.seed import seed_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — initialize DB on startup, close on shutdown."""
    logger.info("Initializing database...")
    await init_db()
    await seed_database()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down database...")
    await close_db()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Core routers
app.include_router(router)
app.include_router(telephony_router)
app.include_router(clients_router)
app.include_router(calls_router)
app.include_router(vapi_router)

# Multi-tenant routers
app.include_router(auth_router)
app.include_router(businesses_router)
app.include_router(knowledge_router)
app.include_router(analytics_router)

static_dir = (Path(__file__).resolve().parent / "static")
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


@app.get("/", include_in_schema=False)
@app.get("/api", include_in_schema=False)
@app.get("/api/index", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
async def website() -> HTMLResponse:
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>SK Voice Agents API is running</h1>")


@app.get("/admin", include_in_schema=False)
@app.get("/api/admin", include_in_schema=False)
async def admin_dashboard() -> HTMLResponse:
    admin_file = static_dir / "admin.html"
    if admin_file.exists():
        return HTMLResponse(content=admin_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Admin Console</h1>")


@app.get("/client", include_in_schema=False)
@app.get("/client.html", include_in_schema=False)
@app.get("/api/client", include_in_schema=False)
async def client_portal() -> HTMLResponse:
    client_file = static_dir / "client.html"
    if client_file.exists():
        return HTMLResponse(content=client_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Client Portal</h1>")

