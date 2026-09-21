import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from voice_call_agent.core.config import settings
from voice_call_agent.models.conversation import Message
from voice_call_agent.providers.llm import LanguageModel

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_SEC = 1.0


class ExpLabsLanguageModel(LanguageModel):
    """Experiential Labs gateway language model client."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str = "qwen3.8-27b",
    ):
        self._api_key = api_key
        self._base_url = base_url
        self.default_model = default_model

    @property
    def api_key(self) -> str:
        return self._api_key if self._api_key is not None else settings.explabs_api_key

    @property
    def base_url(self) -> str:
        url = self._base_url if self._base_url is not None else settings.explabs_base_url
        return url.rstrip("/")

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Synchronous chat completion with retry logic for rate limiting."""
        target_model = model or self.default_model
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        data_bytes = json.dumps(payload).encode("utf-8")
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                last_error = err
                if err.code == 429:
                    backoff = INITIAL_BACKOFF_SEC * (2 ** attempt)
                    logger.warning(
                        "LLM rate limited (429), retrying in %.1fs (attempt %d/%d)",
                        backoff, attempt + 1, MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue
                raise

        # All retries exhausted
        raise last_error  # type: ignore[misc]

    async def reply(self, messages: list[Message]) -> str:
        """Async implementation of LanguageModel protocol."""
        formatted_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        result = await asyncio.to_thread(self.chat_completion, formatted_messages)
        return result["choices"][0]["message"]["content"]

    async def generate_response(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Async chat completion returning full message dictionary (content and tool_calls)."""
        result = await asyncio.to_thread(self.chat_completion, messages, tools)
        return result["choices"][0]["message"]
