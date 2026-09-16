"""Sarvam AI speech providers.

STT: Saaras v2 — 22 Indian languages + English, REST transcription endpoint.
TTS: Bulbul v1 — Indian-language TTS, returns PCM WAV, downsampled to 8 kHz mu-law
     for telephony (Twilio/Telnyx).

API reference: https://docs.sarvam.ai
Get a key at: https://dashboard.sarvam.ai
"""

from __future__ import annotations

import asyncio
import base64
import json
import struct
import urllib.error
import urllib.request
import uuid

from voice_call_agent.providers.speech.codec import pcm16_to_mulaw
from voice_call_agent.providers.speech.stt import SpeechToTextProvider, TranscriptionResult
from voice_call_agent.providers.speech.tts import SynthesisResult, TextToSpeechProvider

_SARVAM_BASE = "https://api.sarvam.ai"

# ---------------------------------------------------------------------------
# Language helpers
# ---------------------------------------------------------------------------

# BCP-47 codes recognised by both Saaras and Bulbul
SARVAM_LANGUAGES: dict[str, str] = {
    "hi": "hi-IN",   # Hindi
    "en": "en-IN",   # Indian English
    "bn": "bn-IN",   # Bengali
    "ta": "ta-IN",   # Tamil
    "te": "te-IN",   # Telugu
    "mr": "mr-IN",   # Marathi
    "gu": "gu-IN",   # Gujarati
    "kn": "kn-IN",   # Kannada
    "ml": "ml-IN",   # Malayalam
    "pa": "pa-IN",   # Punjabi
    "od": "od-IN",   # Odia
    "ur": "ur-IN",   # Urdu
}


def _resolve_language(language: str | None, default: str = "hi-IN") -> str:
    """Normalize a short language code or BCP-47 tag to what Sarvam expects."""
    if not language:
        return default
    if "-" in language:
        return language  # already BCP-47
    return SARVAM_LANGUAGES.get(language, f"{language}-IN")


# ---------------------------------------------------------------------------
# Speech-to-Text  (Saaras v2)
# ---------------------------------------------------------------------------

class SarvamSTT(SpeechToTextProvider):
    """Speech-to-Text provider using Sarvam AI Saaras v2.

    Accepts telephony-ready 8 kHz mu-law audio (via :func:`create_wav`) or any
    WAV bytes and returns a :class:`TranscriptionResult`.

    Args:
        api_key: Sarvam API subscription key (``sk_…``).
        model: Model identifier; ``saaras:v2`` (default) or ``saaras:v1``.
        default_languages: Ordered list of BCP-47 language codes. The first
            entry is used when the caller does not specify a language.
            Defaults to ``["en-IN", "te-IN", "hi-IN"]``.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "saarika:v2.5",
        default_languages: list[str] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.default_languages: list[str] = default_languages or ["en-IN", "te-IN", "hi-IN"]

    @property
    def primary_language(self) -> str:
        """The first (primary/fallback) language in the default list."""
        return self.default_languages[0] if self.default_languages else "en-IN"

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe *audio_bytes* (WAV format) using Sarvam Saaras.

        If *language* is ``None``, the primary language from
        :attr:`default_languages` is used.

        Returns:
            :class:`TranscriptionResult` with ``text`` and detected/requested
            ``language``.
        """
        lang = _resolve_language(language, self.primary_language)
        boundary = f"----SarvamBoundary{uuid.uuid4().hex}"
        url = f"{_SARVAM_BASE}/speech-to-text"

        parts: list[bytes] = []

        # file field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n"
        )
        parts.append(audio_bytes)
        parts.append(b"\r\n")

        # model field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
        parts.append(f"{self.model}\r\n".encode())

        # language_code field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="language_code"\r\n\r\n')
        parts.append(f"{lang}\r\n".encode())

        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "api-subscription-key": self.api_key,
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        def _send() -> bytes:
            with urllib.request.urlopen(req) as resp:
                return resp.read()

        try:
            resp_bytes = await asyncio.to_thread(_send)
            data = json.loads(resp_bytes.decode("utf-8"))
            return TranscriptionResult(
                text=data.get("transcript", ""),
                language=lang,
                confidence=1.0,
            )
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Sarvam STT error {exc.code}: {body_err}"
            ) from exc


# ---------------------------------------------------------------------------
# Text-to-Speech  (Bulbul v1)
# ---------------------------------------------------------------------------

# Built-in fallback voices per language (used when no voice_map entry exists)
# All names are valid Sarvam Bulbul speaker identifiers.
_DEFAULT_VOICES: dict[str, str] = {
    "hi-IN": "ritu",          # Hindi — neutral, widely used
    "en-IN": "ishita",        # Indian English — clear, customer-facing
    "ta-IN": "gokul",         # Tamil
    "te-IN": "kavitha",       # Telugu
    "kn-IN": "chaitra",       # Kannada
    "ml-IN": "ritu",          # Malayalam (fallback)
    "bn-IN": "roopa",         # Bengali
    "mr-IN": "rupali",        # Marathi
    "gu-IN": "pooja",         # Gujarati
    "pa-IN": "anand",         # Punjabi
}


def _detect_script_language(text: str, default: str) -> str:
    """Detect Indian language script from Unicode code points."""
    for ch in text:
        code = ord(ch)
        if 0x0C00 <= code <= 0x0C7F:
            return "te-IN"
        if 0x0900 <= code <= 0x097F:
            return "hi-IN"
        if 0x0B80 <= code <= 0x0BFF:
            return "ta-IN"
        if 0x0C80 <= code <= 0x0CFF:
            return "kn-IN"
    return default


