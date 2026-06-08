# -*- coding: utf-8 -*-
"""Main orchestrator for the AutoGEO backend Agent."""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.database.models import User
from backend.services.agent.intent_recognizer import get_intent_recognizer
from backend.services.agent.memory import get_agent_memory
from backend.services.agent.schemas import AgentMessageRequest, AgentMessageResult
from backend.services.agent.task_executor import get_agent_task_executor
from backend.services.agent.tools import get_agent_tools


class AgentOrchestrator:
    async def handle_web_message(
        self,
        request: AgentMessageRequest,
        current_user: User,
        db: Session,
    ) -> AgentMessageResult:
        trace_id = f"agent_{uuid4().hex[:16]}"
        memory = get_agent_memory()
        tools = get_agent_tools()
        recognizer = get_intent_recognizer()

        session = memory.get_or_create_session(db, current_user, request.session_id)
        memory.add_message(db, session.id, "user", request.message, {"trace_id": trace_id})

        recent_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in memory.get_recent_messages(db, session.id, limit=12)
        ]
        old_slots = dict(session.slots or {})
        intent_result = await recognizer.recognize(request.message, old_slots, recent_messages)

        merged_slots = self._merge_slots(old_slots, intent_result.intent, intent_result.slots)
        merged_slots = self._resolve_business_slots(db, current_user, merged_slots)
        missing_slots, questions = self._missing_slots_and_questions(db, current_user, merged_slots)
        status = "need_clarification" if missing_slots else "understood"

        if missing_slots:
            merged_slots["waiting_for"] = missing_slots
            reply = self._clarification_reply(intent_result.reply, questions)
            memory.merge_slots(db, session, {**merged_slots, "last_status": status})
            memory.update_session_status(db, session, "waiting_user")
            memory.add_message(
                db,
                session.id,
                "assistant",
                reply,
                {"trace_id": trace_id, "status": status, "intent": merged_slots.get("intent")},
            )
            return self._result(
                success=True,
                status=status,
                reply=reply,
                conversation_id=session.id,
                trace_id=trace_id,
                intent=merged_slots.get("intent") or "unknown",
                slots=merged_slots,
                context=self._build_context(db, current_user, merged_slots),
                questions=questions,
                need_user_input=True,
            )

        executor = get_agent_task_executor()
        try:
            merged_slots["_conversation_id"] = session.id
            execution = await executor.execute(db, current_user, merged_slots.get("intent") or "unknown", merged_slots)
        except Exception as exc:
            execution = None
            status = "failed"
            reply = f"执行任务时发生错误：{exc}"
        else:
            status = execution.status
            reply = execution.reply
            updates: Dict[str, Any] = {"last_status": status, "waiting_for": []}
            if execution.article_id:
                updates["article_id"] = execution.article_id
            if execution.task_id:
                updates["task_id"] = execution.task_id
                if execution.status == "confirm_required":
                    updates["pending_task_id"] = execution.task_id
            merged_slots = memory.merge_slots(db, session, {**merged_slots, **updates})

        memory.update_session_status(db, session, self._session_status_from_response(status))
        memory.add_message(
            db,
            session.id,
            "assistant",
            reply,
            {
                "trace_id": trace_id,
                "status": status,
                "intent": merged_slots.get("intent"),
                "task_id": getattr(execution, "task_id", None) if execution else None,
                "article_id": getattr(execution, "article_id", None) if execution else None,
            },
        )

        return self._result(
            success=status != "failed",
            status=status,
            reply=reply,
            conversation_id=session.id,
            trace_id=trace_id,
            intent=merged_slots.get("intent") or "unknown",
            slots=merged_slots,
            context=self._build_context(db, current_user, merged_slots),
            task_id=getattr(execution, "task_id", None) if execution else None,
            article_id=getattr(execution, "article_id", None) if execution else None,
        )

    def _merge_slots(
        self,
        old_slots: Dict[str, Any],
        intent: str,
        new_slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        slots = dict(old_slots or {})
        if intent and intent != "unknown":
            if intent in {"confirm_task", "cancel_task"}:
                slots["intent"] = intent
            elif not slots.get("intent") or slots.get("last_status") in {"completed", "cancelled", "failed"}:
                slots["intent"] = intent
            else:
                slots["intent"] = intent
        elif intent == "unknown":
            # 新消息无法识别意图时，如果上一个任务已完成/取消/失败，
            # 则覆盖旧意图为 unknown，避免重复执行旧任务；
            # 如果上一个任务还在进行中（waiting_user / confirm_required 等），
            # 保留旧意图让用户继续补充信息。
            prev_status = slots.get("last_status")
            if prev_status in {None, "completed", "cancelled", "failed"}:
                slots["intent"] = "unknown"
            # 否则：上一个任务未完成，保留旧意图等用户补充
        for key, value in (new_slots or {}).items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and not value:
                continue
            slots[key] = value
        slots.setdefault("quantity", 1)
        if not slots.get("publish_strategy"):
            slots["publish_strategy"] = (
                "immediate"
                if slots.get("intent") in {"generate_and_publish", "publish_existing_article"}
                else "review_first"
            )
        return slots

    def _resolve_business_slots(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        tools = get_agent_tools()
        intent = slots.get("intent")

        if intent in {"generate_article", "generate_and_publish"} and not slots.get("project_id"):
            project_hint = slots.get("project_hint") or self._project_hint_from_topic(slots.get("topic"))
            resolved = tools.resolve_project(
                db,
                current_user.id,
                project_hint,
                slots.get("company_name"),
            )
            if resolved["status"] == "resolved":
                project = resolved["project"]
                slots["project_id"] = project.id
                slots["project_name"] = project.name
                if project_hint and not slots.get("project_hint"):
                    slots["project_hint"] = project_hint
                if not slots.get("company_name") and project.company_name:
                    slots["company_name"] = project.company_name
                if intent == "generate_article" and not slots.get("topic") and project.domain_keyword:
                    slots["topic"] = project.domain_keyword
            elif resolved["status"] == "ambiguous":
                slots["project_candidates"] = [tools.project_to_dict(p) for p in resolved["candidates"]]

        if intent in {"generate_and_publish", "publish_existing_article"} and not slots.get("account_ids"):
            account_resolution = tools.resolve_accounts(db, current_user.id, slots.get("platforms") or [])
            if account_resolution["status"] == "resolved":
                slots["account_ids"] = [account.id for account in account_resolution["accounts"]]
                if not slots.get("platforms"):
                    slots["platforms"] = list(
                        dict.fromkeys(account.platform for account in account_resolution["accounts"])
                    )
                slots["account_candidates"] = []
            elif account_resolution["status"] == "ambiguous":
                slots["account_candidates"] = [
                    tools.account_to_dict(account)
                    for account in account_resolution["candidates"]
                ]
        return slots

    def _project_hint_from_topic(self, topic: Optional[str]) -> Optional[str]:
        if not topic:
            return None
        value = str(topic).strip(" ，。,.")
        for suffix in ("项目", "公司", "客户"):
            if value.endswith(suffix) and len(value) > len(suffix):
                return value[: -len(suffix)].strip(" ，。,.")
        return None

    def _missing_slots_and_questions(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> tuple[List[str], List[str]]:
        intent = slots.get("intent")
        missing: List[str] = []
        questions: List[str] = []

        if intent == "unknown" or not intent:
            return ["intent"], ["你想生成文章、发布文章，还是查询任务进度？"]

        if intent in {"confirm_task", "cancel_task", "query_task_status", "general_chat"}:
            return [], []

        if intent in {"generate_article", "generate_and_publish"}:
            if intent == "generate_article" and not slots.get("topic"):
                missing.append("topic")
                questions.append("这篇文章的主题是什么？")
            if not slots.get("project_id"):
                missing.append("project")
                candidates = slots.get("project_candidates") or []
                if candidates:
                    names = "、".join(item["name"] for item in candidates[:5])
                    questions.append(f"你想使用哪个项目？当前匹配到：{names}")
                else:
                    questions.append("请告诉我要使用哪个项目，以及对应的公司或客户名称。")

        if intent in {"generate_and_publish", "publish_existing_article"}:
            if intent == "publish_existing_article" and not slots.get("article_id") and not slots.get("article_ids"):
                missing.append("article")
                questions.append("请告诉我要发布哪篇文章，或先让我生成文章。")
            if not slots.get("platforms"):
                missing.append("platform")
                questions.append("你想发布到哪个平台？例如知乎、小红书、头条。")
            elif not slots.get("account_ids"):
                missing.append("account")
                account_candidates = slots.get("account_candidates") or []
                if account_candidates:
                    names = "、".join(
                        f"{item['account_name']}({item['platform']})"
                        for item in account_candidates[:6]
                    )
                    questions.append(f"你有多个可用发布账号，请明确选择：{names}")
                else:
                    questions.append("当前平台没有可用授权账号，请先在账号管理里完成授权。")

        return list(dict.fromkeys(missing)), questions

    def _clarification_reply(self, base_reply: str, questions: List[str]) -> str:
        if not questions:
            return base_reply or "我还需要更多信息才能继续。"
        return f"{base_reply or '我理解了你的需求，但还缺少一些信息。'}\n" + "\n".join(
            f"- {question}" for question in questions
        )

    def _build_context(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        tools = get_agent_tools()
        projects = tools.list_user_projects(db, current_user.id)
        accounts_result = tools.resolve_accounts(db, current_user.id, [])
        accounts = accounts_result.get("accounts") or accounts_result.get("candidates") or []
        return {
            "user": {"id": current_user.id, "username": current_user.username},
            "project_count": len(projects),
            "projects": [tools.project_to_dict(project) for project in projects[:8]],
            "account_count": len(accounts),
            "platforms": sorted({account.platform for account in accounts if account.platform}),
            "memory": {"type": "database", "slots": slots},
            "parser": get_intent_recognizer().parser_status(),
        }

    def _session_status_from_response(self, status: str) -> str:
        mapping = {
            "need_clarification": "waiting_user",
            "confirm_required": "confirm_required",
            "running": "running",
            "completed": "completed",
            "cancelled": "cancelled",
            "failed": "failed",
        }
        return mapping.get(status, "active")

    def _result(
        self,
        success: bool,
        status: str,
        reply: str,
        conversation_id: str,
        trace_id: str,
        intent: str,
        slots: Dict[str, Any],
        context: Dict[str, Any],
        questions: Optional[List[str]] = None,
        need_user_input: bool = False,
        task_id: Optional[int] = None,
        article_id: Optional[int] = None,
    ) -> AgentMessageResult:
        return AgentMessageResult(
            success=success,
            status=status,
            reply=reply,
            conversation_id=conversation_id,
            trace_id=trace_id,
            intent=intent,
            need_user_input=need_user_input,
            next_questions=questions or [],
            task_id=task_id,
            article_id=article_id,
            params=slots,
            context=context,
        )


_instance: Optional[AgentOrchestrator] = None


def get_agent_orchestrator() -> AgentOrchestrator:
    global _instance
    if _instance is None:
        _instance = AgentOrchestrator()
    return _instance
