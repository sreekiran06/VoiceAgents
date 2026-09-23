import base64
import json
from unittest.mock import AsyncMock

import pytest

from voice_call_agent.agent.orchestrator import VoiceAgentOrchestrator
from voice_call_agent.agent.tools.lead_tools import register_default_tools
from voice_call_agent.agent.tools.registry import ToolRegistry
from voice_call_agent.models.conversation import CallSession
from voice_call_agent.providers.llm.client import ExpLabsLanguageModel
from voice_call_agent.providers.speech.tts import MockTextToSpeechProvider


@pytest.mark.anyio
async def test_tool_registry_and_lead_tools():
    registry = ToolRegistry()
    register_default_tools(registry)

    assert len(registry.list_tools()) == 3

    # 1. Test qualify_lead tool
    lead_res = await registry.execute(
        "qualify_lead",
        {
            "requirement": "3BHK luxury flat",
            "budget": "1.5 Cr",
            "location": "Gachibowli, Hyderabad",
            "timeline": "Immediate",
            "name": "Kiran",
            "phone": "+919876543210",
        },
    )
    assert lead_res["status"] == "success"
    assert lead_res["result"]["lead_captured"] is True
    assert lead_res["result"]["location"] == "Gachibowli, Hyderabad"

    # 2. Test book_appointment tool
    booking_res = await registry.execute(
        "book_appointment",
        {
            "customer_name": "Sita",
            "phone": "+919988776655",
            "appointment_type": "site visit",
            "date": "2026-09-12",
            "time": "10:30 AM",
        },
    )
    assert booking_res["status"] == "success"
    assert booking_res["result"]["booking_confirmed"] is True
    assert "SK-" in booking_res["result"]["confirmation_code"]

    # 3. Test transfer_to_human tool
    transfer_res = await registry.execute(
        "transfer_to_human",
        {"department": "senior_counsellor", "reason": "Fee negotiation"},
    )
    assert transfer_res["status"] == "success"
    assert transfer_res["result"]["transfer_requested"] is True


@pytest.mark.anyio
async def test_orchestrator_turn_handling():
    mock_llm = AsyncMock(spec=ExpLabsLanguageModel)
    mock_llm.generate_response.return_value = {
        "role": "assistant",
        "content": "Hello! I can help you find a 2BHK flat in Hyderabad.",
    }
    tts = MockTextToSpeechProvider()

    orchestrator = VoiceAgentOrchestrator(llm=mock_llm, tts=tts)
    session = CallSession(call_id="CA_TEST_ORCH")

    reply, audio_bytes, _tools = await orchestrator.handle_turn(
        session, "Hi, I need a 2BHK in Hyderabad."
    )

    assert "2BHK" in reply
    assert len(audio_bytes) > 0
    assert len(session.messages) == 2  # user + assistant
    assert session.messages[0].content == "Hi, I need a 2BHK in Hyderabad."
    assert session.messages[1].content == reply


@pytest.mark.anyio
async def test_orchestrator_with_tool_calling():
    mock_llm = AsyncMock(spec=ExpLabsLanguageModel)
    # Simulate LLM emitting a tool call
    mock_llm.generate_response.return_value = {
        "role": "assistant",
        "content": "I have noted your budget and requirement.",
        "tool_calls": [
            {
                "function": {
                    "name": "qualify_lead",
                    "arguments": json.dumps(
                        {
                            "requirement": "2BHK",
                            "budget": "60 Lakhs",
                            "location": "Madhapur",
                            "name": "Ravi",
                        }
                    ),
                }
            }
        ],
    }

    orchestrator = VoiceAgentOrchestrator(llm=mock_llm)
    session = CallSession(call_id="CA_TOOL_TEST")

    reply, _audio_bytes, executed_tools = await orchestrator.handle_turn(
        session, "I am Ravi, looking for 2BHK in Madhapur under 60 Lakhs."
    )

    assert len(executed_tools) == 1
    assert executed_tools[0]["tool"] == "qualify_lead"
    assert session.metadata.get("lead", {}).get("location") == "Madhapur"
    assert "noted" in reply


@pytest.mark.anyio
async def test_audio_chunking_stream():
    fake_audio = b"A" * 480  # 480 bytes = 3 chunks of 160
    chunks = []
    async for chunk in VoiceAgentOrchestrator.chunk_mulaw_stream(fake_audio, chunk_size=160):
        chunks.append(chunk)

    assert len(chunks) == 3
    assert all(len(c) == 160 for c in chunks)


@pytest.mark.anyio
async def test_end_to_end_voice_turn_over_websocket():
    import struct

    from fastapi.testclient import TestClient

    from voice_call_agent.main import app as fastapi_app
    from voice_call_agent.providers.speech.codec import pcm16_to_mulaw
    from voice_call_agent.providers.telephony import session_manager

    test_client = TestClient(fastapi_app)
    call_sid = "CA_E2E_VOICE_01"
    stream_sid = "MZ_E2E_01"

    session = await session_manager.get_or_create(call_id=call_sid, from_number="+919876543210")

    # High-energy speech frame (amplitude 5000)
    speech_pcm = struct.pack("<160h", *([5000] * 160))
    speech_mulaw = pcm16_to_mulaw(speech_pcm)
    speech_b64 = base64.b64encode(speech_mulaw).decode("utf-8")

    # Silent frame
    silent_pcm = struct.pack("<160h", *([0] * 160))
    silent_mulaw = pcm16_to_mulaw(silent_pcm)
    silent_b64 = base64.b64encode(silent_mulaw).decode("utf-8")

    from unittest.mock import patch
    from voice_call_agent.providers.speech.stt import TranscriptionResult
    from voice_call_agent.providers.speech.tts import SynthesisResult

    with patch(
        "voice_call_agent.api.telephony.stt_provider.transcribe",
        new_callable=AsyncMock,
        return_value=TranscriptionResult(text="Hello!", language="en"),
    ), patch(
        "voice_call_agent.api.telephony.orchestrator.tts.synthesize",
        new_callable=AsyncMock,
        return_value=SynthesisResult(audio_mulaw_bytes=b"\xff" * 320, duration_seconds=0.04),
    ), patch(
        "voice_call_agent.api.telephony.orchestrator.llm.generate_response",
        new_callable=AsyncMock,
        return_value={"role": "assistant", "content": "Hello!"},
    ), test_client.websocket_connect("/telephony/media-stream") as ws:
        # Start stream
        ws.send_text(
            json.dumps(
                {
                    "event": "start",
                    "streamSid": stream_sid,
                    "start": {
                        "streamSid": stream_sid,
                        "callSid": call_sid,
                        "tracks": ["inbound"],
                    },
                }
            )
        )

        # Send speech (16 frames = 320ms)
        for _ in range(16):
            ws.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": speech_b64},
                    }
                )
            )

        # Send silence (36 frames = 720ms) to finish turn and trigger VAD
        for _ in range(36):
            ws.send_text(
                json.dumps(
                    {
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": silent_b64},
                    }
                )
            )

        # Read responses emitted by server
        received_media = False
        mark_count = 0
        for _ in range(100):
            try:
                raw = ws.receive_text()
                data = json.loads(raw)
                if data.get("event") == "media":
                    received_media = True
                    assert "payload" in data["media"]
                elif data.get("event") == "mark":
                    mark_count += 1
                    if mark_count >= 2:
                        break
            except Exception:  # noqa: BLE001
                break

        assert received_media is True
        assert mark_count >= 1

        # Finish stream
        ws.send_text(json.dumps({"event": "stop", "streamSid": stream_sid}))

    # Verify conversation session history recorded the turn
    assert len(session.messages) >= 2
