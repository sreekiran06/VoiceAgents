import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from voice_call_agent.core.config import settings
from voice_call_agent.main import app as fastapi_app
from voice_call_agent.providers.telephony import session_manager

client = TestClient(fastapi_app)


def compute_twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    data = url
    for key in sorted(params.keys()):
        data += f"{key}{params[key]}"
    mac = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(mac.digest()).decode("utf-8")


@pytest.mark.anyio
async def test_inbound_webhook_returns_twiml():
    form_data = {
        "CallSid": "CA1234567890abcdef",
        "From": "+919876543210",
        "To": "+911122334455",
        "CallStatus": "ringing",
    }
    response = client.post("/telephony/inbound", data=form_data)
    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert "<Connect>" in response.text
    assert "<Stream" in response.text
    assert "CA1234567890abcdef" in response.text

    session = await session_manager.get_by_call_id("CA1234567890abcdef")
    assert session is not None
    assert session.from_number == "+919876543210"
    assert session.to_number == "+911122334455"


@pytest.mark.anyio
async def test_signature_validation():
    # Temporarily enable signature validation
    old_validate = settings.validate_telephony_signatures
    old_token = settings.twilio_auth_token
    settings.validate_telephony_signatures = True
    settings.twilio_auth_token = "secret_auth_token_123"

    try:
        form_data = {"CallSid": "CA_SIG_TEST_01", "From": "+1234"}
        url = "http://testserver/telephony/inbound"

        # Missing signature
        res_missing = client.post("/telephony/inbound", data=form_data)
        assert res_missing.status_code == 403

        # Invalid signature
        res_invalid = client.post(
            "/telephony/inbound",
            data=form_data,
            headers={"X-Twilio-Signature": "invalidsignature=="},
        )
        assert res_invalid.status_code == 403

        # Valid signature
        valid_sig = compute_twilio_signature(url, form_data, settings.twilio_auth_token)
        res_valid = client.post(
            "/telephony/inbound",
            data=form_data,
            headers={"X-Twilio-Signature": valid_sig},
        )
        assert res_valid.status_code == 200
        assert "<Connect>" in res_valid.text
    finally:
        settings.validate_telephony_signatures = old_validate
        settings.twilio_auth_token = old_token


@pytest.mark.anyio
async def test_status_webhook():
    call_sid = "CA_STATUS_TEST"
    await session_manager.get_or_create(call_sid, from_number="+911234567890")

    # In-progress update
    res = client.post("/telephony/status", data={"CallSid": call_sid, "CallStatus": "in-progress"})
    assert res.status_code == 200
    assert res.json() == {"status": "received"}

    session = await session_manager.get_by_call_id(call_sid)
    assert session is not None
    assert session.status == "in-progress"

    # Completed update cleans up session
    res_comp = client.post(
        "/telephony/status",
        data={"CallSid": call_sid, "CallStatus": "completed"},
    )
    assert res_comp.status_code == 200
    session_after = await session_manager.get_by_call_id(call_sid)
    assert session_after is None
