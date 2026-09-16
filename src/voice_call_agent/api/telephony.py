import base64
import json
import logging
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel

from voice_call_agent.agent.orchestrator import VoiceAgentOrchestrator
from voice_call_agent.core.config import settings
from voice_call_agent.models.conversation import Message
from voice_call_agent.providers.speech.stt import MockSpeechToTextProvider, SpeechToTextProvider
from voice_call_agent.providers.speech.tts import MockTextToSpeechProvider, TextToSpeechProvider
from voice_call_agent.providers.speech.vad import AudioTurnBuffer
from voice_call_agent.providers.telephony import TwilioTelephonyProvider, session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])
provider = TwilioTelephonyProvider()


class OutboundCallRequest(BaseModel):
    to_number: str
    from_number: str | None = None


def _init_speech_providers() -> tuple[SpeechToTextProvider, VoiceAgentOrchestrator]:
    if settings.sarvam_api_key:
        from voice_call_agent.providers.speech.sarvam import SarvamSTT, SarvamTTS
        stt = SarvamSTT(
            api_key=settings.sarvam_api_key,
            default_languages=settings.sarvam_language_list,
        )
        tts = SarvamTTS(
            api_key=settings.sarvam_api_key,
            default_languages=settings.sarvam_language_list,
            voice_map=settings.sarvam_voice_map,
            pace=settings.sarvam_pace,
        )
        orch = VoiceAgentOrchestrator(tts=tts)
        return stt, orch
    return MockSpeechToTextProvider(), VoiceAgentOrchestrator()


stt_provider, orchestrator = _init_speech_providers()


def _get_stream_ws_url(request: Request) -> str:
    """Derive the WebSocket URL for the media stream from settings or request."""
    base = settings.public_base_url.rstrip("/")
    if base.startswith("https://"):
        ws_base = "wss://" + base[8:]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[7:]
    else:
        # Fallback to incoming request host
        scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_base = f"{scheme}://{request.url.netloc}"

    return f"{ws_base}/telephony/media-stream"


