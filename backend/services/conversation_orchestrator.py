# -*- coding: utf-8 -*-
"""
Compatibility wrapper for the backend Agent orchestrator.

The implementation lives in backend.services.agent.*. Existing imports keep
working through this module.
"""

from backend.services.agent.orchestrator import AgentOrchestrator, get_agent_orchestrator
from backend.services.agent.schemas import AgentMessageRequest, AgentMessageResult

ConversationMessageRequest = AgentMessageRequest
ConversationMessageResult = AgentMessageResult
ConversationOrchestrator = AgentOrchestrator


def get_conversation_orchestrator() -> AgentOrchestrator:
    return get_agent_orchestrator()
