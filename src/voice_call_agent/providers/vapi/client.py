"""Vapi.ai REST API client for AI-powered phone calls.

Vapi handles the entire voice pipeline (STT → LLM → TTS) in the cloud.
Our server acts as a webhook that receives transcribed user messages
and returns assistant text replies — no raw audio streaming needed.

Docs: https://docs.vapi.ai
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from voice_call_agent.core.config import settings

logger = logging.getLogger(__name__)

VAPI_BASE_URL = "https://api.vapi.ai"


class VapiClient:
    """Lightweight Vapi.ai REST API client (no extra dependencies)."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    @property
    def api_key(self) -> str:
        return self._api_key or settings.vapi_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a synchronous HTTP request to the Vapi API."""
        url = f"{VAPI_BASE_URL}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8")
            logger.error("Vapi API error %s: %s", exc.code, error_body)
            try:
                return json.loads(error_body)
            except Exception:  # noqa: BLE001
                return {"error": error_body, "status": exc.code}

    # ------------------------------------------------------------------
    # Assistants
    # ------------------------------------------------------------------

    def create_assistant(
        self,
        name: str,
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        first_message: str = "Hello! How can I assist you today?",
        language: str = "en-IN",
    ) -> dict[str, Any]:
        """Create a Vapi assistant with the given system prompt and tools.

        Returns the created assistant object including its `id`.
        Tools should already be in Vapi format: {"type":"function","function":{...},"server":{...}}
        """
        payload: dict[str, Any] = {
            "name": name,
            "firstMessage": first_message,
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "systemPrompt": system_prompt,
                "tools": tools or [],
                "temperature": 0.7,
            },
            "voice": {
                "provider": "azure",
                "voiceId": "en-IN-NeerjaNeural",
            },
            "transcriber": {
                "provider": "deepgram",
                "model": "nova-2",
                "language": language,
            },
            "serverUrl": f"{settings.public_base_url.rstrip('/')}/vapi/webhook",
        }

        return self._request("POST", "/assistant", body=payload)


    def get_assistant(self, assistant_id: str) -> dict[str, Any]:
        """Fetch an assistant by ID."""
        return self._request("GET", f"/assistant/{assistant_id}")

    def list_assistants(self) -> list[dict[str, Any]]:
        """List all assistants."""
        result = self._request("GET", "/assistant")
        return result if isinstance(result, list) else result.get("results", [])

    def delete_assistant(self, assistant_id: str) -> dict[str, Any]:
        """Delete an assistant by ID."""
        return self._request("DELETE", f"/assistant/{assistant_id}")

    # ------------------------------------------------------------------
    # Phone Numbers
    # ------------------------------------------------------------------

    def list_phone_numbers(self) -> list[dict[str, Any]]:
        """List all Vapi-managed phone numbers on the account."""
        result = self._request("GET", "/phone-number")
        return result if isinstance(result, list) else result.get("results", [])

    def buy_phone_number(
        self,
        country_code: str = "US",
        area_code: str | None = None,
        assistant_id: str | None = None,
    ) -> dict[str, Any]:
        """Purchase a Vapi phone number. Uses Vapi's built-in Twilio pool — free from your credit."""
        payload: dict[str, Any] = {
            "provider": "vapi",
            "countryCode": country_code,
        }
        if area_code:
            payload["areaCode"] = area_code
        if assistant_id:
            payload["assistantId"] = assistant_id
        return self._request("POST", "/phone-number", body=payload)

    def update_phone_number(
        self,
        phone_number_id: str,
        assistant_id: str,
    ) -> dict[str, Any]:
        """Assign an assistant to a phone number so inbound calls use that assistant."""
        return self._request(
            "PATCH",
            f"/phone-number/{phone_number_id}",
            body={"assistantId": assistant_id},
        )

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    def make_outbound_call(
        self,
        to_number: str,
        assistant_id: str,
        phone_number_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initiate an outbound call to a real phone number using a Vapi assistant.

        Args:
            to_number: E.164 phone number to call, e.g. "+919550365910"
            assistant_id: Vapi assistant ID to handle the conversation
            phone_number_id: Vapi phone number ID to call from (uses account default if omitted)
            metadata: Optional extra data to attach to the call
        """
        if not self.api_key:
            return {"success": False, "error": "VAPI_API_KEY not configured"}

        payload: dict[str, Any] = {
            "assistantId": assistant_id,
            "customer": {"number": to_number},
        }

        pid = phone_number_id or settings.vapi_phone_number_id
        if pid:
            payload["phoneNumberId"] = pid

        if metadata:
            payload["metadata"] = metadata

        result = self._request("POST", "/call", body=payload)
        if "id" in result:
            return {
                "success": True,
                "call_id": result["id"],
                "status": result.get("status"),
                "to": to_number,
            }
        return {
            "success": False,
            "error": result.get("error") or result.get("message") or str(result),
        }

    def get_call(self, call_id: str) -> dict[str, Any]:
        """Fetch call details by ID."""
        return self._request("GET", f"/call/{call_id}")

    def list_calls(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent calls."""
        result = self._request("GET", f"/call?limit={limit}")
        return result if isinstance(result, list) else result.get("results", [])