@router.post("/inbound")
async def inbound_call_webhook(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header()] = None,
) -> Response:
    """Handle incoming call webhook from telephony provider and return TwiML."""
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}

    if settings.validate_telephony_signatures:
        if not x_twilio_signature:
            raise HTTPException(status_code=403, detail="Missing signature header")
        url = str(request.url)
        if not provider.verify_signature(url, params, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    call_sid = params.get("CallSid", "")
    from_number = params.get("From")
    to_number = params.get("To")

    if call_sid:
        await session_manager.get_or_create(
            call_id=call_sid,
            from_number=from_number,
            to_number=to_number,
            metadata={"direction": "inbound"},
        )

    stream_url = _get_stream_ws_url(request)
    twiml_content = provider.generate_connect_twiml(
        stream_url=stream_url,
        call_sid=call_sid,
    )

    return Response(content=twiml_content, media_type="application/xml")


@router.post("/status")
async def call_status_webhook(
    request: Request,
    x_twilio_signature: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Handle call status callbacks (e.g. ringing, in-progress, completed)."""
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}

    if settings.validate_telephony_signatures:
        if not x_twilio_signature:
            raise HTTPException(status_code=403, detail="Missing signature header")
        url = str(request.url)
        if not provider.verify_signature(url, params, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    call_sid = params.get("CallSid", "")
    call_status = params.get("CallStatus", "unknown")

    if call_sid:
        if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
            await session_manager.remove_session(call_sid)
        else:
            await session_manager.update_status(call_sid, call_status)

    return {"status": "received"}


@router.post("/call")
async def place_outbound_call(payload: OutboundCallRequest, request: Request) -> dict[str, Any]:
    """Initiate an outbound call to a telephone number connecting to the voice agent."""
    callback_url = f"{settings.public_base_url.rstrip('/')}/telephony/inbound"
    result = await provider.make_outbound_call(
        to_number=payload.to_number,
        callback_url=callback_url,
        from_number=payload.from_number,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.websocket("/media-stream")
async def media_stream_websocket(websocket: WebSocket) -> None:
    """Bi-directional audio WebSocket stream for telephony audio packets."""
    await websocket.accept()
    stream_sid: str | None = None
    vad = AudioTurnBuffer()
    is_agent_speaking = False

    try:
        while True:
            raw_message = await websocket.receive_text()
            data = json.loads(raw_message)
            event_type = data.get("event")

            if event_type == "connected":
                logger.info("Media stream connected: %s", data.get("protocol"))

            elif event_type == "start":
                start_data = data.get("start", {})
                stream_sid = data.get("streamSid") or start_data.get("streamSid")
                call_sid = (
                    start_data.get("callSid")
                    or start_data.get("customParameters", {}).get("callSid")
                )
                if stream_sid and call_sid:
                    # Ensure session exists (web phone calls skip /inbound webhook)
                    session = await session_manager.get_or_create(
                        call_id=call_sid,
                        metadata={"direction": "web"},
                    )
                    await session_manager.link_stream(stream_sid, call_sid)

                    # For web browser calls, greet the caller immediately upon connection
                    if session.metadata.get("direction") == "web":
                        try:
                            greeting_text = "నమస్కారం! SK Voice Agents కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?"
                            session.messages.append(Message(role="assistant", content=greeting_text))
                            greeting_res = await orchestrator.tts.synthesize(greeting_text, language="te-IN")
                            if greeting_res and greeting_res.audio_mulaw_bytes:
                                vad.reset()
                                is_agent_speaking = True
                                async for chunk in orchestrator.chunk_mulaw_stream(greeting_res.audio_mulaw_bytes):
                                    chunk_b64 = base64.b64encode(chunk).decode("utf-8")
                                    await websocket.send_text(
                                        json.dumps(provider.create_media_message(stream_sid, chunk_b64))
                                    )
                                mark_msg = provider.create_mark_message(stream_sid, "greeting_complete")
                                await websocket.send_text(json.dumps(mark_msg))
                                vad.reset()
                                is_agent_speaking = False
                        except Exception as err:  # noqa: BLE001
                            logger.error("Error sending initial greeting: %s", err)
                logger.info("Stream started: stream_sid=%s call_sid=%s", stream_sid, call_sid)

            elif event_type == "media":
                payload_str = data.get("media", {}).get("payload", "")
                if payload_str and stream_sid:
                    chunk_bytes = base64.b64decode(payload_str)

                    # Interruption check: If caller interrupts agent playback, send clear event
                    if is_agent_speaking and vad.is_speaking:
                        logger.info("Interruption detected on stream %s; clearing output", stream_sid)
                        clear_msg = provider.create_clear_message(stream_sid)
                        await websocket.send_text(json.dumps(clear_msg))
                        is_agent_speaking = False

                    utterance_wav = vad.add_chunk(chunk_bytes)
                    if utterance_wav is not None:
                        transcription = await stt_provider.transcribe(utterance_wav)
                        if transcription.text and transcription.text.strip():
                            session = await session_manager.get_by_stream_id(stream_sid)
                            if session:
                                _text, audio_mulaw, _tools = await orchestrator.handle_turn(
                                    session, transcription.text
                                )
                                vad.reset()
                                is_agent_speaking = True
                                async for chunk in orchestrator.chunk_mulaw_stream(audio_mulaw):
                                    if not is_agent_speaking:
                                        break
                                    chunk_b64 = base64.b64encode(chunk).decode("utf-8")
                                    await websocket.send_text(
                                        json.dumps(provider.create_media_message(stream_sid, chunk_b64))
                                    )
                                if is_agent_speaking:
                                    mark_msg = provider.create_mark_message(stream_sid, "turn_complete")
                                    await websocket.send_text(json.dumps(mark_msg))
                                    vad.reset()
                                    is_agent_speaking = False

            elif event_type == "mark":
                logger.debug("Playback mark reached: %s", data.get("mark", {}).get("name"))

            elif event_type == "stop":
                logger.info("Media stream stop event received for stream_sid=%s", stream_sid)
                if stream_sid:
                    await session_manager.remove_by_stream_id(stream_sid)
                break

    except WebSocketDisconnect:
        logger.info("Media stream WebSocket disconnected for stream_sid=%s", stream_sid)
    finally:
        if stream_sid:
            await session_manager.remove_by_stream_id(stream_sid)
