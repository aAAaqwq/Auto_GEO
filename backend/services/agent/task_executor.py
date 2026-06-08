# -*- coding: utf-8 -*-
"""Task executor for the AutoGEO backend Agent."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.database.models import (
    Account,
    AutoPublishRecord,
    AutoPublishTask,
    ConversationMessage,
    ConversationSession,
    GeoArticle,
    Project,
    User,
)
from backend.services.agent.schemas import AgentExecutionResult
from backend.services.agent.tools import get_agent_tools
from backend.services.geo_article_service import GeoArticleService


class AgentTaskExecutor:
    async def execute(
        self,
        db: Session,
        current_user: User,
        intent: str,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        if intent == "generate_article":
            return await self.generate_article(db, current_user, slots)
        if intent == "generate_and_publish":
            return await self.generate_and_prepare_publish(db, current_user, slots)
        if intent == "publish_existing_article":
            return await self.prepare_publish_existing_article(db, current_user, slots)
        if intent == "confirm_task":
            return await self.confirm_task(db, current_user, slots)
        if intent == "cancel_task":
            return self.cancel_task(db, current_user, slots)
        if intent == "query_task_status":
            return self.query_task_status(db, current_user, slots)
        if intent == "general_chat":
            return self.general_chat(slots)
        return AgentExecutionResult(
            success=False,
            status="failed",
            reply=f"当前还不支持执行意图：{intent}",
        )

    def general_chat(self, slots: Dict[str, Any]) -> AgentExecutionResult:
        answer = str(slots.get("answer") or "").strip()
        if answer:
            return AgentExecutionResult(success=True, status="completed", reply=answer)

        question = str(slots.get("question") or "")
        if "模型" in question:
            reply = (
                "我是 AutoGEO 后台智能体。自然语言关键字段识别优先走已配置的 DeepSeek，"
                "并由本地规则做兜底纠偏；项目、账号和权限会由后端查库确认。"
            )
        elif "能做什么" in question or "可以做什么" in question or "能力" in question:
            reply = "我可以根据项目或公司识别发布需求，蒸馏关键词，生成文章，并按指定平台自动发布。"
        else:
            reply = "你好，我是 AutoGEO 后台智能体。你可以告诉我要使用哪个项目或公司，以及要发布到哪个平台。"
        return AgentExecutionResult(success=True, status="completed", reply=reply)

    async def generate_article(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        tools = get_agent_tools()
        project = self._resolve_project_from_slots(db, current_user, slots)
        if not project:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="我还没有确定要使用哪个项目，请先告诉我项目或客户名称。",
            )

        topic = slots.get("topic")
        if not topic:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="我还不知道文章主题，请告诉我要生成什么内容。",
            )

        keyword = await tools.prepare_keyword(
            db,
            project,
            topic,
            company_name=slots.get("company_name") or project.company_name,
        )
        if not keyword:
            return AgentExecutionResult(
                success=False,
                status="failed",
                reply="没有找到或生成可用关键词，暂时无法创建文章。",
            )

        result = await GeoArticleService(db).generate(
            keyword_id=keyword.id,
            company_name=project.company_name or project.name,
            target_platforms=[],
            publish_strategy="draft",
        )
        if not result.get("success"):
            return AgentExecutionResult(
                success=False,
                status="failed",
                reply=f"文章生成任务启动失败：{result.get('message', '未知错误')}",
            )
        article_id = result.get("article_id")
        return AgentExecutionResult(
            success=True,
            status="running",
            article_id=article_id,
            reply=f"已开始为项目「{project.name}」生成「{topic}」文章，文章 ID：{article_id}。生成完成后可继续让我质检或发布。",
            data={"project_id": project.id, "keyword_id": keyword.id, "article_id": article_id},
        )

    def _resolve_project_from_slots(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> Optional[Project]:
        tools = get_agent_tools()
        project_id = slots.get("project_id")
        allowed_ids = [project.id for project in tools.list_user_projects(db, current_user.id)]
        if project_id and int(project_id) in allowed_ids:
            return db.query(Project).filter(Project.id == int(project_id), Project.status == 1).first()

        resolved = tools.resolve_project(
            db,
            current_user.id,
            slots.get("project_hint") or self._project_hint_from_topic(slots.get("topic")),
            slots.get("company_name"),
        )
        return resolved.get("project")

    def _project_hint_from_topic(self, topic: Optional[str]) -> Optional[str]:
        if not topic:
            return None
        value = str(topic).strip(" ，。,.")
        for suffix in ("项目", "公司", "客户"):
            if value.endswith(suffix) and len(value) > len(suffix):
                return value[: -len(suffix)].strip(" ，。,.")
        return None

    async def generate_and_prepare_publish(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        tools = get_agent_tools()
        platforms = slots.get("platforms") or []
        if not platforms:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="我还不知道要发布到哪个平台，请告诉我要发布到知乎、小红书还是其他平台。",
            )

        account_resolution = tools.resolve_accounts(db, current_user.id, platforms)
        if account_resolution["status"] == "missing":
            return AgentExecutionResult(
                success=False,
                status="account_required",
                reply=f"你还没有可用的 {', '.join(platforms)} 发布账号，请先在账号管理里完成授权。",
            )
        if account_resolution["status"] == "ambiguous":
            names = "、".join(
                f"{account.account_name}({account.platform})"
                for account in account_resolution["candidates"][:6]
            )
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply=f"找到多个可用账号，请明确使用哪一个：{names}",
            )

        project = self._resolve_project_from_slots(db, current_user, slots)
        if not project:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="我还没有确定要使用哪个项目，请告诉我要使用的项目以及对应公司或客户名称。",
            )

        topic = slots.get("topic")
        keyword = await tools.prepare_keyword(
            db,
            project,
            topic,
            company_name=slots.get("company_name") or project.company_name,
            prefer_distill=True,
        )
        if not keyword:
            return AgentExecutionResult(
                success=False,
                status="failed",
                reply="关键词蒸馏后没有得到可用关键词，暂时无法生成文章。",
            )

        result = await GeoArticleService(db).generate(
            keyword_id=keyword.id,
            company_name=slots.get("company_name") or project.company_name or project.name,
            target_platforms=platforms,
            publish_strategy="draft",
        )
        if not result.get("success"):
            return AgentExecutionResult(
                success=False,
                status="failed",
                reply=f"文章生成任务启动失败：{result.get('message', '未知错误')}",
            )

        article_id = result.get("article_id")
        article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
        account_ids = [account.id for account in account_resolution["accounts"]]
        if not article:
            return AgentExecutionResult(
                success=True,
                status="running",
                article_id=article_id,
                reply=f"已用关键词「{keyword.keyword}」启动文章生成。生成完成后会自动质检并发布到 {', '.join(platforms)}。",
                data={"project_id": project.id, "keyword_id": keyword.id, "article_id": article_id},
            )

        if article.publish_status == "completed":
            publish_result = await self._quality_check_and_publish(
                db=db,
                current_user=current_user,
                article=article,
                account_ids=account_ids,
                platforms=platforms,
                immediate=slots.get("publish_strategy") == "immediate",
            )
            return publish_result

        conversation_id = slots.get("_conversation_id")
        if conversation_id:
            asyncio.create_task(
                self._wait_for_article_and_prepare_publish(
                    article_id=article.id,
                    system_user_id=current_user.id,
                    account_ids=account_ids,
                    platforms=platforms,
                    conversation_id=conversation_id,
                    immediate=slots.get("publish_strategy") == "immediate",
                )
            )

        return AgentExecutionResult(
            success=True,
            status="running",
            article_id=article.id,
            reply=f"已随机选择关键词「{keyword.keyword}」并启动文章生成，文章 ID：{article.id}。生成完成后会自动发布到 {', '.join(platforms)}。",
            data={"article_id": article.id, "account_ids": account_ids, "keyword_id": keyword.id},
        )

    async def _wait_for_article_and_prepare_publish(
        self,
        article_id: int,
        system_user_id: int,
        account_ids: List[int],
        platforms: List[str],
        conversation_id: str,
        immediate: bool,
    ) -> None:
        for _ in range(60):
            await asyncio.sleep(10)
            db = SessionLocal()
            try:
                article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
                if not article:
                    return
                if article.publish_status == "failed":
                    self._append_assistant_message(
                        db,
                        conversation_id,
                        f"文章 #{article_id} 生成失败：{article.error_msg or '未知错误'}",
                        {"status": "failed", "article_id": article_id},
                    )
                    return
                if article.publish_status != "completed":
                    continue

                user = db.query(User).filter(User.id == system_user_id).first()
                if not user:
                    return
                publish_result = await self._quality_check_and_publish(
                    db=db,
                    current_user=user,
                    article=article,
                    account_ids=account_ids,
                    platforms=platforms,
                    immediate=immediate,
                )
                if not publish_result.task_id:
                    return
                self._update_session_slots(
                    db,
                    conversation_id,
                    {
                        "article_id": article.id,
                        "task_id": publish_result.task_id,
                        "last_status": publish_result.status,
                    },
                    status=publish_result.status,
                )
                self._append_assistant_message(
                    db,
                    conversation_id,
                    publish_result.reply,
                    {"status": publish_result.status, "article_id": article.id, "task_id": publish_result.task_id},
                )
                return
            finally:
                db.close()

    async def _quality_check_and_publish(
        self,
        db: Session,
        current_user: User,
        article: GeoArticle,
        account_ids: List[int],
        platforms: List[str],
        immediate: bool,
    ) -> AgentExecutionResult:
        quality = await GeoArticleService(db).check_quality(article.id)
        db.refresh(article)
        quality_passed = article.quality_status == "passed"
        if not quality_passed and not immediate:
            return AgentExecutionResult(
                success=True,
                status="review_required",
                article_id=article.id,
                reply="文章已生成，但质检未通过或需要人工审核，暂不发布。",
                data={"quality": quality, "article_id": article.id},
            )

        task = self._create_publish_task(
            db=db,
            current_user=current_user,
            article_ids=[article.id],
            account_ids=account_ids,
            name=f"Agent立即发布-{datetime.now().strftime('%m%d%H%M')}" if immediate else f"Agent待确认发布-{datetime.now().strftime('%m%d%H%M')}",
            description="由后台 Agent 创建，生成后立即发布" if immediate else "由后台 Agent 创建，等待用户确认后发布",
            status="pending",
        )

        if immediate:
            from backend.api.auto_publish import execute_auto_publish_task

            asyncio.create_task(execute_auto_publish_task(task.id))
            quality_note = "文章已生成并通过质检" if quality_passed else "文章已生成，质检未通过但按自动发布策略继续发布"
            return AgentExecutionResult(
                success=True,
                status="running",
                article_id=article.id,
                task_id=task.id,
                reply=f"{quality_note}，发布任务 #{task.id} 已启动，将发布到 {', '.join(platforms)}。",
                data={
                    "article_id": article.id,
                    "task_id": task.id,
                    "account_ids": account_ids,
                    "quality": quality,
                    "quality_passed": quality_passed,
                },
            )

        return AgentExecutionResult(
            success=True,
            status="confirm_required",
            article_id=article.id,
            task_id=task.id,
            reply=f"文章已生成并通过质检。我已创建待确认发布任务 #{task.id}，确认后将发布到 {', '.join(platforms)}。",
            data={"article_id": article.id, "task_id": task.id, "account_ids": account_ids},
        )

    def _append_assistant_message(
        self,
        db: Session,
        conversation_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> None:
        db.add(
            ConversationMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=content,
                message_metadata=metadata,
            )
        )
        db.commit()

    def _update_session_slots(
        self,
        db: Session,
        conversation_id: str,
        updates: Dict[str, Any],
        status: str,
    ) -> None:
        session = db.query(ConversationSession).filter(ConversationSession.id == conversation_id).first()
        if not session:
            return
        slots = dict(session.slots or {})
        slots.update(updates)
        session.slots = slots
        session.status = status
        session.updated_at = datetime.utcnow()
        db.commit()

    async def prepare_publish_existing_article(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        article_id = slots.get("article_id")
        if not article_id:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="我还不知道要发布哪篇文章，请告诉我文章 ID，或先让我生成文章。",
            )

        article = db.query(GeoArticle).filter(GeoArticle.id == int(article_id)).first()
        if not article:
            return AgentExecutionResult(success=False, status="failed", reply="没有找到这篇文章。")
        allowed_project_ids = {project.id for project in get_agent_tools().list_user_projects(db, current_user.id)}
        if article.project_id and article.project_id not in allowed_project_ids:
            return AgentExecutionResult(success=False, status="failed", reply="这篇文章不属于你可访问的项目，不能发布。")
        if article.publish_status == "generating" or "正在创作" in (article.content or ""):
            return AgentExecutionResult(
                success=True,
                status="running",
                article_id=article.id,
                reply=f"文章 #{article.id} 还在生成中，完成后再进行质检和发布准备。",
            )
        if not article.content or "正在努力写作" in article.content:
            return AgentExecutionResult(success=False, status="failed", reply="文章内容还不可用，暂时不能发布。")

        tools = get_agent_tools()
        platforms = slots.get("platforms") or article.target_platforms or []
        account_resolution = tools.resolve_accounts(db, current_user.id, platforms)
        if account_resolution["status"] == "missing":
            return AgentExecutionResult(
                success=False,
                status="account_required",
                reply="没有找到可用发布账号，请先在账号管理里完成授权。",
            )
        if account_resolution["status"] == "ambiguous":
            names = "、".join(
                f"{account.account_name}({account.platform})"
                for account in account_resolution["candidates"][:6]
            )
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply=f"找到多个可用账号，请明确使用哪一个：{names}",
            )

        account_ids = [account.id for account in account_resolution["accounts"]]
        immediate = slots.get("publish_strategy") == "immediate"
        return await self._quality_check_and_publish(
            db=db,
            current_user=current_user,
            article=article,
            account_ids=account_ids,
            platforms=platforms,
            immediate=immediate,
        )

    async def confirm_task(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        task_id = slots.get("pending_task_id") or slots.get("task_id")
        if not task_id:
            return AgentExecutionResult(
                success=False,
                status="need_clarification",
                reply="当前没有等待确认的发布任务。",
            )
        task = (
            db.query(AutoPublishTask)
            .filter(
                AutoPublishTask.id == int(task_id),
                AutoPublishTask.triggered_by_user_id == current_user.id,
            )
            .first()
        )
        if not task:
            return AgentExecutionResult(
                success=False,
                status="failed",
                reply="没有找到属于你的待确认发布任务。",
            )

        from backend.api.auto_publish import execute_auto_publish_task

        asyncio.create_task(execute_auto_publish_task(task.id))
        return AgentExecutionResult(
            success=True,
            status="running",
            task_id=task.id,
            reply=f"已确认，发布任务 #{task.id} 已开始执行。",
        )

    def cancel_task(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        task_id = slots.get("pending_task_id") or slots.get("task_id")
        if not task_id:
            return AgentExecutionResult(success=True, status="cancelled", reply="当前没有待取消的任务。")
        task = (
            db.query(AutoPublishTask)
            .filter(AutoPublishTask.id == int(task_id), AutoPublishTask.triggered_by_user_id == current_user.id)
            .first()
        )
        if task and task.status in {"pending", "running"}:
            task.status = "cancelled"
            db.commit()
        return AgentExecutionResult(success=True, status="cancelled", task_id=int(task_id), reply="已取消当前待确认任务。")

    def query_task_status(
        self,
        db: Session,
        current_user: User,
        slots: Dict[str, Any],
    ) -> AgentExecutionResult:
        task = (
            db.query(AutoPublishTask)
            .filter(AutoPublishTask.triggered_by_user_id == current_user.id)
            .order_by(AutoPublishTask.created_at.desc())
            .first()
        )
        if not task:
            return AgentExecutionResult(success=True, status="completed", reply="你当前还没有由 Agent 触发的发布任务。")
        return AgentExecutionResult(
            success=True,
            status=task.status or "running",
            task_id=task.id,
            reply=f"最近任务 #{task.id} 当前状态：{task.status}，进度 {task.completed_count}/{task.total_count}，失败 {task.failed_count}。",
            data={"task_id": task.id, "status": task.status},
        )

    def _create_publish_task(
        self,
        db: Session,
        current_user: User,
        article_ids: List[int],
        account_ids: List[int],
        name: str,
        description: str,
        status: str = "pending",
    ) -> AutoPublishTask:
        articles = db.query(GeoArticle).filter(GeoArticle.id.in_(article_ids)).all()
        allowed_project_ids = {project.id for project in get_agent_tools().list_user_projects(db, current_user.id)}
        accounts = (
            db.query(Account)
            .filter(
                Account.id.in_(account_ids),
                Account.user_id == current_user.id,
                Account.status == 1,
                Account.deleted_at.is_(None),
            )
            .all()
        )
        if len(articles) != len(article_ids):
            raise ValueError("部分文章不存在")
        if any(article.project_id and article.project_id not in allowed_project_ids for article in articles):
            raise ValueError("部分文章不属于当前用户可访问项目")
        if len(accounts) != len(account_ids):
            raise ValueError("部分发布账号不存在或不属于当前用户")

        task = AutoPublishTask(
            name=name,
            description=description,
            article_ids=article_ids,
            account_ids=account_ids,
            exec_type="immediate",
            total_count=len(article_ids) * len(account_ids),
            completed_count=0,
            failed_count=0,
            status=status,
            triggered_by_user_id=current_user.id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        for article_id in article_ids:
            for account_id in account_ids:
                db.add(
                    AutoPublishRecord(
                        task_id=task.id,
                        article_id=article_id,
                        account_id=account_id,
                        status="pending",
                    )
                )
        db.commit()
        return task


_instance: Optional[AgentTaskExecutor] = None


def get_agent_task_executor() -> AgentTaskExecutor:
    global _instance
    if _instance is None:
        _instance = AgentTaskExecutor()
    return _instance
