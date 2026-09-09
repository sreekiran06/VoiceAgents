from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class CallSession:
    call_id: str
    stream_id: str | None = None
    from_number: str | None = None
    to_number: str | None = None
    status: str = "initiated"
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
