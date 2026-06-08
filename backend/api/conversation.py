# -*- coding: utf-8 -*-
"""Internal AutoGEO assistant conversation API."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.user import get_current_active_user
from backend.database import get_db
from backend.database.models import ConversationMessage, ConversationSession, User
from backend.services.conversation_orchestrator import (
    ConversationMessageRequest,
    ConversationMessageResult,
    get_conversation_orchestrator,
)

router = APIRouter(prefix="/api/conversation", tags=["智能对话"])


@router.post("/message", response_model=ConversationMessageResult)
async def send_message(
    payload: ConversationMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Send a message to the internal AutoGEO assistant.

    The user identity comes from the current backend login token. The caller
    cannot specify system_user_id, project_id, account_id, or any publishing
    authority directly.
    """
    orchestrator = get_conversation_orchestrator()
    return await orchestrator.handle_web_message(payload, current_user, db)


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    session = (
        db.query(ConversationSession)
        .filter(
            ConversationSession.id == session_id,
            ConversationSession.system_user_id == current_user.id,
        )
        .first()
    )
    if not session:
        return {"success": False, "message": "会话不存在或无权访问"}

    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == session.id)
        .order_by(ConversationMessage.created_at.asc(), ConversationMessage.id.asc())
        .all()
    )
    return {
        "success": True,
        "data": {
            "session": {
                "id": session.id,
                "status": session.status,
                "current_intent": session.current_intent,
                "slots": session.slots or {},
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            },
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "metadata": message.message_metadata or {},
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                }
                for message in messages
            ],
        },
    }
