import asyncio
import base64
import hashlib
import hmac
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from voice_call_agent.core.config import settings
from voice_call_agent.providers.telephony.interface import TelephonyProvider


class TwilioTelephonyProvider(TelephonyProvider):
    """Twilio Voice and Media Streams telephony provider."""

    def __init__(
        self,
        auth_token: str | None = None,
        account_sid: str | None = None,
        from_number: str | None = None,
    ):
        self._auth_token = auth_token
        self._account_sid = account_sid
        self._from_number = from_number

    @property
    def auth_token(self) -> str:
        return self._auth_token if self._auth_token is not None else settings.twilio_auth_token

    @property
    def account_sid(self) -> str:
        return self._account_sid if self._account_sid is not None else settings.twilio_account_sid

    @property
    def from_number(self) -> str:
        return self._from_number if self._from_number is not None else settings.twilio_from_number

    def verify_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Verify the X-Twilio-Signature header using RFC 2104 HMAC-SHA1.

        Documentation: https://www.twilio.com/docs/usage/security#validating-requests
        """
        if not self.auth_token:
            return False

        # Build data: URL + sorted key-value pairs
        data = url
        for key in sorted(params.keys()):
            data += f"{key}{params[key]}"

        mac = hmac.new(
            self.auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        )
        computed_signature = base64.b64encode(mac.digest()).decode("utf-8")
        return hmac.compare_digest(computed_signature, signature)

    def generate_connect_twiml(
        self,
        stream_url: str,
        call_sid: str,
        custom_params: dict[str, str] | None = None,
    ) -> str:
        """Generate TwiML connecting the call to a bidirectional audio WebSocket stream."""
        response = ET.Element("Response")
        connect = ET.SubElement(response, "Connect")
        stream = ET.SubElement(connect, "Stream", {"url": stream_url})

        # Add callSid parameter
        ET.SubElement(stream, "Parameter", {"name": "callSid", "value": call_sid})

        if custom_params:
            for key, value in custom_params.items():
                ET.SubElement(stream, "Parameter", {"name": key, "value": value})

        return ET.tostring(response, encoding="utf-8", xml_declaration=True).decode("utf-8")

    def create_media_message(
        self,
        stream_sid: str,
        payload_base64: str,
    ) -> dict[str, Any]:
        """Create media event payload to stream μ-law audio to Twilio."""
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
        """Create mark event payload to receive playback acknowledgement from Twilio."""
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
        """Create clear event payload to cancel queued audio on caller interruption."""
        return {
            "event": "clear",
            "streamSid": stream_sid,
        }

    async def make_outbound_call(
        self,
        to_number: str,
        callback_url: str,
        from_number: str | None = None,
    ) -> dict[str, Any]:
        """Trigger an outbound call using Twilio REST API Calls endpoint."""
        caller_id = from_number or self.from_number
        if not self.account_sid or not self.auth_token or not caller_id:
            return {
                "success": False,
                "error": "Missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_FROM_NUMBER.",
                "call_sid": None,
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls.json"
        data = urllib.parse.urlencode({
            "To": to_number,
            "From": caller_id,
            "Url": callback_url,
        }).encode("utf-8")

        auth_header = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )

        def _send() -> dict[str, Any]:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))

        try:
            result = await asyncio.to_thread(_send)
            return {
                "success": True,
                "call_sid": result.get("sid"),
                "status": result.get("status"),
                "to": to_number,
                "from": caller_id,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": str(exc),
                "call_sid": None,
            }
