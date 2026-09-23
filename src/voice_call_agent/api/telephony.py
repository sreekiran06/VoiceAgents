import asyncio
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
from voice_call_agent.core.context import DEFAULT_CONTEXT
from voice_call_agent.core.context_loader import resolve_business_context
from voice_call_agent.models.conversation import Message
from voice_call_agent.providers.speech.codec import mulaw_to_pcm16, pcm16_to_mulaw
from voice_call_agent.providers.speech.stt import MockSpeechToTextProvider, SpeechToTextProvider
from voice_call_agent.providers.speech.tts import MockTextToSpeechProvider, TextToSpeechProvider
from voice_call_agent.providers.speech.vad import AudioTurnBuffer
from voice_call_agent.providers.telephony import (
    ExotelTelephonyProvider,
    TwilioTelephonyProvider,
    get_telephony_provider,
    session_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])
twilio_provider = TwilioTelephonyProvider()
exotel_provider = ExotelTelephonyProvider()
provider = twilio_provider


class OutboundCallRequest(BaseModel):
    to_number: str
    from_number: str | None = None
    provider: str | None = None  # "twilio" | "exotel"
    app_id: str | None = None  # Exotel App ID (https://my.exotel.com/apps#installed-apps)
    custom_field: str | None = None


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
    base = settings.base_url
    if base.startswith("https://"):
        ws_base = "wss://" + base[8:]
    elif base.startswith("http://"):
        ws_base = "ws://" + base[7:]
    else:
        # Fallback to incoming request host
        scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_base = f"{scheme}://{request.url.netloc}"

    return f"{ws_base}/telephony/media-stream"


# ---------------------------------------------------------------------------
# Exotel PCM streaming helpers
# ---------------------------------------------------------------------------
# Exotel Voicebot applet sends/receives **raw 16-bit 8 kHz mono PCM** (slin).
# Chunks sent back MUST be multiples of 320 bytes.
# Minimum recommended chunk: 3 200 bytes (~200 ms at 8 kHz 16-bit).
EXOTEL_PCM_CHUNK_SIZE = 3200  # 200 ms of 16-bit 8 kHz audio


async def _send_pcm_audio_to_exotel(
    websocket: WebSocket,
    pcm16_bytes: bytes,
    stream_sid: str,
) -> None:
    """Stream PCM16 audio back to Exotel in correctly sized chunks."""
    offset = 0
    while offset < len(pcm16_bytes):
        chunk = pcm16_bytes[offset : offset + EXOTEL_PCM_CHUNK_SIZE]
        # Pad last chunk to a multiple of 320 bytes
        remainder = len(chunk) % 320
        if remainder != 0:
            chunk += b"\x00" * (320 - remainder)
        chunk_b64 = base64.b64encode(chunk).decode("utf-8")
        msg = {
            "event": "media",
            "stream_sid": stream_sid,
            "streamSid": stream_sid,
            "media": {"payload": chunk_b64},
        }
        await websocket.send_text(json.dumps(msg))
        offset += EXOTEL_PCM_CHUNK_SIZE

    # Send a mark to know when playback finishes
    mark_msg = {
        "event": "mark",
        "stream_sid": stream_sid,
        "streamSid": stream_sid,
        "mark": {"name": "playback_done"},
    }
    await websocket.send_text(json.dumps(mark_msg))


async def _send_mulaw_audio_to_twilio(
    websocket: WebSocket,
    mulaw_bytes: bytes,
    stream_sid: str,
) -> None:
    """Stream mu-law audio back to Twilio in 160-byte (20 ms) chunks."""
    async for chunk in orchestrator.chunk_mulaw_stream(mulaw_bytes):
        chunk_b64 = base64.b64encode(chunk).decode("utf-8")
        msg = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {"payload": chunk_b64},
        }
        await websocket.send_text(json.dumps(msg))

    mark_msg = {
        "event": "mark",
        "streamSid": stream_sid,
        "mark": {"name": "playback_done"},
    }
    await websocket.send_text(json.dumps(mark_msg))


