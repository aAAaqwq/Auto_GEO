# -*- coding: utf-8 -*-
"""Schemas for AutoGEO backend Agent."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(None, max_length=120)


class IntentResult(BaseModel):
    intent: str = "unknown"
    slots: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    reply: str = ""


class AgentPlan(BaseModel):
    intent: str
    steps: List[str] = Field(default_factory=list)
    executable: bool = False
    requires_confirmation: bool = False
    missing_slots: List[str] = Field(default_factory=list)


class AgentExecutionResult(BaseModel):
    success: bool
    status: str
    reply: str
    task_id: Optional[int] = None
    article_id: Optional[int] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class AgentMessageResult(BaseModel):
    success: bool
    status: str
    reply: str
    conversation_id: str
    trace_id: str
    intent: str
    need_user_input: bool = False
    next_questions: List[str] = Field(default_factory=list)
    task_id: Optional[int] = None
    article_id: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
