from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from voice_call_agent.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_outbound_call_missing_credentials():
    # Calling without Twilio credentials should return HTTP 400 with descriptive error
    from voice_call_agent.core.config import settings

    with patch.object(settings, "twilio_account_sid", ""):
        response = client.post(
            "/telephony/call",
            json={"to_number": "+919876543210"},
        )
        assert response.status_code == 400
        assert "Missing" in response.json()["detail"]


@pytest.mark.anyio
async def test_outbound_call_mocked_success():
    mock_result = {
        "success": True,
        "call_sid": "CA_OUTBOUND_12345",
        "status": "queued",
        "to": "+919876543210",
        "from": "+914048210000",
    }

    with patch(
        "voice_call_agent.api.telephony.provider.make_outbound_call",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(
            "/telephony/call",
            json={"to_number": "+919876543210", "from_number": "+914048210000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["call_sid"] == "CA_OUTBOUND_12345"
        assert data["to"] == "+919876543210"
