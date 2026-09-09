from voice_call_agent.providers.speech.codec import (
    calculate_rms_energy,
    create_wav,
    mulaw_to_pcm16,
)


class AudioTurnBuffer:
    """Voice Activity Detection (VAD) audio buffer for turn-taking telephony.

    Accumulates 8kHz mu-law audio chunks (e.g. 20ms / 160 bytes), detects speech onset,
    and returns a full utterance WAV once the caller has finished speaking.
    """

    def __init__(
        self,
        energy_threshold: float = 400.0,
        min_speech_duration_ms: int = 300,
        silence_timeout_ms: int = 700,
        chunk_duration_ms: int = 20,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.min_speech_frames = max(1, min_speech_duration_ms // chunk_duration_ms)
        self.silence_frames_threshold = max(1, silence_timeout_ms // chunk_duration_ms)

        self._audio_chunks: list[bytes] = []
        self._pcm_chunks: list[bytes] = []
        self._speech_frames_count = 0
        self._silence_frames_count = 0
        self._has_speech_started = False

    @property
    def is_speaking(self) -> bool:
        """True if the caller has started speaking and has not yet completed the turn."""
        return self._has_speech_started

    def add_chunk(self, mulaw_chunk: bytes) -> bytes | None:
        """Add an 8kHz mu-law chunk.

        Returns complete WAV audio bytes when an utterance finishes, or None if still accumulating.
        """
        pcm16 = mulaw_to_pcm16(mulaw_chunk)
        energy = calculate_rms_energy(pcm16)

        if energy >= self.energy_threshold:
            self._speech_frames_count += 1
            self._silence_frames_count = 0
            if self._speech_frames_count >= self.min_speech_frames:
                self._has_speech_started = True
            self._audio_chunks.append(mulaw_chunk)
            self._pcm_chunks.append(pcm16)
            return None

        # Energy is below threshold (silence / background noise)
        if self._has_speech_started:
            self._silence_frames_count += 1
            self._audio_chunks.append(mulaw_chunk)
            self._pcm_chunks.append(pcm16)

            if self._silence_frames_count >= self.silence_frames_threshold:
                # Turn completed! Return the assembled WAV
                assembled_pcm = b"".join(self._pcm_chunks)
                wav_bytes = create_wav(assembled_pcm, sample_rate=8000, channels=1)
                self.reset()
                return wav_bytes

        # If speech hasn't started, retain rolling window of trailing frames for pre-speech buffer
        self._audio_chunks.append(mulaw_chunk)
        self._pcm_chunks.append(pcm16)
        if len(self._audio_chunks) > 10:  # Keep ~200ms pre-speech audio
            self._audio_chunks.pop(0)
            self._pcm_chunks.pop(0)

        return None

    def reset(self) -> None:
        """Clear all buffers and reset state."""
        self._audio_chunks.clear()
        self._pcm_chunks.clear()
        self._speech_frames_count = 0
        self._silence_frames_count = 0
        self._has_speech_started = False
