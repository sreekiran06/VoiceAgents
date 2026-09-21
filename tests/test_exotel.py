from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from voice_call_agent.core.config import settings
from voice_call_agent.main import app as fastapi_app
from voice_call_agent.providers.telephony import (
    ExotelTelephonyProvider,
    TwilioTelephonyProvider,
    get_telephony_provider,
    session_manager,
)

client = TestClient(fastapi_app)


def test_provider_factory():
    provider_tw = get_telephony_provider("twilio")
    assert isinstance(provider_tw, TwilioTelephonyProvider)

    provider_exo = get_telephony_provider("exotel")
    assert isinstance(provider_exo, ExotelTelephonyProvider)


@pytest.mark.anyio
async def test_exotel_provider_missing_credentials():
    exo = ExotelTelephonyProvider(account_sid="", api_key="", api_token="", caller_id="")
    result = await exo.make_outbound_call(to_number="+919876543210")
    assert result["success"] is False
    assert "Missing" in result["error"]


@pytest.mark.anyio
async def test_exotel_outbound_call_mocked_success():
    mock_result = {
        "success": True,
        "provider": "exotel",
        "call_sid": "exo_call_123456",
        "status": "in-progress",
        "to": "+919876543210",
        "from": "08012345678",
        "app_id": "12345",
    }

    with patch(
        "voice_call_agent.providers.telephony.exotel.ExotelTelephonyProvider.make_outbound_call",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(
            "/telephony/call",
            json={
                "to_number": "+919876543210",
                "from_number": "08012345678",
                "provider": "exotel",
                "app_id": "12345",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["provider"] == "exotel"
        assert data["call_sid"] == "exo_call_123456"
        assert data["app_id"] == "12345"


@pytest.mark.anyio
async def test_exotel_status_callback():
    call_sid = "exo_status_call_789"
    await session_manager.get_or_create(call_sid, from_number="+919876543210")

    # POST status update
    res_post = client.post(
        "/telephony/exotel/status",
        data={"CallSid": call_sid, "Status": "in-progress"},
    )
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "received"

    session = await session_manager.get_by_call_id(call_sid)
    assert session is not None
    assert session.status == "in-progress"

    # Completed status removes session
    res_comp = client.post(
        "/telephony/exotel/status",
        data={"CallSid": call_sid, "Status": "completed"},
    )
    assert res_comp.status_code == 200
    assert await session_manager.get_by_call_id(call_sid) is None


@pytest.mark.anyio
async def test_exotel_passthru_callback():
    call_sid = "exo_passthru_call_101"
    response = client.post(
        "/telephony/exotel/passthru",
        data={"CallSid": call_sid, "From": "+919876543210", "To": "08012345678"},
    )
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Response>" in response.text
    assert "<Say>" in response.text

    session = await session_manager.get_by_call_id(call_sid)
    assert session is not None
    assert session.metadata.get("provider") == "exotel"
