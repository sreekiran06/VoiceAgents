from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from voice_call_agent.core.context import BusinessContext


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class CallSession:
    call_id: str
    business_id: str | None = None
    stream_id: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    status: str = "initiated"
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Loaded once at call start, used throughout the call
    business_context: "BusinessContext | None" = field(default=None, repr=False)

