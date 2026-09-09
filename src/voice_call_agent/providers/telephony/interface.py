from typing import Any, Protocol


class TelephonyProvider(Protocol):
    """Protocol defining telephony provider operations."""

    def verify_signature(
        self,
        url: str,
        params: dict[str, str],
        signature: str,
    ) -> bool:
        """Verify whether the incoming request was signed by the telephony provider."""
        ...

    def generate_connect_twiml(
        self,
        stream_url: str,
        call_sid: str,
        custom_params: dict[str, str] | None = None,
    ) -> str:
        """Generate response payload/TwiML connecting the call to the media stream WebSocket."""
        ...

    def create_media_message(
        self,
        stream_sid: str,
        payload_base64: str,
    ) -> dict[str, Any]:
        """Create a media chunk payload to transmit audio back over the stream."""
        ...

    def create_mark_message(
        self,
        stream_sid: str,
        mark_name: str,
    ) -> dict[str, Any]:
        """Create a mark message to receive playback confirmation."""
        ...

    def create_clear_message(
        self,
        stream_sid: str,
    ) -> dict[str, Any]:
        """Create a clear message to immediately halt playback on caller interruption."""
        ...
