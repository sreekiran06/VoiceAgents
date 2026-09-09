from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voice_call_agent.api.clients import router as clients_router
from voice_call_agent.api.routes import router
from voice_call_agent.api.telephony import router as telephony_router
from voice_call_agent.api.vapi import router as vapi_router
from voice_call_agent.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(router)
app.include_router(telephony_router)
app.include_router(clients_router)
app.include_router(vapi_router)

static_dir = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


@app.get("/", include_in_schema=False)
async def website() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/admin", include_in_schema=False)
async def admin_dashboard() -> FileResponse:
    return FileResponse(static_dir / "admin.html")
