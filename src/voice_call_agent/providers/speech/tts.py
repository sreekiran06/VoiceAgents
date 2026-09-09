import asyncio
import json
import math
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from voice_call_agent.providers.speech.codec import pcm16_to_mulaw


@dataclass
class SynthesisResult:
    audio_mulaw_bytes: bytes
    duration_seconds: float


class TextToSpeechProvider(Protocol):
    """Protocol for Text-to-Speech synthesis adapters."""

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> SynthesisResult:
        """Synthesize text into telephony-ready 8kHz mu-law audio bytes."""
        ...


class MockTextToSpeechProvider(TextToSpeechProvider):
    """Mock TTS provider generating synthetic 8kHz mu-law audio chunks for testing."""

    def __init__(self, tone_frequency: float = 440.0) -> None:
        self.tone_frequency = tone_frequency

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> SynthesisResult:
        # Approximate duration based on word count (~150 words per minute -> ~0.4s per word)
        words = max(1, len(text.split()))
        duration = min(5.0, max(0.4, words * 0.35))

        # Generate 8000 Hz 16-bit PCM sinusoidal tone
        sample_rate = 8000
        num_samples = int(sample_rate * duration)
        pcm_samples = []
        for i in range(num_samples):
            # Soft sine wave to avoid clipping
            val = int(8000 * math.sin(2 * math.pi * self.tone_frequency * (i / sample_rate)))
            pcm_samples.append(val)

        pcm16_bytes = struct.pack(f"<{num_samples}h", *pcm_samples)
        mulaw_bytes = pcm16_to_mulaw(pcm16_bytes)

        return SynthesisResult(
            audio_mulaw_bytes=mulaw_bytes,
            duration_seconds=duration,
        )


class OpenAICompatibleTTS(TextToSpeechProvider):
    """Text-to-Speech provider connecting to OpenAI-compatible /audio/speech endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "tts-1",
        default_voice: str = "alloy",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.default_voice = default_voice

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> SynthesisResult:
        """Request PCM audio from speech endpoint and convert to 8kHz mu-law."""
        url = f"{self.base_url}/audio/speech"
        payload = {
            "model": self.model,
            "input": text,
            "voice": voice or self.default_voice,
            "response_format": "pcm",  # 24kHz 16-bit PCM by default
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        def _send_request() -> bytes:
            with urllib.request.urlopen(req) as resp:
                return resp.read()

        raw_pcm24k = await asyncio.to_thread(_send_request)

        # Simple downsampling from 24kHz to 8kHz (factor of 3)
        num_samples_24k = len(raw_pcm24k) // 2
        samples_24k = struct.unpack(f"<{num_samples_24k}h", raw_pcm24k[: num_samples_24k * 2])
        samples_8k = samples_24k[::3]
        pcm16_8k = struct.pack(f"<{len(samples_8k)}h", *samples_8k)

        mulaw_bytes = pcm16_to_mulaw(pcm16_8k)
        duration = len(samples_8k) / 8000.0

        return SynthesisResult(
            audio_mulaw_bytes=mulaw_bytes,
            duration_seconds=duration,
        )
