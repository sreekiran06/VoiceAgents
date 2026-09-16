"""Interactive Voice Chat with the AI Agent.

Allows you to speak or type in Telugu, Hindi, or English,
get an AI agent response, and hear the real Sarvam AI synthesized speech
played directly on your Mac!

Usage:
    python scripts/talk.py
"""

from __future__ import annotations

import os
import sys

# Auto-switch to repository virtualenv if not already active
_repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_venv_python = os.path.join(_repo_dir, ".venv", "bin", "python")
if os.path.exists(_venv_python) and os.path.abspath(sys.executable) != os.path.abspath(_venv_python):
    os.execv(_venv_python, [_venv_python] + sys.argv)

import asyncio
import subprocess
import tempfile

sys.path.insert(0, os.path.join(_repo_dir, "src"))

from voice_call_agent.agent.orchestrator import VoiceAgentOrchestrator
from voice_call_agent.core.config import settings
from voice_call_agent.models.conversation import CallSession
from voice_call_agent.providers.speech import SarvamSTT, SarvamTTS
from voice_call_agent.providers.speech.codec import create_wav, mulaw_to_pcm16


def play_audio(wav_bytes: bytes) -> None:
    """Play WAV audio directly on macOS using afplay."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_bytes)
        tmp_path = f.name

    try:
        subprocess.run(["afplay", tmp_path], check=False)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def main() -> None:
    print("=" * 65)
    print("  🎙️  SK Voice Agent - Interactive Voice Console")
    print(f"  Languages : {settings.sarvam_language_list} (Telugu, Hindi, English)")
    print(f"  Voices    : {settings.sarvam_voice_map}")
    print("=" * 65)

    if not settings.sarvam_api_key:
        print("❌ SARVAM_API_KEY is not set in .env. Please set it first.")
        return

    # Build providers
    tts = SarvamTTS(
        api_key=settings.sarvam_api_key,
        default_languages=settings.sarvam_language_list,
        voice_map=settings.sarvam_voice_map,
        pace=settings.sarvam_pace,
    )
    stt = SarvamSTT(
        api_key=settings.sarvam_api_key,
        default_languages=settings.sarvam_language_list,
    )
    orchestrator = VoiceAgentOrchestrator(tts=tts)

    session = CallSession(
        call_id="cli_interactive_test",
        from_number="+919876543210",
    )

    print("\n🟢 Agent is ready!")
    print("You can type in English, Telugu (e.g. 'నమస్కారం, నాకు 2BHK ఫ్లాట్ కావాలి'), or Hindi.")
    print("Type 'exit' or 'quit' to end.\n")

    # Initial greeting
    greeting_text = "నమస్కారం! SK Voice Agents కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?"
    print(f"🤖 Agent: {greeting_text}")
    print("🔊 [Speaking via Sarvam AI...]")
    greeting_audio = await tts.synthesize(greeting_text, language="te-IN")
    wav_bytes = create_wav(mulaw_to_pcm16(greeting_audio.audio_mulaw_bytes), sample_rate=8000)
    play_audio(wav_bytes)

    while True:
        try:
            user_input = input("\n👤 You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nEnding session.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        print("\n⏳ Agent is thinking...")
        reply_text, mulaw_audio, tools = await orchestrator.handle_turn(
            session=session,
            user_transcript=user_input,
        )

        print(f"🤖 Agent: {reply_text}")
        if tools:
            for t in tools:
                print(f"   ⚡ Action Taken [{t['tool']}]: {t['args']}")

        if mulaw_audio:
            print("🔊 [Speaking...]")
            wav = create_wav(mulaw_to_pcm16(mulaw_audio), sample_rate=8000)
            play_audio(wav)


if __name__ == "__main__":
    asyncio.run(main())
