import asyncio
import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranscriptionResult:
    text: str
    language: str | None = None
    confidence: float = 1.0


class SpeechToTextProvider(Protocol):
    """Protocol for Speech-to-Text transcription adapters."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio bytes (typically WAV) to text."""
        ...


class MockSpeechToTextProvider(SpeechToTextProvider):
    """Configurable mock STT provider for tests and offline development."""

    def __init__(
        self,
        default_text: str = "Hello, I am looking for a 2BHK property.",
        default_language: str = "en",
    ) -> None:
        self.default_text = default_text
        self.default_language = default_language
        self.transcriptions_queue: list[TranscriptionResult] = []

    def queue_transcription(self, text: str, language: str = "en", confidence: float = 1.0) -> None:
        """Queue a specific transcription result for the next transcribe call."""
        self.transcriptions_queue.append(
            TranscriptionResult(text=text, language=language, confidence=confidence)
        )

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        if self.transcriptions_queue:
            return self.transcriptions_queue.pop(0)

        # Simple heuristic to simulate language recognition
        chosen_lang = language or self.default_language
        return TranscriptionResult(
            text=self.default_text,
            language=chosen_lang,
            confidence=0.98,
        )


class OpenAICompatibleSTT(SpeechToTextProvider):
    """Speech-to-Text provider connecting to OpenAI-compatible /audio/transcriptions endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Send multipart/form-data to /audio/transcriptions endpoint."""
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        url = f"{self.base_url}/audio/transcriptions"

        parts: list[bytes] = []

        # Model field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
        parts.append(f"{self.model}\r\n".encode())

        # Language field (optional, e.g. "te", "hi", "en")
        if language:
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(b'Content-Disposition: form-data; name="language"\r\n\r\n')
            parts.append(f"{language}\r\n".encode())

        # Audio file field
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            b'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            b"Content-Type: audio/wav\r\n\r\n"
        )
        parts.append(audio_bytes)
        parts.append(b"\r\n")

        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        def _send_request() -> bytes:
            with urllib.request.urlopen(req) as resp:
                return resp.read()

        resp_bytes = await asyncio.to_thread(_send_request)
        data = json.loads(resp_bytes.decode("utf-8"))
        return TranscriptionResult(
            text=data.get("text", ""),
            language=language or data.get("language"),
            confidence=1.0,
        )
