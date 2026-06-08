# -*- coding: utf-8 -*-
"""External integration API endpoints."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from loguru import logger

from backend.config import AUTOGEO_AGENT_TOKEN
from backend.database import get_db
from backend.services.agent_command_handler import (
    AgentCommandRequest,
    AgentCommandResult,
    get_agent_command_handler,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])
log = logger.bind(module="Integrations")


@router.post("/agent-command", response_model=AgentCommandResult)
async def agent_command(
    payload: AgentCommandRequest,
    x_autogeo_agent_token: str = Header(default="", alias="X-AutoGEO-Agent-Token"),
    db=Depends(get_db),
):
    """
    Unified command entry point for OpenClaw and other external agents.

    Phase 0 validates the caller, resolves the external identity through the
    existing Feishu binding table, parses intent, and returns the parsed result
    without creating publish tasks.
    """
    if not AUTOGEO_AGENT_TOKEN:
        log.error("AUTOGEO_AGENT_TOKEN is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent Command API is not configured",
        )

    if not hmac.compare_digest(x_autogeo_agent_token, AUTOGEO_AGENT_TOKEN):
        log.warning(
            "Rejected agent command with invalid token: source={}, channel={}",
            payload.source,
            payload.channel,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        )

    handler = get_agent_command_handler()
    return await handler.handle(payload, db)
