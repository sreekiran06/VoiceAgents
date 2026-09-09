import asyncio
from typing import Any

from voice_call_agent.models.conversation import CallSession


class CallSessionManager:
    """In-memory call session store with async lock protection."""

    def __init__(self) -> None:
        self._sessions_by_call_id: dict[str, CallSession] = {}
        self._call_ids_by_stream_id: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        call_id: str,
        from_number: str | None = None,
        to_number: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CallSession:
        async with self._lock:
            if call_id not in self._sessions_by_call_id:
                self._sessions_by_call_id[call_id] = CallSession(
                    call_id=call_id,
                    from_number=from_number,
                    to_number=to_number,
                    status="initiated",
                    metadata=metadata or {},
                )
            session = self._sessions_by_call_id[call_id]
            if from_number and not session.from_number:
                session.from_number = from_number
            if to_number and not session.to_number:
                session.to_number = to_number
            if metadata:
                session.metadata.update(metadata)
            return session

    async def get_by_call_id(self, call_id: str) -> CallSession | None:
        async with self._lock:
            return self._sessions_by_call_id.get(call_id)

    async def get_by_stream_id(self, stream_id: str) -> CallSession | None:
        async with self._lock:
            call_id = self._call_ids_by_stream_id.get(stream_id)
            if not call_id:
                return None
            return self._sessions_by_call_id.get(call_id)

    async def link_stream(self, stream_id: str, call_id: str) -> CallSession | None:
        async with self._lock:
            session = self._sessions_by_call_id.get(call_id)
            if session:
                session.stream_id = stream_id
                session.status = "in-progress"
                self._call_ids_by_stream_id[stream_id] = call_id
            return session

    async def update_status(self, call_id: str, status: str) -> CallSession | None:
        async with self._lock:
            session = self._sessions_by_call_id.get(call_id)
            if session:
                session.status = status
            return session

    async def remove_session(self, call_id: str) -> CallSession | None:
        async with self._lock:
            session = self._sessions_by_call_id.pop(call_id, None)
            if session and session.stream_id:
                self._call_ids_by_stream_id.pop(session.stream_id, None)
            return session

    async def remove_by_stream_id(self, stream_id: str) -> CallSession | None:
        async with self._lock:
            call_id = self._call_ids_by_stream_id.pop(stream_id, None)
            if not call_id:
                return None
            return self._sessions_by_call_id.pop(call_id, None)

    async def active_session_count(self) -> int:
        async with self._lock:
            return len(self._sessions_by_call_id)


# Global session manager instance
session_manager = CallSessionManager()
