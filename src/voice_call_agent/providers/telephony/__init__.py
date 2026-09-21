from voice_call_agent.core.config import settings
from voice_call_agent.providers.telephony.exotel import ExotelTelephonyProvider
from voice_call_agent.providers.telephony.interface import TelephonyProvider
from voice_call_agent.providers.telephony.session_manager import (
    CallSessionManager,
    session_manager,
)
from voice_call_agent.providers.telephony.twilio import TwilioTelephonyProvider


def get_telephony_provider(name: str | None = None) -> TelephonyProvider:
    """Retrieve telephony provider instance based on name or settings."""
    provider_name = (name or settings.telephony_provider or "twilio").lower()
    if provider_name == "exotel":
        return ExotelTelephonyProvider()
    return TwilioTelephonyProvider()


__all__ = [
    "CallSessionManager",
    "ExotelTelephonyProvider",
    "TelephonyProvider",
    "TwilioTelephonyProvider",
    "get_telephony_provider",
    "session_manager",
]

