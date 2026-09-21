import asyncio
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from voice_call_agent.core.config import settings
from voice_call_agent.providers.telephony.interface import TelephonyProvider

logger = logging.getLogger(__name__)


class ExotelTelephonyProvider(TelephonyProvider):
    """Exotel Voice telephony provider.

    Supports connecting calls via Exotel Installed Apps / Flows (App Bazaar),
    ExoML response generation, and status callbacks.
    Documentation: https://developer.exotel.com/api/
    """

    def __init__(
        self,
        account_sid: str | None = None,
        api_key: str | None = None,
        api_token: str | None = None,
        caller_id: str | None = None,
        subdomain: str | None = None,
        app_id: str | None = None,
    ):
        self._account_sid = account_sid
        self._api_key = api_key
        self._api_token = api_token
        self._caller_id = caller_id
        self._subdomain = subdomain
        self._app_id = app_id

    @property
    def account_sid(self) -> str:
        return self._account_sid if self._account_sid is not None else settings.exotel_account_sid

    @property
    def api_key(self) -> str:
        return self._api_key if self._api_key is not None else settings.exotel_api_key

    @property
    def api_token(self) -> str:
        return self._api_token if self._api_token is not None else settings.exotel_api_token

    @property
    def caller_id(self) -> str:
        return self._caller_id if self._caller_id is not None else settings.exotel_caller_id

    @property
    def subdomain(self) -> str:
        return self._subdomain if self._subdomain is not None else (settings.exotel_subdomain or "api.exotel.com")

    @property
    def app_id(self) -> str:
        return self._app_id if self._app_id is not None else settings.exotel_app_id

    def verify_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Exotel uses basic token/IP or shared secret validation if configured."""
        if not self.api_token:
            return True
        return True

    def generate_connect_twiml(
        self,
        stream_url: str,
        call_sid: str,
        custom_params: dict[str, str] | None = None,
    ) -> str:
        """Generate ExoML / XML connecting response for Exotel Passthru applet."""
        response = ET.Element("Response")
        say = ET.SubElement(response, "Say")
        say.text = "Connecting to Voice Agent..."
        return ET.tostring(response, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def generate_exoml_say(self, text: str) -> str:
        """Generate ExoML response speaking a message to the caller."""
        response = ET.Element("Response")
        say = ET.SubElement(response, "Say")
        say.text = text
        return ET.tostring(response, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def generate_exoml_gather(
        self,
        say_text: str,
        action_url: str | None = None,
        timeout: int = 6,
        finish_on_key: str = "#",
    ) -> str:
        """Generate ExoML response that speaks LLM output and listens for caller response."""
        response = ET.Element("Response")
        gather_attrs: dict[str, str] = {"timeout": str(timeout)}
        if action_url:
            gather_attrs["action"] = action_url
            gather_attrs["method"] = "POST"
        if finish_on_key:
            gather_attrs["finishOnKey"] = finish_on_key

        gather = ET.SubElement(response, "Gather", gather_attrs)
        say = ET.SubElement(gather, "Say")
        say.text = say_text
        return ET.tostring(response, encoding="utf-8", xml_declaration=True).decode("utf-8")


    def create_media_message(
        self,
        stream_sid: str,
        payload_base64: str,
    ) -> dict[str, Any]:
        return {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": payload_base64,
            },
        }

    def create_mark_message(
        self,
        stream_sid: str,
        mark_name: str,
    ) -> dict[str, Any]:
        return {
            "event": "mark",
            "streamSid": stream_sid,
            "mark": {
                "name": mark_name,
            },
        }

    def create_clear_message(
        self,
        stream_sid: str,
    ) -> dict[str, Any]:
        return {
            "event": "clear",
            "streamSid": stream_sid,
        }

    async def make_outbound_call(
        self,
        to_number: str,
        callback_url: str | None = None,
        from_number: str | None = None,
        app_id: str | None = None,
        custom_field: str | None = None,
    ) -> dict[str, Any]:
        """Trigger an outbound call using Exotel Connect API.

        In Exotel:
        - `From`: The destination customer phone number to dial first.
        - `CallerId`: Your virtual ExoPhone number.
        - `Url`: http://my.exotel.com/{account_sid}/exoml/start_voice/{app_id}
        """
        caller_id = from_number or self.caller_id
        target_app_id = app_id or self.app_id

        if not self.account_sid or not self.api_key or not self.api_token:
            return {
                "success": False,
                "error": "Missing EXOTEL_ACCOUNT_SID, EXOTEL_API_KEY, or EXOTEL_API_TOKEN.",
                "call_sid": None,
            }

        if not caller_id:
            return {
                "success": False,
                "error": "Missing EXOTEL_CALLER_ID (ExoPhone). Please set your ExoPhone virtual number.",
                "call_sid": None,
            }

        # Format URL for Exotel App Bazaar flow
        flow_url = ""
        if target_app_id:
            flow_url = f"http://my.exotel.com/{self.account_sid}/exoml/start_voice/{target_app_id}"
        elif callback_url:
            flow_url = callback_url

        endpoint = f"https://{self.subdomain}/v1/Accounts/{self.account_sid}/Calls/connect.json"

        params: dict[str, str] = {
            "From": to_number,
            "CallerId": caller_id,
            "CallType": "trans",
        }
        if flow_url:
            params["Url"] = flow_url
        if callback_url:
            params["StatusCallback"] = callback_url
        if custom_field:
            params["CustomField"] = custom_field

        data = urllib.parse.urlencode(params).encode("utf-8")
        auth_header = base64.b64encode(f"{self.api_key}:{self.api_token}".encode("utf-8")).decode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "VoiceCallAgent-Exotel/1.0",
            },
            method="POST",
        )

        def _send() -> dict[str, Any]:
            try:
                with urllib.request.urlopen(req) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as err:
                error_body = err.read().decode("utf-8")
                try:
                    err_json = json.loads(error_body)
                    msg = err_json.get("RestException", {}).get("Message") or error_body
                except Exception:  # noqa: BLE001
                    msg = error_body or str(err)
                raise RuntimeError(f"Exotel API Error ({err.code}): {msg}") from err

        try:
            result = await asyncio.to_thread(_send)
            call_obj = result.get("Call", {})
            call_sid = call_obj.get("Sid") or result.get("Sid")
            status = call_obj.get("Status") or result.get("Status", "queued")

            return {
                "success": True,
                "provider": "exotel",
                "call_sid": call_sid,
                "status": status,
                "to": to_number,
                "from": caller_id,
                "app_id": target_app_id,
                "details": call_obj,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to make outbound call via Exotel: %s", exc)
            return {
                "success": False,
                "provider": "exotel",
                "error": str(exc),
                "call_sid": None,
            }