# ---------------------------------------------------------------------------
# HTTP webhook endpoints
# ---------------------------------------------------------------------------

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
        if not twilio_provider.verify_signature(url, params, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    call_sid = params.get("CallSid", "")
    from_number = params.get("From")
    to_number = params.get("To")

    if call_sid:
        await session_manager.get_or_create(
            call_id=call_sid,
            from_number=from_number,
            to_number=to_number,
            metadata={"direction": "inbound", "provider": "twilio"},
        )

    stream_url = _get_stream_ws_url(request)
    twiml_content = twilio_provider.generate_connect_twiml(
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
        if not twilio_provider.verify_signature(url, params, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    call_sid = params.get("CallSid", "")
    call_status = params.get("CallStatus", "unknown")

    if call_sid:
        if call_status in ("completed", "failed", "busy", "no-answer", "canceled"):
            await session_manager.remove_session(call_sid)
        else:
            await session_manager.update_status(call_sid, call_status)

    return {"status": "received"}


@router.api_route("/exotel/status", methods=["GET", "POST"])
async def exotel_status_callback(request: Request) -> dict[str, Any]:
    """Handle Exotel call status callback."""
    if request.method == "POST":
        form_data = await request.form()
        params = {k: str(v) for k, v in form_data.items()}
    else:
        params = dict(request.query_params)

    call_sid = params.get("CallSid") or params.get("Sid", "")
    status = params.get("Status") or params.get("CallStatus", "unknown")

    logger.info("Exotel call status update: call_sid=%s status=%s", call_sid, status)
    if call_sid:
        if status in ("completed", "failed", "busy", "no-answer", "canceled"):
            await session_manager.remove_session(call_sid)
        else:
            await session_manager.update_status(call_sid, status)

    return {"status": "received", "provider": "exotel", "call_sid": call_sid}


@router.api_route("/exotel/passthru", methods=["GET", "POST"])
async def exotel_passthru_callback(request: Request) -> Response:
    """Handle Exotel Passthru / Voicebot applet callback connected to LLM."""
    if request.method == "POST":
        form_data = await request.form()
        params = {k: str(v) for k, v in form_data.items()}
    else:
        params = dict(request.query_params)

    call_sid = params.get("CallSid") or params.get("Sid", "exo_inbound")
    from_number = params.get("From") or params.get("Caller", "unknown")
    to_number = params.get("To") or settings.exotel_caller_id
    user_speech_or_digits = (
        params.get("SpeechResult")
        or params.get("Digits")
        or params.get("Body")
    )

    session = await session_manager.get_or_create(
        call_id=call_sid,
        from_number=from_number,
        to_number=to_number,
        metadata={"direction": "inbound", "provider": "exotel"},
    )

    action_url = f"{settings.public_base_url.rstrip('/')}/telephony/exotel/passthru"

    try:
        # If caller provided speech / digit input, run through LLM turn
        if user_speech_or_digits and user_speech_or_digits not in ("trans", "incomplete", "completed"):
            response_text, _audio, _tools = await orchestrator.handle_turn(session, user_speech_or_digits)
        elif not session.messages:
            # Initial greeting from LLM
            initial_prompt = f"Customer just connected from number {from_number}. Greet them in Telugu and English, and offer your help."
            response_text, _audio, _tools = await orchestrator.handle_turn(session, initial_prompt)
        else:
            response_text = "మీకు ఇంకా ఏమైనా సహాయం కావాలా? (How else may I help you?)"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error processing LLM turn for Exotel call: %s", exc)
        response_text = "నమస్కారం! SK Voice Agents కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?"

    exoml = exotel_provider.generate_exoml_gather(say_text=response_text, action_url=action_url)
    return Response(content=exoml, media_type="application/xml")



@router.post("/call")
async def place_outbound_call(payload: OutboundCallRequest, request: Request) -> dict[str, Any]:
    """Initiate an outbound call to a telephone number connecting to the voice agent."""
    target_provider_name = payload.provider or settings.telephony_provider
    selected_provider = get_telephony_provider(target_provider_name)

    if isinstance(selected_provider, ExotelTelephonyProvider):
        callback_url = f"{settings.public_base_url.rstrip('/')}/telephony/exotel/status"
        result = await selected_provider.make_outbound_call(
            to_number=payload.to_number,
            callback_url=callback_url,
            from_number=payload.from_number,
            app_id=payload.app_id,
            custom_field=payload.custom_field,
        )
    else:
        callback_url = f"{settings.public_base_url.rstrip('/')}/telephony/inbound"
        result = await selected_provider.make_outbound_call(
            to_number=payload.to_number,
            callback_url=callback_url,
            from_number=payload.from_number,
        )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


# ---------------------------------------------------------------------------
# WebSocket media stream (Twilio + Exotel Voicebot)
# ---------------------------------------------------------------------------

@router.websocket("/media-stream")
async def media_stream_websocket(websocket: WebSocket) -> None:
    """Bi-directional audio WebSocket stream for telephony audio packets.

    Supports both Twilio (mu-law) and Exotel Voicebot (raw 16-bit 8 kHz PCM).
    """
    await websocket.accept()
    stream_sid: str | None = None
    call_sid: str | None = None
    vad = AudioTurnBuffer()
    is_agent_speaking = False
    is_exotel = (settings.telephony_provider == "exotel")  # Default to configured provider

    logger.info("WebSocket media-stream connection accepted (is_exotel=%s)", is_exotel)

    try:
        while True:
            raw_message = await websocket.receive_text()
            data = json.loads(raw_message)
            event_type = data.get("event")

            if event_type == "connected":
                logger.info("Media stream connected: protocol=%s", data.get("protocol", "unknown"))

            elif event_type == "start":
                start_data = data.get("start", {})
                logger.info("EXOTEL START PAYLOAD: %s", json.dumps(data))
                stream_sid = (
                    data.get("stream_sid")
                    or data.get("streamSid")
                    or start_data.get("stream_sid")
                    or start_data.get("streamSid")
                )
                call_sid = (
                    start_data.get("call_sid")
                    or start_data.get("callSid")
                    or start_data.get("custom_parameters", {}).get("call_sid")
                    or start_data.get("customParameters", {}).get("callSid")
                    or stream_sid
                )

                # Detect Exotel vs Twilio:
                # Exotel uses snake_case keys (stream_sid, call_sid, account_sid)
                # Twilio uses camelCase keys (streamSid, callSid, accountSid)
                has_exotel_keys = (
                    "stream_sid" in data
                    or "stream_sid" in start_data
                    or "call_sid" in start_data
                    or "account_sid" in start_data
                )
                has_twilio_keys = (
                    "streamSid" in data
                    or "streamSid" in start_data
                    or "callSid" in start_data
                )
                media_format = start_data.get("media_format") or start_data.get("mediaFormat", {})
                encoding = str(media_format.get("encoding", "")).lower()

                if has_exotel_keys or "raw" in encoding or "slin" in encoding or "pcm" in encoding:
                    is_exotel = True
                elif has_twilio_keys or "mulaw" in encoding or "ulaw" in encoding:
                    is_exotel = False
                else:
                    is_exotel = (settings.telephony_provider == "exotel")

                if stream_sid and call_sid:
                    # Resolve destination number → BusinessContext
                    to_number_raw = (
                        start_data.get("to")
                        or start_data.get("To")
                        or start_data.get("custom_parameters", {}).get("to")
                        or start_data.get("customParameters", {}).get("To")
                        or settings.exotel_caller_id
                    )
                    try:
                        context = await resolve_business_context(to_number_raw or "")
                    except Exception as ctx_err:  # noqa: BLE001
                        logger.warning("Failed to resolve business context: %s", ctx_err)
                        context = DEFAULT_CONTEXT

                    session = await session_manager.get_or_create(
                        call_id=call_sid,
                        metadata={
                            "direction": "inbound",
                            "provider": "exotel" if is_exotel else "twilio",
                            "encoding": "pcm16" if is_exotel else "mulaw",
                            "business_id": context.business_id,
                        },
                    )
                    session.business_id = context.business_id
                    session.business_context = context
                    await session_manager.link_stream(stream_sid, call_sid)

                    logger.info(
                        "Business context resolved: %s → %s (%s)",
                        to_number_raw, context.business_id, context.business_name,
                    )

                    # Send initial greeting from business context
                    try:
                        greeting_text = context.greeting_text
                        session.messages.append(Message(role="assistant", content=greeting_text))

                        # Determine greeting language from context
                        greeting_lang = context.languages[0] if context.languages else "te-IN"
                        logger.info("Synthesizing greeting for %s stream (is_exotel=%s, lang=%s)", stream_sid, is_exotel, greeting_lang)
                        greeting_res = await orchestrator.tts.synthesize(greeting_text, language=greeting_lang)

                        if greeting_res and greeting_res.audio_mulaw_bytes:
                            vad.reset()
                            is_agent_speaking = True

                            if is_exotel:
                                # Convert mu-law → PCM16 for Exotel
                                pcm16_audio = mulaw_to_pcm16(greeting_res.audio_mulaw_bytes)
                                logger.info(
                                    "Sending greeting PCM to Exotel: %d bytes (%d ms)",
                                    len(pcm16_audio),
                                    len(pcm16_audio) // 16,  # 8000 Hz * 2 bytes = 16 bytes/ms
                                )
                                await _send_pcm_audio_to_exotel(websocket, pcm16_audio, stream_sid)
                            else:
                                # Twilio: send mu-law chunks
                                await _send_mulaw_audio_to_twilio(
                                    websocket, greeting_res.audio_mulaw_bytes, stream_sid
                                )

                            vad.reset()
                            is_agent_speaking = False
                            logger.info("Greeting sent successfully for stream %s", stream_sid)
                    except Exception as err:  # noqa: BLE001
                        logger.exception("Error sending initial greeting: %s", err)
                        is_agent_speaking = False

                logger.info(
                    "Stream started: stream_sid=%s call_sid=%s is_exotel=%s",
                    stream_sid, call_sid, is_exotel,
                )

            elif event_type == "media":
                payload_str = data.get("media", {}).get("payload", "")
                if not stream_sid:
                    stream_sid = data.get("stream_sid") or data.get("streamSid")

                if payload_str and stream_sid:
                    chunk_bytes = base64.b64decode(payload_str)

                    # Interruption: caller speaking while agent is talking
                    if is_agent_speaking and vad.is_speaking:
                        logger.info("Interruption detected on stream %s; clearing output", stream_sid)
                        clear_msg = {
                            "event": "clear",
                            "stream_sid": stream_sid,
                            "streamSid": stream_sid,
                        }
                        await websocket.send_text(json.dumps(clear_msg))
                        is_agent_speaking = False

                    # Feed audio into VAD (is_raw_pcm=True for Exotel)
                    utterance_wav = vad.add_chunk(chunk_bytes, is_raw_pcm=is_exotel)

                    if utterance_wav is not None:
                        wav_len = len(utterance_wav)
                        logger.info("Utterance detected on stream %s (%d bytes WAV), transcribing...", stream_sid, wav_len)

                        # Save latest utterance for debugging
                        try:
                            with open("/tmp/latest_utterance.wav", "wb") as f:
                                f.write(utterance_wav)
                        except Exception:
                            pass

                        # Run STT concurrently across supported languages
                        transcription = None
                        languages_to_try = settings.sarvam_language_list or ["te-IN", "en-IN", "hi-IN"]
                        tasks = [stt_provider.transcribe(utterance_wav, language=lc) for lc in languages_to_try]
                        results = await asyncio.gather(*tasks, return_exceptions=True)

                        best_result = None
                        for lc, res in zip(languages_to_try, results):
                            if isinstance(res, Exception):
                                logger.warning("STT [%s] error for stream %s: %s", lc, stream_sid, res)
                                continue
                            logger.info("STT [%s] for %s: text='%s'", lc, stream_sid, res.text)
                            if res.text and res.text.strip():
                                if best_result is None or len(res.text) > len(best_result.text):
                                    best_result = res

                        transcription = best_result

                        if transcription and transcription.text and transcription.text.strip():
                            logger.info(
                                "Recognized speech for stream %s: '%s' (lang: %s)",
                                stream_sid,
                                transcription.text,
                                transcription.language,
                            )
                            session = await session_manager.get_by_stream_id(stream_sid)
                            if session:
                                try:
                                    _text, audio_mulaw, _tools = await orchestrator.handle_turn(
                                        session, transcription.text
                                    )
                                    logger.info(
                                        "LLM response for stream %s: '%s' (%d bytes audio)",
                                        stream_sid,
                                        _text[:80] if _text else "(empty)",
                                        len(audio_mulaw) if audio_mulaw else 0,
                                    )
                                except Exception as llm_err:  # noqa: BLE001
                                    logger.exception("LLM error on stream %s: %s", stream_sid, llm_err)
                                    # Use business context fallback or default Telugu
                                    sess_ctx = session.business_context if session else None
                                    fallback = sess_ctx.fallback_message if sess_ctx else "క్షమించండి, మీ మాట సరిగ్గా వినిపించలేదు. దయచేసి మళ్ళీ చెప్పగలరా?"
                                    fallback_lang = sess_ctx.languages[0] if sess_ctx and sess_ctx.languages else "te-IN"
                                    tts_result = await orchestrator.tts.synthesize(fallback, language=fallback_lang)
                                    audio_mulaw = tts_result.audio_mulaw_bytes
                                    _text = fallback

                                if audio_mulaw:
                                    vad.reset()
                                    is_agent_speaking = True

                                    if is_exotel:
                                        pcm16_audio = mulaw_to_pcm16(audio_mulaw)
                                        await _send_pcm_audio_to_exotel(websocket, pcm16_audio, stream_sid)
                                    else:
                                        await _send_mulaw_audio_to_twilio(
                                            websocket, audio_mulaw, stream_sid
                                        )

                                    vad.reset()
                                    is_agent_speaking = False
                        else:
                            logger.debug("Empty transcription on stream %s, ignoring", stream_sid)

            elif event_type == "dtmf":
                digit = data.get("dtmf", {}).get("digit", "")
                logger.info("DTMF digit received on stream %s: %s", stream_sid, digit)

            elif event_type == "mark":
                logger.debug("Playback mark reached: %s", data.get("mark", {}).get("name"))

            elif event_type == "stop":
                logger.info("Media stream stop event received for stream_sid=%s", stream_sid)
                if stream_sid:
                    await session_manager.remove_by_stream_id(stream_sid)
                break

    except WebSocketDisconnect:
        logger.info("Media stream WebSocket disconnected for stream_sid=%s", stream_sid)
    except Exception:
        logger.exception("Unexpected error in media stream for stream_sid=%s", stream_sid)
    finally:
        if stream_sid:
            await session_manager.remove_by_stream_id(stream_sid)
