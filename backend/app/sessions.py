"""In-memory sessions holding each user's per-institution access tokens.

Tokens never leave the backend: the frontend server only holds an opaque
session id. Memory storage is a deliberate hackathon trade-off: sessions are
lost on restart and are not shared across processes. Replace with
PostgreSQL/Redis for anything beyond a single local process.
"""
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Connection:
    access_token: str
    expires_at: float
    customer: dict[str, Any]


@dataclass
class Session:
    id: str
    last_seen: float
    user_id: str | None = None
    auth_session_id: str | None = None
    connections: dict[str, Connection] = field(default_factory=dict)
    revoked: set[str] = field(default_factory=set)

    def active(self, institution_id: str) -> Connection | None:
        connection = self.connections.get(institution_id)
        if connection and connection.expires_at <= time.time():
            del self.connections[institution_id]
            return None
        return connection


class SessionStore:
    def __init__(self, ttl_seconds: int, max_sessions: int):
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._sessions: dict[str, Session] = {}

    def _prune(self) -> None:
        cutoff = time.time() - self._ttl
        for session_id in [sid for sid, s in self._sessions.items() if s.last_seen < cutoff]:
            del self._sessions[session_id]

    def create(self, user_id: str | None = None, auth_session_id: str | None = None) -> Session:
        self._prune()
        if len(self._sessions) >= self._max:
            oldest = min(self._sessions.values(), key=lambda s: s.last_seen)
            del self._sessions[oldest.id]
        session = Session(id=secrets.token_urlsafe(32), last_seen=time.time(), user_id=user_id, auth_session_id=auth_session_id)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None or session.last_seen < time.time() - self._ttl:
            self._sessions.pop(session_id, None)
            return None
        session.last_seen = time.time()
        return session
