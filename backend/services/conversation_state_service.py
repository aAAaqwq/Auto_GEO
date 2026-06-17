# -*- coding: utf-8 -*-
"""
Short-term conversation memory for the AutoGEO assistant.

This phase keeps memory in process so the assistant can handle multi-turn
clarification without a database migration. Persistent memory can later move
to a conversation_sessions table with the same slots shape.
"""

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


class ConversationStateService:
    def __init__(self, ttl_minutes: int = 60):
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def get_slots(self, conversation_id: str) -> Dict[str, Any]:
        self._cleanup_expired()
        session = self._sessions.get(conversation_id)
        if not session:
            return {}
        session["updated_at"] = datetime.utcnow()
        return deepcopy(session.get("slots", {}))

    def update_slots(self, conversation_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        self._cleanup_expired()
        session = self._sessions.setdefault(
            conversation_id,
            {
                "slots": {},
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        slots = session["slots"]
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, list) and not value:
                continue
            slots[key] = value
        session["updated_at"] = datetime.utcnow()
        return deepcopy(slots)

    def clear(self, conversation_id: str) -> None:
        self._sessions.pop(conversation_id, None)

    def _cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired = [
            conversation_id
            for conversation_id, session in self._sessions.items()
            if now - session["updated_at"] > self._ttl
        ]
        for conversation_id in expired:
            self._sessions.pop(conversation_id, None)


_instance: Optional[ConversationStateService] = None


def get_conversation_state_service() -> ConversationStateService:
    global _instance
    if _instance is None:
        _instance = ConversationStateService()
    return _instance
