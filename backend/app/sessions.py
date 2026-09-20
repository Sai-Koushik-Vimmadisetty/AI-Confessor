"""Per-connection session state.

Each WebSocket connection gets its own session: an isolated conversation
history (sliding window) guarded by an asyncio lock. The server is fully
async, so many sessions run concurrently on one worker. For multi-worker
deployments, swap this in-memory store for Redis.
"""
import asyncio
import logging
import uuid

log = logging.getLogger(__name__)


class Session:
    def __init__(self, session_id: str, system_prompt: str, max_history: int):
        self.id = session_id
        self._lock = asyncio.Lock()
        self._max_history = max_history
        self._history: list[dict] = [{"role": "system", "content": system_prompt}]

    async def add_message(self, role: str, content: str) -> None:
        async with self._lock:
            self._history.append({"role": role, "content": content})
            # Sliding window: keep system prompt + the most recent turns.
            while len(self._history) > self._max_history + 1:
                del self._history[1]

    async def get_messages(self) -> list[dict]:
        async with self._lock:
            return list(self._history)

    async def reset(self) -> None:
        async with self._lock:
            system = self._history[0]
            self._history = [system]


class SessionManager:
    def __init__(self, system_prompt: str, max_history: int):
        self._system_prompt = system_prompt
        self._max_history = max_history
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create(self) -> Session:
        session = Session(str(uuid.uuid4()), self._system_prompt, self._max_history)
        async with self._lock:
            self._sessions[session.id] = session
        log.info("session created: %s", session.id)
        return session

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)
        log.info("session closed: %s", session_id)

    def count(self) -> int:
        return len(self._sessions)
