import collections
import logging
from voice_call_agent.providers.speech.codec import (
    calculate_rms_energy,
    create_wav,
    mulaw_to_pcm16,
)

logger = logging.getLogger(__name__)


class AudioTurnBuffer:
    """Voice Activity Detection (VAD) buffer for turn-taking telephony.

    Maintains a rolling pre-speech ring buffer. Once speech onset is detected,
    accumulates all audio chunks until the caller stops speaking (silence timeout),
    then returns the complete utterance WAV.
    """

    def __init__(
        self,
        energy_threshold: float = 120.0,
        min_speech_duration_ms: int = 250,
        silence_timeout_ms: int = 700,
        sample_rate: int = 8000,
        pre_speech_ms: int = 300,
        max_utterance_ms: int = 7000,
        chunk_duration_ms: int = 20,
        **kwargs,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.sample_rate = sample_rate
        self.pre_speech_ms = pre_speech_ms
        self.max_utterance_ms = max_utterance_ms

        # Ring buffer for pre-speech audio (stores recent PCM chunks)
        self._pre_buffer: collections.deque[bytes] = collections.deque()
        self._pre_buffer_ms = 0.0

        # Utterance recording buffer (active once speech starts)
        self._recording_chunks: list[bytes] = []
        self._speech_ms: float = 0.0
        self._silence_ms: float = 0.0
        self._is_recording: bool = False

    @property
    def is_speaking(self) -> bool:
        """True if the caller is currently speaking or in active turn."""
        return self._is_recording

    def _chunk_duration_ms(self, pcm16_bytes: bytes) -> float:
        """Duration of a PCM16 chunk in milliseconds."""
        num_samples = len(pcm16_bytes) // 2
        return (num_samples / self.sample_rate) * 1000.0

    def add_chunk(self, audio_chunk: bytes, is_raw_pcm: bool = False) -> bytes | None:
        """Add an 8kHz audio chunk (mu-law or raw 16-bit PCM).

        Returns complete WAV audio bytes when an utterance finishes, or None if still accumulating.
        """
        pcm16 = audio_chunk if is_raw_pcm else mulaw_to_pcm16(audio_chunk)
        energy = calculate_rms_energy(pcm16)
        chunk_ms = self._chunk_duration_ms(pcm16)

        is_voice = energy >= self.energy_threshold

        if not self._is_recording:
            # Not recording yet: update rolling pre-speech ring buffer
            self._pre_buffer.append(pcm16)
            self._pre_buffer_ms += chunk_ms
            while self._pre_buffer_ms > self.pre_speech_ms and len(self._pre_buffer) > 1:
                oldest = self._pre_buffer.popleft()
                self._pre_buffer_ms -= self._chunk_duration_ms(oldest)

            # Check for speech onset
            if is_voice:
                self._is_recording = True
                self._speech_ms = chunk_ms
                self._silence_ms = 0.0
                # Initialize recording buffer with pre-speech context
                self._recording_chunks = list(self._pre_buffer)
                self._pre_buffer.clear()
                self._pre_buffer_ms = 0.0
            return None

        # Active recording turn
        self._recording_chunks.append(pcm16)

        if is_voice:
            self._speech_ms += chunk_ms
            self._silence_ms = 0.0
        else:
            self._silence_ms += chunk_ms

        # Check if turn is complete (silence detected OR reached maximum utterance limit)
        if self._silence_ms >= self.silence_timeout_ms or (self._speech_ms + self._silence_ms) >= self.max_utterance_ms:
            total_speech = self._speech_ms
            assembled_pcm = b"".join(self._recording_chunks)
            self.reset()

            # Discard false triggers (clicks/pops shorter than minimum speech)
            if total_speech < self.min_speech_duration_ms:
                return None

            # Return full utterance WAV
            return create_wav(assembled_pcm, sample_rate=self.sample_rate, channels=1)

        return None

    def reset(self) -> None:
        """Clear all buffers and reset state."""
        self._pre_buffer.clear()
        self._pre_buffer_ms = 0.0
        self._recording_chunks.clear()
        self._speech_ms = 0.0
        self._silence_ms = 0.0
        self._is_recording = False
