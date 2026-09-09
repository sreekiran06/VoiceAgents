import math
import struct
from unittest.mock import MagicMock, patch

import pytest

from voice_call_agent.providers.speech import (
    AudioTurnBuffer,
    MockSpeechToTextProvider,
    MockTextToSpeechProvider,
    OpenAICompatibleSTT,
    OpenAICompatibleTTS,
    calculate_rms_energy,
    create_wav,
    mulaw_to_pcm16,
    pcm16_to_mulaw,
)


def test_mulaw_codec_roundtrip():
    # Generate 16-bit sine wave
    sample_rate = 8000
    samples = [int(12000 * math.sin(2 * math.pi * 440 * (i / sample_rate))) for i in range(160)]
    pcm_original = struct.pack(f"<{len(samples)}h", *samples)

    # Encode to mu-law (8-bit)
    mulaw_encoded = pcm16_to_mulaw(pcm_original)
    assert len(mulaw_encoded) == 160

    # Decode back to PCM16
    pcm_decoded = mulaw_to_pcm16(mulaw_encoded)
    assert len(pcm_decoded) == 320  # 160 samples * 2 bytes

    # Check that quantization error is small (< 5% max error for 12000 amplitude)
    decoded_samples = struct.unpack(f"<{len(samples)}h", pcm_decoded)
    for orig, dec in zip(samples, decoded_samples):
        assert abs(orig - dec) < 600


def test_create_wav_header():
    pcm_data = b"\x00\x00" * 800  # 100ms at 8kHz (800 samples)
    wav = create_wav(pcm_data, sample_rate=8000, channels=1)

    assert len(wav) == 44 + len(pcm_data)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[12:16] == b"fmt "
    assert wav[36:40] == b"data"

    # Verify sample rate field in header
    sample_rate = struct.unpack("<I", wav[24:28])[0]
    assert sample_rate == 8000


def test_calculate_rms_energy():
    silence = b"\x00\x00" * 160
    assert calculate_rms_energy(silence) == 0.0

    loud_samples = [10000] * 160
    loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
    energy = calculate_rms_energy(loud_pcm)
    assert math.isclose(energy, 10000.0, rel_tol=0.01)


def test_vad_audio_turn_buffer():
    # 20ms of silence in mu-law (0xFF is quiet in mu-law)
    silent_pcm = struct.pack("<160h", *([0] * 160))
    silent_chunk = pcm16_to_mulaw(silent_pcm)

    # 20ms of speech (amplitude 6000, well above default 400.0 threshold)
    speech_pcm = struct.pack("<160h", *([6000] * 160))
    speech_chunk = pcm16_to_mulaw(speech_pcm)

    vad = AudioTurnBuffer(
        energy_threshold=400.0,
        min_speech_duration_ms=40,  # 2 frames
        silence_timeout_ms=60,      # 3 frames
        chunk_duration_ms=20,
    )

    # 1. Feed silence - should not trigger speech
    assert vad.add_chunk(silent_chunk) is None
    assert vad.is_speaking is False

    # 2. Feed 2 speech frames - should trigger speaking
    assert vad.add_chunk(speech_chunk) is None
    assert vad.add_chunk(speech_chunk) is None
    assert vad.is_speaking is True

    # 3. Feed 2 silence frames (not reached threshold yet)
    assert vad.add_chunk(silent_chunk) is None
    assert vad.add_chunk(silent_chunk) is None
    assert vad.is_speaking is True

    # 4. 3rd silence frame triggers utterance end!
    result_wav = vad.add_chunk(silent_chunk)
    assert result_wav is not None
    assert result_wav[:4] == b"RIFF"
    assert vad.is_speaking is False


@pytest.mark.anyio
async def test_mock_stt_multilingual():
    stt = MockSpeechToTextProvider()

    # Default transcription
    res1 = await stt.transcribe(b"dummy_wav")
    assert "2BHK" in res1.text
    assert res1.language == "en"

    # Queued multilingual transcriptions
    stt.queue_transcription("మీ ప్రాజెక్ట్ వివరాలు ఏమిటి?", language="te")
    stt.queue_transcription("मुझे अपॉइंटमेंट बुक करना है", language="hi")

    res_te = await stt.transcribe(b"dummy_wav")
    assert res_te.language == "te"
    assert "వివరాలు" in res_te.text

    res_hi = await stt.transcribe(b"dummy_wav")
    assert res_hi.language == "hi"
    assert "अपॉइंटमेंट" in res_hi.text


@pytest.mark.anyio
async def test_mock_tts_synthesis():
    tts = MockTextToSpeechProvider()
    res = await tts.synthesize("Namaste, how can I help you today?")

    assert res.duration_seconds > 0.5
    assert len(res.audio_mulaw_bytes) > 0
    # Length should match duration * 8000 bytes (1 byte per sample)
    expected_bytes = int(res.duration_seconds * 8000)
    assert abs(len(res.audio_mulaw_bytes) - expected_bytes) <= 10


@pytest.mark.anyio
async def test_openai_compatible_stt_mocked():
    stt = OpenAICompatibleSTT(api_key="test_key", base_url="https://mock.ai/v1")

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"text": "Hello world", "language": "en"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await stt.transcribe(b"fake_wav", language="en")
        assert res.text == "Hello world"
        assert res.language == "en"


@pytest.mark.anyio
async def test_openai_compatible_tts_mocked():
    tts = OpenAICompatibleTTS(api_key="test_key", base_url="https://mock.ai/v1")

    # 2400 samples at 24kHz (0.1s)
    fake_pcm_24k = struct.pack("<2400h", *([1000] * 2400))

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_pcm_24k
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = await tts.synthesize("Test speech synthesis")
        assert res.duration_seconds == 0.1
        # Downsampled to 800 samples at 8kHz -> 800 bytes of mu-law
        assert len(res.audio_mulaw_bytes) == 800
