"""Live integration tests for Sarvam AI STT + TTS.

Run with:
    pytest tests/test_sarvam.py -v -s

Or run directly (no pytest needed):
    python tests/test_sarvam.py

Requires SARVAM_API_KEY to be set in .env.
Generated audio files are saved to tests/output/ for manual listening.
"""

from __future__ import annotations

import asyncio
import os
import struct
import sys

# Allow running directly without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from voice_call_agent.core.config import settings
from voice_call_agent.providers.speech import SarvamSTT, SarvamTTS
from voice_call_agent.providers.speech.codec import create_wav

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _build_providers() -> tuple[SarvamTTS, SarvamSTT]:
    api_key = settings.sarvam_api_key
    if not api_key:
        raise RuntimeError(
            "SARVAM_API_KEY is not set in .env — "
            "get a key at https://dashboard.sarvam.ai"
        )
    langs = settings.sarvam_language_list
    voice_map = settings.sarvam_voice_map

    tts = SarvamTTS(
        api_key=api_key,
        default_languages=langs,
        voice_map=voice_map,
        pace=settings.sarvam_pace,
    )
    stt = SarvamSTT(
        api_key=api_key,
        default_languages=langs,
    )
    return tts, stt


# ---------------------------------------------------------------------------
# TTS tests
# ---------------------------------------------------------------------------

async def _test_tts_language(tts: SarvamTTS, text: str, language: str, label: str) -> bytes:
    print(f"\n🔊 TTS [{label}] synthesizing: {text!r}")
    result = await tts.synthesize(text, language=language)
    print(f"   ✅ Got {len(result.audio_mulaw_bytes):,} mu-law bytes "
          f"({result.duration_seconds:.2f}s)")

    # Save as WAV so you can play it
    pcm = bytes(result.audio_mulaw_bytes)  # already mu-law; save as-is for reference
    # Re-build a proper 8kHz mono WAV from the mu-law bytes for easy playback
    # Convert mu-law back to PCM16 for WAV wrapping
    from voice_call_agent.providers.speech.codec import mulaw_to_pcm16
    pcm16 = mulaw_to_pcm16(result.audio_mulaw_bytes)
    wav = create_wav(pcm16, sample_rate=8000)
    path = os.path.join(OUTPUT_DIR, f"tts_{label}.wav")
    with open(path, "wb") as f:
        f.write(wav)
    print(f"   💾 Saved → {path}")
    return result.audio_mulaw_bytes


async def _run_tts_english(tts: SarvamTTS) -> None:
    await _test_tts_language(
        tts,
        text="Hello! Welcome to our voice assistant. How can I help you today?",
        language="en-IN",
        label="en-IN",
    )


async def _run_tts_telugu(tts: SarvamTTS) -> None:
    await _test_tts_language(
        tts,
        text="నమస్కారం! మీకు ఎలా సహాయం చేయగలను?",
        language="te-IN",
        label="te-IN",
    )


async def _run_tts_hindi(tts: SarvamTTS) -> None:
    await _test_tts_language(
        tts,
        text="नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
        language="hi-IN",
        label="hi-IN",
    )


# ---------------------------------------------------------------------------
# STT test (round-trip: TTS → WAV → STT)
# ---------------------------------------------------------------------------

async def _run_stt_roundtrip(tts: SarvamTTS, stt: SarvamSTT) -> None:
    """Synthesize a sentence, then transcribe the resulting audio back."""
    text = "Hello, please book an appointment for tomorrow at ten AM."
    language = "en-IN"

    print(f"\n🔄 Round-trip test [{language}]")
    print(f"   Original: {text!r}")

    # Step 1: TTS
    tts_result = await tts.synthesize(text, language=language)

    # Step 2: Convert mu-law → 16-bit PCM → WAV (Sarvam STT expects WAV)
    from voice_call_agent.providers.speech.codec import mulaw_to_pcm16
    pcm16 = mulaw_to_pcm16(tts_result.audio_mulaw_bytes)
    wav_bytes = create_wav(pcm16, sample_rate=8000)

    # Step 3: STT
    stt_result = await stt.transcribe(wav_bytes, language=language)
    print(f"   Transcript: {stt_result.text!r}")

    if stt_result.text.strip():
        print("   ✅ Round-trip successful!")
    else:
        print("   ⚠️  Empty transcript — audio may be too short or noisy at 8kHz")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_all() -> None:
    print("=" * 60)
    print("  Sarvam AI Integration Test")
    print(f"  Languages : {settings.sarvam_language_list}")
    print(f"  Voices    : {settings.sarvam_voice_map}")
    print(f"  Pace      : {settings.sarvam_pace}")
    print("=" * 60)

    tts, stt = _build_providers()

    await _run_tts_english(tts)
    await _run_tts_telugu(tts)
    await _run_tts_hindi(tts)
    await _run_stt_roundtrip(tts, stt)

    print(f"\n✅ All tests done — audio files saved to: {OUTPUT_DIR}/")


# ---------------------------------------------------------------------------
# pytest hooks (optional)
# ---------------------------------------------------------------------------

def test_sarvam_tts_en() -> None:
    asyncio.run(_run_single_tts("en-IN"))


def test_sarvam_tts_te() -> None:
    asyncio.run(_run_single_tts("te-IN"))


def test_sarvam_tts_hi() -> None:
    asyncio.run(_run_single_tts("hi-IN"))


async def _run_single_tts(lang: str) -> None:
    tts, _ = _build_providers()
    samples = {
        "en-IN": "Hello, this is a test.",
        "te-IN": "నమస్కారం, ఇది ఒక పరీక్ష.",
        "hi-IN": "नमस्ते, यह एक परीक्षण है।",
    }
    result = await tts.synthesize(samples[lang], language=lang)
    assert len(result.audio_mulaw_bytes) > 0, "Expected non-empty audio"
    assert result.duration_seconds > 0


if __name__ == "__main__":
    asyncio.run(run_all())
