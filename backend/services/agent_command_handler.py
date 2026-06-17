# -*- coding: utf-8 -*-
"""
External agent command handler.

This module is the business-facing adapter for OpenClaw and other external
entry points. Phase 0 intentionally parses and validates a command without
starting generation or publishing tasks.
"""

import re
from typing import Any, Dict, Optional
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.models import FeishuUserBinding, User
from backend.services.feishu_intent_parser import FeishuCommand, get_feishu_intent_parser

log = logger.bind(module="AgentCommand")


class AgentCommandRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=50)
    channel: str = Field(..., min_length=1, max_length=50)
    external_user_id: str = Field(..., min_length=1, max_length=200)
    external_chat_id: Optional[str] = Field(None, max_length=200)
    message: str = Field(..., min_length=1, max_length=4000)
    raw_event: Optional[Dict[str, Any]] = None


class AgentCommandResult(BaseModel):
    success: bool
    status: str
    reply: str
    trace_id: str
    task_id: Optional[int] = None
    bind_hint: Optional[str] = None
    action: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    system_user_id: Optional[int] = None


class AgentCommandHandler:
    async def handle(
        self,
        request: AgentCommandRequest,
        db: Session,
    ) -> AgentCommandResult:
        trace_id = f"agent_{uuid4().hex[:16]}"
        log.info(
            "Received agent command: trace_id={}, source={}, channel={}, external_user_id={}",
            trace_id,
            request.source,
            request.channel,
            request.external_user_id,
        )

        binding = self._resolve_binding(request, db)
        if not binding:
            return AgentCommandResult(
                success=False,
                status="binding_required",
                reply="你还没有绑定 AutoGEO 系统账号，请先完成绑定。",
                bind_hint="请发送：绑定 <绑定码>",
                trace_id=trace_id,
            )

        user = db.query(User).filter(User.id == binding.system_user_id).first()
        if not user:
            return AgentCommandResult(
                success=False,
                status="binding_invalid",
                reply="当前外部账号绑定的 AutoGEO 用户不存在，请联系管理员重新绑定。",
                trace_id=trace_id,
            )

        command = await self._parse_command(request)
        log.info(
            "Parsed agent command: trace_id={}, user_id={}, action={}, params={}",
            trace_id,
            binding.system_user_id,
            command.action,
            command.params,
        )

        return AgentCommandResult(
            success=True,
            status="accepted",
            reply=command.reply or "收到，AutoGEO 已解析你的指令。",
            trace_id=trace_id,
            action=command.action,
            params=command.params,
            system_user_id=binding.system_user_id,
        )

    def _resolve_binding(
        self,
        request: AgentCommandRequest,
        db: Session,
    ) -> Optional[FeishuUserBinding]:
        """
        Phase 0 transition strategy:
        OpenClaw's Feishu channel passes Feishu open_id as external_user_id,
        so we reuse feishu_user_bindings and do not allow callers to provide
        system_user_id or account_id.
        """
        if request.channel != "feishu":
            log.info(
                "Unsupported binding channel for phase 0: source={}, channel={}",
                request.source,
                request.channel,
            )
            return None

        return (
            db.query(FeishuUserBinding)
            .filter(
                FeishuUserBinding.open_id == request.external_user_id,
                FeishuUserBinding.status == 1,
            )
            .first()
        )

    async def _parse_command(self, request: AgentCommandRequest) -> FeishuCommand:
        parser = get_feishu_intent_parser()
        context = {
            "source": request.source,
            "channel": request.channel,
            "external_chat_id": request.external_chat_id,
        }
        command = await parser.parse(request.message, context)
        if command.action != "unknown":
            return command

        fallback = self._rule_based_fallback(request.message)
        return fallback or command

    def _rule_based_fallback(self, message: str) -> Optional[FeishuCommand]:
        text = message.strip()
        lowered = text.lower()

        platform_aliases = {
            "知乎": "zhihu",
            "百家号": "baijiahao",
            "搜狐": "sohu",
            "搜狐号": "sohu",
            "头条": "toutiao",
            "今日头条": "toutiao",
            "小红书": "xiaohongshu",
            "抖音": "douyin",
            "公众号": "weixin",
            "微信公众号": "weixin",
            "微信": "weixin",
        }
        platforms = [
            platform_id
            for alias, platform_id in platform_aliases.items()
            if alias in text
        ]
        platforms = list(dict.fromkeys(platforms))

        quantity = 1
        quantity_match = re.search(r"(\d+)\s*[篇个条]", text)
        if quantity_match:
            quantity = int(quantity_match.group(1))

        has_generate = any(
            keyword in text
            for keyword in ("写", "生成", "创作", "撰写", "起草", "帮我写", "帮我生成")
        )
        has_publish = any(
            keyword in text
            for keyword in ("发布", "发到", "发表", "推送", "分发")
        )
        has_status = any(
            keyword in text
            for keyword in ("进度", "状态", "结果", "怎么样", "如何")
        )
        bind_match = re.search(r"绑定\s*([A-Za-z0-9]{4,20})", text)

        if bind_match:
            return FeishuCommand(
                action="bind",
                params={"binding_code": bind_match.group(1)},
                reply="正在验证绑定码。",
            )

        if has_generate and has_publish:
            return FeishuCommand(
                action="generate_and_publish",
                params={
                    "quantity": quantity,
                    "platforms": platforms,
                    "publish_strategy": "immediate",
                },
                reply="收到，正在为你生成文章并准备发布。",
            )

        if has_generate:
            return FeishuCommand(
                action="generate",
                params={
                    "quantity": quantity,
                    "platforms": [],
                    "publish_strategy": "draft",
                },
                reply="收到，正在为你生成文章草稿。",
            )

        if has_publish:
            return FeishuCommand(
                action="publish",
                params={"platforms": platforms},
                reply="收到，正在准备发布文章。",
            )

        if has_status or "status" in lowered:
            return FeishuCommand(
                action="query_status",
                params={},
                reply="正在查询最新任务进度。",
            )

        return None


_instance: Optional[AgentCommandHandler] = None


def get_agent_command_handler() -> AgentCommandHandler:
    global _instance
    if _instance is None:
        _instance = AgentCommandHandler()
    return _instance
