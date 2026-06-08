# -*- coding: utf-8 -*-
"""Persistent memory manager for the AutoGEO backend Agent."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.database.models import ConversationMessage, ConversationSession, User


class AgentMemory:
    def get_or_create_session(
        self,
        db: Session,
        current_user: User,
        session_id: Optional[str] = None,
        source: str = "web",
        channel: str = "web",
    ) -> ConversationSession:
        if session_id:
            session = (
                db.query(ConversationSession)
                .filter(
                    ConversationSession.id == session_id,
                    ConversationSession.system_user_id == current_user.id,
                )
                .first()
            )
            if session:
                return session

        session = ConversationSession(
            id=session_id or f"web_{current_user.id}_{uuid4().hex[:12]}",
            source=source,
            channel=channel,
            system_user_id=current_user.id,
            status="active",
            slots={},
            expires_at=datetime.utcnow() + timedelta(days=1),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def add_message(
        self,
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def get_recent_messages(
        self,
        db: Session,
        conversation_id: str,
        limit: int = 12,
    ) -> List[ConversationMessage]:
        messages = (
            db.query(ConversationMessage)
            .filter(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(messages))

    def merge_slots(
        self,
        db: Session,
        session: ConversationSession,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        slots = dict(session.slots or {})
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and not value:
                continue
            slots[key] = value
        session.slots = slots
        session.current_intent = slots.get("intent") or session.current_intent
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
        return dict(session.slots or {})

    def update_session_status(
        self,
        db: Session,
        session: ConversationSession,
        status: str,
    ) -> None:
        session.status = status
        session.updated_at = datetime.utcnow()
        db.commit()


_instance: Optional[AgentMemory] = None


def get_agent_memory() -> AgentMemory:
    global _instance
    if _instance is None:
        _instance = AgentMemory()
    return _instance
