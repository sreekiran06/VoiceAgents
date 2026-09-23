"""Google Gemini LLM client using the Gemini REST API (generativelanguage.googleapis.com).

Uses httpx for high-performance async requests.
"""

import asyncio
import json
import logging
from typing import Any

import httpx

from voice_call_agent.core.config import settings
from voice_call_agent.models.conversation import Message
from voice_call_agent.providers.llm import LanguageModel

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 0.5
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_FALLBACK_MODELS = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-3.6-flash"]


class GeminiLanguageModel(LanguageModel):
    """Google Gemini language model client via REST API.

    Uses gemini-3.5-flash-lite with httpx for high-speed voice turn generation (<1s latency).
    """

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "gemini-3.5-flash-lite",
    ):
        self._api_key = api_key
        self.default_model = default_model

    @property
    def api_key(self) -> str:
        return self._api_key if self._api_key is not None else settings.gemini_api_key

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Convert OpenAI-style messages to Gemini format.

        Returns (system_instruction_text, contents_list).
        """
        system_text: str | None = None
        contents: list[dict[str, Any]] = []

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            if role == "system":
                system_text = content
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        return system_text, contents

    async def generate_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Async chat completion with Gemini REST API."""
        models_to_try = [model] if model else _FALLBACK_MODELS
        system_text, contents = self._convert_messages(messages)

        payload: dict[str, Any] = {"contents": contents}
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }

        payload["generationConfig"] = {
            "temperature": 0.7,
            "topP": 0.9,
            "maxOutputTokens": 80,
        }

        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=3.0) as client:
            for target_model in models_to_try:
                url = f"{_GEMINI_BASE}/models/{target_model}:generateContent?key={self.api_key}"
                for attempt in range(2):
                    try:
                        resp = await client.post(
                            url,
                            json=payload,
                            headers={"Content-Type": "application/json"},
                        )

                        if resp.status_code in (429, 500, 502, 503, 504):
                            backoff = INITIAL_BACKOFF_SEC * (2 ** attempt)
                            logger.warning(
                                "Gemini model %s returned %d, retrying in %.1fs: %s",
                                target_model, resp.status_code, backoff, resp.text[:120],
                            )
                            await asyncio.sleep(backoff)
                            continue

                        if resp.status_code != 200:
                            logger.error("Gemini API error %d: %s", resp.status_code, resp.text[:200])
                            break

                        result = resp.json()
                        candidates = result.get("candidates", [])
                        if not candidates:
                            break

                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)

                        return {
                            "role": "assistant",
                            "content": text.strip(),
                            "tool_calls": [],
                        }

                    except Exception as exc:
                        last_error = exc
                        logger.warning("Gemini %s attempt %d failed (%s): %s", target_model, attempt + 1, type(exc).__name__, exc)
                        await asyncio.sleep(INITIAL_BACKOFF_SEC)

        raise last_error or RuntimeError("Gemini failed across all fallback models")

    async def reply(self, messages: list[Message]) -> str:
        """Async implementation of LanguageModel protocol."""
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        result = await self.generate_response(formatted)
        return result.get("content", "")
