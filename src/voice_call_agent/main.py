from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
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

static_dir = (Path(__file__).resolve().parent / "static")
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir), name="assets")


@app.get("/", include_in_schema=False)
async def website() -> HTMLResponse:
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>SK Voice Agents API is running</h1>")


@app.get("/admin", include_in_schema=False)
async def admin_dashboard() -> HTMLResponse:
    admin_file = static_dir / "admin.html"
    if admin_file.exists():
        return HTMLResponse(content=admin_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Admin Console</h1>")

