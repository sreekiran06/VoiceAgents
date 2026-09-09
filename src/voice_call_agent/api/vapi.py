"""Vapi.ai webhook and management API routes.

Vapi calls our server with these events via POST /vapi/webhook:
  - assistant-request  → return assistant config dynamically
  - function-call      → execute a tool and return result
  - end-of-call-report → store call summary

We also expose management endpoints:
  POST /vapi/setup   → create assistant + buy phone number (run once)
  POST /vapi/call    → place an outbound call
  GET  /vapi/calls   → list recent calls
  GET  /vapi/numbers → list phone numbers
"""

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from voice_call_agent.agent.prompts import SYSTEM_PROMPT
from voice_call_agent.agent.tools.lead_tools import register_default_tools
from voice_call_agent.agent.tools.registry import ToolRegistry
from voice_call_agent.core.config import settings
from voice_call_agent.providers.vapi import VapiClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vapi", tags=["vapi"])

# Shared tool registry used to execute Vapi function-call events
_tool_registry = ToolRegistry()
register_default_tools(_tool_registry)

# Singleton Vapi client
_vapi = VapiClient()


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class OutboundCallRequest(BaseModel):
    to_number: str
    assistant_id: str | None = None
    phone_number_id: str | None = None


class SetupRequest(BaseModel):
    """One-time setup: create assistant and optionally buy a phone number."""
    buy_phone_number: bool = True
    country_code: str = "US"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_vapi_tools() -> list[dict[str, Any]]:
    """Convert our internal tool registry schema into Vapi-compatible tool definitions."""
    vapi_tools = []
    for t in _tool_registry.list_tools():
        # Registry returns OpenAI format: {"type": "function", "function": {...}}
        fn = t.get("function", {})
        vapi_tools.append({
            "type": "function",
            "function": {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {"type": "object", "properties": {}}),
            },
            "server": {
                "url": f"{settings.public_base_url.rstrip('/')}/vapi/webhook",
            },
        })
    return vapi_tools


def _assistant_config() -> dict[str, Any]:
    """Return the full Vapi assistant configuration object."""
    webhook_url = f"{settings.public_base_url.rstrip('/')}/vapi/webhook"

    return {
        "name": "SK Voice Agent",
        "firstMessage": "Hello! I'm your AI assistant. How can I help you today?",
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "systemPrompt": SYSTEM_PROMPT,
            "tools": _build_vapi_tools(),
        },
        "voice": {
            "provider": "azure",
            "voiceId": "en-IN-NeerjaNeural",
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "en-IN",
        },
        "serverUrl": webhook_url,
    }


