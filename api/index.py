import os
import sys

# Ensure src package is importable in Vercel serverless environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from voice_call_agent.main import app as fastapi_app  # noqa: E402


async def app(scope, receive, send):
    """Normalize Vercel serverless request path to match FastAPI routes."""
    if scope.get("type") == "http":
        headers = dict(scope.get("headers", []))
        matched_path = (
            headers.get(b"x-matched-path", b"").decode("utf-8")
            or headers.get(b"x-forwarded-uri", b"").decode("utf-8")
        )
        if matched_path and not matched_path.startswith("/api/index"):
            scope["path"] = matched_path.split("?")[0]
        elif scope.get("path") in ("/api/index.py", "/api/index", "/api/index/"):
            scope["path"] = "/"
    await fastapi_app(scope, receive, send)

