import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from voice_call_agent.main import app
from voice_call_agent.providers.telephony import session_manager

client = TestClient(app)


@pytest.mark.anyio
async def test_media_stream_websocket_lifecycle():
    call_sid = "CA_STREAM_LIFECYCLE_01"
    stream_sid = "MZ_STREAM_01"

    # Pre-register call session from inbound webhook
    await session_manager.get_or_create(call_id=call_sid, from_number="+919999999999")

    with client.websocket_connect("/telephony/media-stream") as websocket:
        # 1. Connected event
        websocket.send_text(
            json.dumps({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        )

        # 2. Start event
        websocket.send_text(
            json.dumps(
                {
                    "event": "start",
                    "streamSid": stream_sid,
                    "start": {
                        "streamSid": stream_sid,
                        "accountSid": "AC12345",
                        "callSid": call_sid,
                        "tracks": ["inbound"],
                        "mediaFormat": {
                            "encoding": "audio/x-mulaw",
                            "sampleRate": 8000,
                            "channels": 1,
                        },
                    },
                }
            )
        )

        # Wait briefly for server loop to process start frame
        session = None
        for _ in range(20):
            session = await session_manager.get_by_stream_id(stream_sid)
            if session is not None:
                break
            await asyncio.sleep(0.02)

        assert session is not None
        assert session.call_id == call_sid
        assert session.status == "in-progress"

        # 3. Media event (silent audio chunk)
        dummy_audio_b64 = "////////"  # PCMU silence
        websocket.send_text(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {
                        "track": "inbound",
                        "chunk": "1",
                        "timestamp": "20",
                        "payload": dummy_audio_b64,
                    },
                }
            )
        )

        # 4. Stop event
        websocket.send_text(
            json.dumps(
                {
                    "event": "stop",
                    "streamSid": stream_sid,
                    "stop": {"accountSid": "AC12345", "callSid": call_sid},
                }
            )
        )

    # After websocket closes and stop event processed, stream session should be cleaned up
    session_after = None
    for _ in range(20):
        session_after = await session_manager.get_by_stream_id(stream_sid)
        if session_after is None:
            break
        await asyncio.sleep(0.02)

    assert session_after is None
