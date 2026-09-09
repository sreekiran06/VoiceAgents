from typing import Protocol

from voice_call_agent.models.conversation import Message


class LanguageModel(Protocol):
    """Minimal text reply interface; extend for streaming and tool calls."""

    async def reply(self, messages: list[Message]) -> str: ...


from voice_call_agent.providers.llm.client import ExpLabsLanguageModel

__all__ = ["ExpLabsLanguageModel", "LanguageModel"]