class SarvamTTS(TextToSpeechProvider):
    """Text-to-Speech provider using Sarvam AI Bulbul v1.

    The Sarvam TTS endpoint returns a base64-encoded WAV (16-bit PCM at
    22 050 Hz).  This provider:

    1. Decodes the base64 payload.
    2. Strips the 44-byte WAV header to get raw PCM samples.
    3. Down-samples from 22 050 Hz \u2192 8 000 Hz (integer decimation ~2.75\u00d7,
       using simple decimation with anti-aliasing by averaging).
    4. Encodes the 8 kHz PCM to ITU-T G.711 mu-law for telephony.

    Args:
        api_key: Sarvam API subscription key (``sk_\u2026``).
        model: Model identifier; ``bulbul:v1`` (default).
        default_languages: Ordered list of BCP-47 language codes. The first
            entry is the primary used when the caller omits language.
            Defaults to ``["en-IN", "te-IN", "hi-IN"]``.
        voice_map: Dict mapping BCP-47 codes to speaker names, e.g.
            ``{"en-IN": "maya", "te-IN": "arvind", "hi-IN": "meera"}``.
            Entries here take priority over the built-in :data:`_DEFAULT_VOICES`.
        pace: Speech pace multiplier (0.5 \u2013 2.0).  1.0 is neutral.
    """

    _SARVAM_SAMPLE_RATE = 22050  # Hz returned by Bulbul
    _TARGET_SAMPLE_RATE = 8000   # Hz required by Twilio/Telnyx mu-law

    def __init__(
        self,
        api_key: str,
        model: str = "bulbul:v3",
        default_languages: list[str] | None = None,
        voice_map: dict[str, str] | None = None,
        pace: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.default_languages: list[str] = default_languages or ["en-IN", "te-IN", "hi-IN"]
        # Merge caller-supplied map on top of built-in defaults
        self.voice_map: dict[str, str] = {**_DEFAULT_VOICES, **(voice_map or {})}
        self.pace = pace

    @property
    def primary_language(self) -> str:
        """The first (primary/fallback) language in the default list."""
        return self.default_languages[0] if self.default_languages else "en-IN"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resample_22050_to_8000(pcm16_bytes: bytes) -> bytes:
        """Downsample 22 050 Hz 16-bit PCM to 8 000 Hz using averaging decimation.

        Decimation factor: 22050 / 8000 = 2.75625.
        We use a rational approximation: keep every Nth sample via simple
        polyphase averaging (3-tap) to reduce aliasing without scipy.
        """
        num_in = len(pcm16_bytes) // 2
        if num_in == 0:
            return b""
        samples_in = struct.unpack(f"<{num_in}h", pcm16_bytes[: num_in * 2])

        # Rational ratio: 22050 / 8000 = 441/160
        # For every output sample i, the centre input index is i * 441/160.
        # We average a 3-sample window around that index.
        num_out = int(num_in * 8000 / 22050)
        out: list[int] = []
        ratio = 22050 / 8000

        for i in range(num_out):
            centre = i * ratio
            lo = max(0, int(centre) - 1)
            hi = min(num_in - 1, int(centre) + 1)
            window = samples_in[lo : hi + 1]
            out.append(int(sum(window) / len(window)))

        return struct.pack(f"<{len(out)}h", *out)

    def _pick_voice(self, language: str, voice: str | None) -> str:
        """Resolve the speaker name for *language*.

        Priority: explicit ``voice`` arg > ``voice_map`` entry > built-in default.
        """
        if voice:
            return voice
        return self.voice_map.get(language, _DEFAULT_VOICES.get(language, "meera"))

    # ------------------------------------------------------------------
    # Protocol implementation
    # ------------------------------------------------------------------

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> SynthesisResult:
        """Synthesize *text* and return telephony-ready 8 kHz mu-law audio.

        If *language* is ``None``, the primary language from
        :attr:`default_languages` is used.
        """
        fallback_lang = _detect_script_language(text, self.primary_language)
        lang = _resolve_language(language, fallback_lang)
        speaker = self._pick_voice(lang, voice)

        payload = {
            "inputs": [text],
            "target_language_code": lang,
            "speaker": speaker,
            "model": self.model,
            "pace": self.pace,
            "enable_preprocessing": True,
        }

        req = urllib.request.Request(
            f"{_SARVAM_BASE}/text-to-speech",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _send() -> bytes:
            with urllib.request.urlopen(req) as resp:
                return resp.read()

        try:
            resp_bytes = await asyncio.to_thread(_send)
            data = json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Sarvam TTS error {exc.code}: {body_err}"
            ) from exc

        # Sarvam returns a list of base64-encoded WAV audios
        audios: list[str] = data.get("audios", [])
        if not audios:
            raise RuntimeError("Sarvam TTS returned no audio data")

        # Decode base64 → WAV bytes
        wav_bytes = base64.b64decode(audios[0])

        # Strip the standard 44-byte RIFF/WAV header to get raw PCM
        pcm22k = wav_bytes[44:]

        # Downsample 22 050 → 8 000 Hz
        pcm8k = self._resample_22050_to_8000(pcm22k)

        # Encode to mu-law
        mulaw_bytes = pcm16_to_mulaw(pcm8k)
        duration = len(pcm8k) / (self._TARGET_SAMPLE_RATE * 2)  # 16-bit → bytes/2

        return SynthesisResult(
            audio_mulaw_bytes=mulaw_bytes,
            duration_seconds=duration,
        )