# ---------------------------------------------------------------------------
# Webhook — Vapi calls this endpoint during every conversation
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def vapi_webhook(request: Request) -> dict[str, Any]:
    """Central Vapi webhook handler.

    Vapi posts JSON events here. We handle:
      - assistant-request  → dynamically provide assistant config
      - function-call      → execute tool and return result
      - end-of-call-report → log summary
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return {"error": "invalid JSON"}

    message = body.get("message", {})
    msg_type = message.get("type", "")

    logger.info("Vapi webhook event: %s", msg_type)

    # ── 1. assistant-request ─────────────────────────────────────────────────
    if msg_type == "assistant-request":
        call = message.get("call", {})
        logger.info("Assistant request for call: %s", call.get("id", "unknown"))
        return {"assistant": _assistant_config()}

    # ── 2. function-call (tool execution) ────────────────────────────────────
    if msg_type == "function-call":
        fn = message.get("functionCall", {})
        fn_name = fn.get("name", "")
        fn_params = fn.get("parameters", {})

        logger.info("Vapi function call: %s(%s)", fn_name, fn_params)

        try:
            result = await _tool_registry.execute(fn_name, fn_params)
        except Exception as exc:  # noqa: BLE001
            logger.error("Tool execution error for %s: %s", fn_name, exc)
            result = {"error": str(exc)}

        return {"result": result}

    # ── 3. end-of-call-report ────────────────────────────────────────────────
    if msg_type == "end-of-call-report":
        call = message.get("call", {})
        summary = message.get("summary", "")
        transcript = message.get("transcript", "")
        logger.info(
            "Call ended: id=%s | summary=%s | transcript_len=%d",
            call.get("id"),
            summary[:120],
            len(transcript),
        )
        return {"received": True}

    # ── 4. status-update ─────────────────────────────────────────────────────
    if msg_type == "status-update":
        status = message.get("status", "")
        logger.info("Vapi call status: %s", status)
        return {"received": True}

    # ── 5. hang (caller hung up) ──────────────────────────────────────────────
    if msg_type == "hang":
        logger.info("Caller hung up")
        return {"received": True}

    logger.debug("Unhandled Vapi event type: %s", msg_type)
    return {"received": True}


# ---------------------------------------------------------------------------
# One-time Setup — create assistant + buy phone number
# ---------------------------------------------------------------------------


@router.post("/setup")
async def vapi_setup(payload: SetupRequest) -> dict[str, Any]:
    """One-time setup: create a Vapi assistant and optionally buy a phone number.

    Run this ONCE after adding your VAPI_API_KEY to .env.
    The returned assistant_id and phone_number_id should be saved back to .env.
    """
    if not settings.vapi_api_key:
        raise HTTPException(
            status_code=400,
            detail="VAPI_API_KEY is not configured. Add it to your .env file.",
        )

    result: dict[str, Any] = {}

    # Create assistant
    def _create_assistant() -> dict[str, Any]:
        return _vapi.create_assistant(
            name="SK Voice Agent",
            system_prompt=SYSTEM_PROMPT,
            tools=_build_vapi_tools(),
            first_message="Hello! I'm your AI assistant. How can I help you today?",
        )

    assistant = await asyncio.to_thread(_create_assistant)
    if "id" not in assistant:
        raise HTTPException(status_code=400, detail=f"Failed to create assistant: {assistant}")

    assistant_id = assistant["id"]
    result["assistant_id"] = assistant_id
    result["assistant_name"] = assistant.get("name")
    logger.info("✅ Created Vapi assistant: %s", assistant_id)

    # Optionally buy a phone number
    if payload.buy_phone_number:
        def _buy_number() -> dict[str, Any]:
            return _vapi.buy_phone_number(
                country_code=payload.country_code,
                assistant_id=assistant_id,
            )

        phone = await asyncio.to_thread(_buy_number)
        if "id" in phone:
            result["phone_number_id"] = phone["id"]
            result["phone_number"] = phone.get("number") or phone.get("phoneNumber")
            logger.info("✅ Bought Vapi phone number: %s", result["phone_number"])
        else:
            result["phone_number_warning"] = f"Could not buy number automatically: {phone}"

    result["next_steps"] = (
        "Add these to your .env:\n"
        f"  VAPI_ASSISTANT_ID={assistant_id}\n"
        + (f"  VAPI_PHONE_NUMBER_ID={result.get('phone_number_id','')}\n" if "phone_number_id" in result else "")
        + "Then restart the server."
    )

    return result


# ---------------------------------------------------------------------------
# Outbound Call
# ---------------------------------------------------------------------------


@router.post("/call")
async def place_vapi_call(payload: OutboundCallRequest) -> dict[str, Any]:
    """Place an outbound AI call to a real phone number via Vapi."""
    assistant_id = payload.assistant_id or settings.vapi_assistant_id
    if not assistant_id:
        raise HTTPException(
            status_code=400,
            detail="No assistant_id provided. Run POST /vapi/setup first, or pass assistant_id in the request.",
        )
    if not settings.vapi_api_key:
        raise HTTPException(status_code=400, detail="VAPI_API_KEY not configured in .env")

    def _call() -> dict[str, Any]:
        return _vapi.make_outbound_call(
            to_number=payload.to_number,
            assistant_id=assistant_id,
            phone_number_id=payload.phone_number_id,
        )

    result = await asyncio.to_thread(_call)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ---------------------------------------------------------------------------
# List Calls & Phone Numbers (for Admin Dashboard)
# ---------------------------------------------------------------------------


@router.get("/calls")
async def list_vapi_calls(limit: int = 20) -> list[dict[str, Any]]:
    """List recent Vapi calls."""
    if not settings.vapi_api_key:
        return []

    def _list() -> list[dict[str, Any]]:
        return _vapi.list_calls(limit=limit)

    return await asyncio.to_thread(_list)


@router.get("/numbers")
async def list_vapi_numbers() -> list[dict[str, Any]]:
    """List Vapi phone numbers on this account."""
    if not settings.vapi_api_key:
        return []

    def _list() -> list[dict[str, Any]]:
        return _vapi.list_phone_numbers()

    return await asyncio.to_thread(_list)


@router.get("/assistants")
async def list_vapi_assistants() -> list[dict[str, Any]]:
    """List Vapi assistants."""
    if not settings.vapi_api_key:
        return []

    def _list() -> list[dict[str, Any]]:
        return _vapi.list_assistants()

    return await asyncio.to_thread(_list)


@router.get("/status")
async def vapi_status() -> dict[str, Any]:
    """Check Vapi configuration status."""
    return {
        "configured": bool(settings.vapi_api_key),
        "assistant_id": settings.vapi_assistant_id or None,
        "phone_number_id": settings.vapi_phone_number_id or None,
        "webhook_url": f"{settings.public_base_url.rstrip('/')}/vapi/webhook",
        "setup_url": f"{settings.public_base_url.rstrip('/')}/vapi/setup",
    }
