# -*- coding: utf-8 -*-
"""
飞书任务编排器
将解析后的意图指令桥接到现有业务服务（文章生成、发布、查询状态）
并在关键节点通过飞书推送进度通知
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

from loguru import logger
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.database.models import (
    Project,
    Keyword,
    GeoArticle,
    Account,
    AutoPublishTask,
    AutoPublishRecord,
    Client,
    FeishuUserBinding,
    KeywordUsageRecord,
    User,
)
from backend.services.feishu_client import get_feishu_client
from backend.services.feishu_intent_parser import FeishuCommand
from backend.services.geo_article_service import GeoArticleService
from backend.services.n8n_service import get_n8n_service
from backend.config import PLATFORMS

log = logger.bind(module="飞书任务编排")


class FeishuTaskHandler:
    """
    飞书任务编排器

    根据 FeishuCommand.action 将任务分发到对应的处理方法，
    每个处理方法复用现有服务并在关键节点推送飞书通知。
    """

    def __init__(self):
        self._feishu = get_feishu_client()

    async def dispatch(self, command: FeishuCommand, chat_id: str, user_id: str):
        """
        根据指令类型分发任务

        Args:
            command: 解析后的指令
            chat_id: 飞书群聊 ID
            user_id: 飞书用户 open_id
        """
        action = command.action
        params = command.params

        log.info(f"📤 飞书任务分发: action={action}, chat_id={chat_id}, open_id={user_id}")

        # 0. 绑定命令特殊处理：不需要先有绑定才能执行（绑定的目的就是完成绑定）
        if action == "bind":
            await self._handle_bind(params, chat_id, user_id)
            return

        # 1. 解析用户绑定（非绑定命令都必须先解析）
        system_user_id, binding = self._resolve_system_user(user_id)
        if system_user_id is None:
            await self._feishu.send_progress_card(
                chat_id,
                title="未绑定系统账号",
                status="失败",
                detail="你还没有绑定系统账号。请先在管理后台完成飞书绑定后再发起发布任务。\n\n💡 获取绑定码：登录 AutoGEO → 飞书绑定 → 获取绑定码 → 在飞书中发送「绑定 <绑定码>」",
            )
            return

        log.info(f"✅ 用户已绑定: open_id={user_id} -> system_user_id={system_user_id}")

        try:
            if action == "generate_and_publish":
                await self._handle_generate_and_publish(params, chat_id, system_user_id, binding)
            elif action == "generate":
                await self._handle_generate(params, chat_id, system_user_id, binding)
            elif action == "publish":
                await self._handle_publish(params, chat_id, system_user_id)
            elif action == "query_status":
                await self._handle_query_status(params, chat_id, system_user_id)
            else:
                await self._feishu.send_text_message(
                    chat_id,
                    "抱歉，暂时不支持这个操作 🤔\n\n目前支持：\n• 绑定飞书账号: 发送「绑定 <绑定码>」\n• 生成文章\n• 发布文章\n• 查询任务进度",
                )
        except Exception as e:
            log.exception(f"飞书任务执行异常: {e}")
            await self._feishu.send_progress_card(
                chat_id,
                title="❌ 任务执行出错",
                status="失败",
                detail=f"错误信息: {str(e)[:200]}\n\n请联系管理员处理。",
            )

    def _resolve_system_user(self, open_id: str) -> tuple:
        """
        将飞书 open_id 解析为系统用户

        Returns:
            (system_user_id, FeishuUserBinding) 或 (None, None)
        """
        db = SessionLocal()
        try:
            binding = (
                db.query(FeishuUserBinding)
                .filter(
                    FeishuUserBinding.open_id == open_id,
                    FeishuUserBinding.status == 1,
                )
                .first()
            )
            if binding:
                return binding.system_user_id, binding
            return None, None
        except Exception as e:
            log.error(f"查询用户绑定失败: {e}")
            return None, None
        finally:
            db.close()

    # ==================== 生成 + 发布（核心流程） ====================

    async def _handle_generate_and_publish(
        self, params: Dict[str, Any], chat_id: str,
        system_user_id: int,
        binding=None,
    ):
        """
        生成并发布文章的完整流程

        流程：
        1. 查找匹配的项目（按用户作用域）
        2. 获取/准备关键词（含蒸馏管道）
        3. 逐个生成文章
        4. 创建批量发布任务（按用户过滤账号）
        5. 推送完成通知
        """
        company_name = params.get("company_name", "")
        keywords = params.get("keywords", [])
        quantity = params.get("quantity", 1)
        target_platforms = params.get("platforms", [])
        publish_strategy = params.get("publish_strategy", "immediate")

        # 获取平台中文名
        platform_names = [
            PLATFORMS.get(p, {}).get("name", p) for p in target_platforms
        ]
        platform_text = "、".join(platform_names) if platform_names else "自动选择"

        # 1. 通知开始
        await self._feishu.send_progress_card(
            chat_id,
            title=f"📝 收到！正在为【{company_name or '默认'}】处理文章任务",
            status="处理中",
            detail=f"📋 计划生成 **{quantity}** 篇文章\n🎯 目标平台: {platform_text}\n⏳ 预计需要几分钟，请耐心等待...",
        )

        db = SessionLocal()
        try:
            # 2. 查找项目（用户作用域）
            project = self._find_project(db, company_name, system_user_id, binding)
            if not project:
                if company_name:
                    await self._feishu.send_text_message(
                        chat_id,
                        f"⚠️ 未在系统中找到公司【{company_name}】对应的项目，或你无权访问该项目。",
                    )
                else:
                    await self._feishu.send_progress_card(
                        chat_id,
                        title="未找到可用项目",
                        status="失败",
                        detail="你还没有配置默认项目。请在管理后台为你的飞书账号绑定默认项目，或在指令中指定公司名/项目名。",
                    )
                return

            company_name_resolved = company_name or (project.company_name if project else "默认")

            # 3. 准备关键词（含蒸馏管道）
            keyword_objects = await self._resolve_keywords(
                db, project, keywords, quantity,
                system_user_id, company_name_resolved,
            )

            if not keyword_objects:
                await self._feishu.send_progress_card(
                    chat_id,
                    title="❌ 无法准备关键词",
                    status="失败",
                    detail="未找到可用的关键词，请先在管理后台添加项目和关键词。",
                )
                return

            keyword_names = [kw.keyword for kw in keyword_objects]
            await self._feishu.send_text_message(
                chat_id,
                f"🔑 已准备 {len(keyword_names)} 个关键词: {', '.join(keyword_names[:5])}{'...' if len(keyword_names) > 5 else ''}",
            )

            # 4. 逐个生成文章
            service = GeoArticleService(db)
            article_ids = []
            total = len(keyword_objects)

            for i, kw_obj in enumerate(keyword_objects):
                # 通知进度
                await self._feishu.send_text_message(
                    chat_id,
                    f"⏳ 第 {i + 1}/{total} 篇文章正在生成中（关键词: {kw_obj.keyword}）...",
                )

                try:
                    # 飞书链路必须自己完成账号过滤、质检和发布任务创建。
                    # 这里固定按草稿生成，避免 GeoArticleService 的通用 immediate 逻辑抢先用全局账号发布。
                    generation_strategy = "draft" if publish_strategy == "immediate" else publish_strategy
                    result = await service.generate(
                        keyword_id=kw_obj.id,
                        company_name=company_name_resolved,
                        target_platforms=target_platforms if target_platforms else None,
                        publish_strategy=generation_strategy,
                    )

                    if result.get("success"):
                        article_id = result.get("article_id")

                        # 记录关键词使用
                        self._record_keyword_usage(
                            db, project.id if project else None,
                            kw_obj.id, kw_obj.keyword, article_id,
                            system_user_id, "feishu",
                        )

                        article = await self._wait_for_generated_article(db, article_id)
                        if not article:
                            await self._feishu.send_text_message(
                                chat_id,
                                f"⏳ 第 {i + 1} 篇文章已提交生成，但暂未完成。稍后可发送「任务进度」查看状态。",
                            )
                            continue

                        quality = await service.check_quality(article_id)
                        db.refresh(article)
                        if article.quality_status != "passed":
                            await self._feishu.send_progress_card(
                                chat_id,
                                title="需要人工审核",
                                status="失败",
                                detail=(
                                    f"第 {i + 1} 篇文章《{(article.title or '')[:30]}》未达到自动发布阈值，"
                                    f"已保留为草稿。\n"
                                    f"质量分: {quality.get('quality_score', article.quality_score)}，"
                                    f"事实风险: {quality.get('fact_risk_score', article.fact_risk_score)}，"
                                    f"平台风险: {quality.get('platform_risk_score', article.platform_risk_score)}，"
                                    f"重复度: {quality.get('duplication_score', article.duplication_score)}"
                                ),
                            )
                            continue

                        article_ids.append(article_id)

                        title = article.title if article else "生成中"
                        score = article.ai_score if article else None
                        score_text = f"（AI评分: {score}分）" if score else ""

                        await self._feishu.send_text_message(
                            chat_id,
                            f"✅ 第 {i + 1} 篇生成完成{score_text}: 《{title[:30]}{'...' if len(title) > 30 else ''}》",
                        )
                    else:
                        await self._feishu.send_text_message(
                            chat_id,
                            f"❌ 第 {i + 1} 篇生成失败: {result.get('message', '未知错误')}",
                        )
                except Exception as e:
                    log.error(f"文章生成异常 (keyword_id={kw_obj.id}): {e}")
                    await self._feishu.send_text_message(
                        chat_id,
                        f"❌ 第 {i + 1} 篇生成异常: {str(e)[:100]}",
                    )

            # 5. 处理发布
            if not article_ids:
                await self._feishu.send_progress_card(
                    chat_id,
                    title="暂无可自动发布文章",
                    status="失败",
                    detail="文章可能仍在生成中，或未通过自动发布质检。请稍后查询任务状态，或在后台人工审核后发布。",
                )
                return

            # 如果是 immediate 策略且有目标平台，创建自动发布任务
            if publish_strategy == "immediate" and target_platforms:
                await self._feishu.send_text_message(
                    chat_id,
                    f"📊 {len(article_ids)} 篇文章生成完成，开始发布到 {platform_text}...",
                )
                await self._create_and_execute_publish_task(
                    db, article_ids, target_platforms, chat_id, system_user_id,
                )
            elif publish_strategy == "immediate" and not target_platforms:
                # 没有指定平台，文章已设为 generating/completed，通知用户到后台配置
                await self._feishu.send_result_card(
                    chat_id,
                    title="✅ 文章生成完成",
                    success=True,
                    summary=f"共成功生成 **{len(article_ids)}** 篇文章，已保存为草稿。\n\n请到管理后台配置发布平台和账号。",
                )
            else:
                await self._feishu.send_result_card(
                    chat_id,
                    title="✅ 文章生成完成",
                    success=True,
                    summary=f"共成功生成 **{len(article_ids)}** 篇文章，状态为草稿。",
                )

        except Exception as e:
            log.exception(f"生成+发布流程异常: {e}")
            await self._feishu.send_progress_card(
                chat_id,
                title="❌ 任务执行异常",
                status="失败",
                detail=f"错误: {str(e)[:200]}",
            )
        finally:
            db.close()

    # ==================== 仅生成 ====================

    async def _handle_generate(
        self, params: Dict[str, Any], chat_id: str,
        system_user_id: int,
        binding=None,
    ):
        """仅生成文章（不自动发布）"""
        # 与 generate_and_publish 相同，但策略为 draft
        params["publish_strategy"] = "draft"
        await self._handle_generate_and_publish(params, chat_id, system_user_id, binding)

    # ==================== 仅发布 ====================

    async def _handle_publish(
        self, params: Dict[str, Any], chat_id: str,
        system_user_id: int,
    ):
        """
        发布已有文章（按用户作用域过滤）

        查找该用户最近完成的未发布文章并执行发布
        """
        target_platforms = params.get("platforms", [])
        platform_names = [
            PLATFORMS.get(p, {}).get("name", p) for p in target_platforms
        ]
        platform_text = "、".join(platform_names) if platform_names else "所有可用平台"

        await self._feishu.send_progress_card(
            chat_id,
            title="📤 正在准备发布文章",
            status="处理中",
            detail=f"目标平台: {platform_text}",
        )

        db = SessionLocal()
        try:
            # 获取用户可访问的项目 ID 列表
            accessible_project_ids = self._get_user_project_ids(db, system_user_id)

            # 查找该用户最近完成的待发布文章
            query = db.query(GeoArticle).filter(
                GeoArticle.publish_status.in_(["completed", "failed"]),
                GeoArticle.project_id.in_(accessible_project_ids),
            ).order_by(GeoArticle.created_at.desc()).limit(10)

            articles = query.all()

            if not articles:
                await self._feishu.send_text_message(
                    chat_id,
                    "⚠️ 没有找到可发布的文章。请先生成文章。",
                )
                return

            article_ids = [a.id for a in articles]

            if target_platforms:
                await self._create_and_execute_publish_task(
                    db, article_ids, target_platforms, chat_id, system_user_id,
                )
            else:
                # 未指定平台，提示用户（只显示该用户的账号）
                available = []
                for pid, pconf in PLATFORMS.items():
                    account = db.query(Account).filter(
                        Account.platform == pid,
                        Account.status == 1,
                        Account.user_id == system_user_id,
                        Account.deleted_at == None,
                    ).first()
                    if account:
                        available.append(pconf["name"])

                if not available:
                    await self._feishu.send_text_message(
                        chat_id,
                        "⚠️ 你还没有已授权的发布账号。请先在管理后台授权平台账号。",
                    )
                else:
                    await self._feishu.send_text_message(
                        chat_id,
                        f"请指定发布平台。你的可用平台: {', '.join(available[:10])}\n\n"
                        "例如: 帮我把文章发到知乎和搜狐",
                    )

        finally:
            db.close()

    # ==================== 查询状态 ====================

    async def _handle_query_status(
        self, params: Dict[str, Any], chat_id: str,
        system_user_id: int,
    ):
        """查询该用户最近的任务状态（用户作用域内）"""
        db = SessionLocal()
        try:
            # 获取用户可访问的项目 ID
            accessible_project_ids = self._get_user_project_ids(db, system_user_id)

            # 查询该用户最近的文章
            recent_articles = (
                db.query(GeoArticle)
                .filter(GeoArticle.project_id.in_(accessible_project_ids))
                .order_by(GeoArticle.created_at.desc())
                .limit(5)
                .all()
            )

            # 查询该用户最近的自动发布任务
            recent_tasks = (
                db.query(AutoPublishTask)
                .filter(AutoPublishTask.triggered_by_user_id == system_user_id)
                .order_by(AutoPublishTask.created_at.desc())
                .limit(3)
                .all()
            )

            if not recent_articles and not recent_tasks:
                await self._feishu.send_text_message(chat_id, "📭 暂无任务记录。")
                return

            # 构建状态卡片
            status_map = {
                "generating": "🔄 生成中",
                "completed": "✅ 已生成",
                "scheduled": "📅 已排期",
                "publishing": "🚀 发布中",
                "published": "🎉 已发布",
                "failed": "❌ 失败",
                "draft": "📝 草稿",
            }

            lines = ["## 📋 最近文章状态\n"]
            for article in recent_articles:
                status_text = status_map.get(article.publish_status, article.publish_status)
                title = article.title[:25] + ("..." if len(article.title) > 25 else "")
                lines.append(f"- {status_text} 《{title}》")

            if recent_tasks:
                lines.append("\n## 📦 最近发布任务\n")
                task_status_map = {
                    "pending": "⏳ 待执行",
                    "running": "🔄 执行中",
                    "completed": "✅ 已完成",
                    "failed": "❌ 失败",
                    "cancelled": "🚫 已取消",
                }
                for task in recent_tasks:
                    ts = task_status_map.get(task.status, task.status)
                    lines.append(
                        f"- {ts} {task.name} "
                        f"({task.completed_count}/{task.total_count})"
                    )

            await self._feishu.send_card_message(
                chat_id,
                {
                    "header": {
                        "title": {"tag": "plain_text", "content": "📊 任务状态总览"},
                        "template": "blue",
                    },
                    "elements": [
                        {"tag": "markdown", "content": "\n".join(lines)},
                    ],
                },
            )

        finally:
            db.close()

    # ==================== 绑定处理 ====================

    async def _handle_bind(
        self,
        params: Dict[str, Any],
        chat_id: str,
        open_id: str,
    ):
        """
        处理飞书绑定命令

        用户在飞书发送「绑定 ABC123」，
        系统验证绑定码后将 open_id 绑定到对应的 system_user_id。
        """
        binding_code = params.get("binding_code", "").strip().upper()

        if not binding_code:
            await self._feishu.send_text_message(
                chat_id,
                "⚠️ 请提供绑定码。正确的格式是：绑定 <6位绑定码>\n\n"
                "💡 获取绑定码：登录 AutoGEO 管理后台 → 飞书绑定页面 → 生成绑定码",
            )
            return

        log.info(f"🔗 收到绑定请求: open_id={open_id}, code={binding_code}")

        db = SessionLocal()
        try:
            from backend.database.models import FeishuBindingCode
            from datetime import datetime

            # 1. 检查是否已经绑定过
            existing_binding = (
                db.query(FeishuUserBinding)
                .filter(
                    FeishuUserBinding.open_id == open_id,
                    FeishuUserBinding.status == 1,
                )
                .first()
            )
            if existing_binding:
                user = db.query(User).filter(User.id == existing_binding.system_user_id).first()
                await self._feishu.send_text_message(
                    chat_id,
                    f"✅ 你的飞书账号已经绑定到用户「{user.username if user else existing_binding.system_user_id}」。\n\n"
                    "如需更换绑定，请先在管理后台解绑后再重新绑定。",
                )
                return

            # 2. 查找绑定码
            code_record = (
                db.query(FeishuBindingCode)
                .filter(
                    FeishuBindingCode.code == binding_code,
                    FeishuBindingCode.status == 0,
                )
                .first()
            )

            if not code_record:
                await self._feishu.send_text_message(
                    chat_id,
                    f"❌ 绑定码「{binding_code}」无效或已被使用。\n\n"
                    "请检查绑定码是否正确，或在管理后台重新生成绑定码。",
                )
                return

            # 3. 检查是否过期
            if code_record.expires_at < datetime.now():
                code_record.status = -1  # 标记过期
                db.commit()
                await self._feishu.send_text_message(
                    chat_id,
                    f"⏰ 绑定码「{binding_code}」已过期。请在管理后台重新生成绑定码。",
                )
                return

            # 4. 创建绑定
            binding = FeishuUserBinding(
                open_id=open_id,
                system_user_id=code_record.system_user_id,
                status=1,
            )
            db.add(binding)

            # 5. 标记绑定码已使用
            code_record.status = 1
            code_record.used_by_open_id = open_id
            code_record.used_at = datetime.now()

            db.commit()

            # 6. 获取用户名用于提示
            user = db.query(User).filter(User.id == code_record.system_user_id).first()
            username = user.username if user else f"用户ID {code_record.system_user_id}"

            log.success(f"✅ 飞书绑定成功: open_id={open_id} -> user={username} (user_id={code_record.system_user_id})")

            await self._feishu.send_progress_card(
                chat_id,
                title="✅ 绑定成功",
                status="已完成",
                detail=f"你的飞书账号已成功绑定到 AutoGEO 用户「{username}」。\n\n"
                       "现在你可以直接在这里发送指令来生成和发布文章了！\n\n"
                       "试试发送：**帮我写一篇关于智慧物流的文章发到知乎**",
            )

        except Exception as e:
            db.rollback()
            log.exception(f"绑定处理异常: {e}")
            await self._feishu.send_text_message(
                chat_id,
                f"❌ 绑定失败，请稍后重试。\n\n错误信息: {str(e)[:200]}",
            )
        finally:
            db.close()

    # ==================== 内部辅助方法 ====================

    def _get_user_project_ids(self, db: Session, system_user_id: int) -> List[int]:
        """
        获取用户可访问的项目 ID 列表

        通过 project_members 表或 binding 的 default_project 来确定用户可访问的项目。
        暂时也考虑用户拥有账号则对其 client 的项目有访问权。
        """
        project_ids = set()

        # 1. 从 project_members 获取
        from backend.database.models import ProjectMember
        member_projects = (
            db.query(ProjectMember.project_id)
            .filter(
                ProjectMember.user_id == system_user_id,
                ProjectMember.status == 1,
            )
            .all()
        )
        for (pid,) in member_projects:
            project_ids.add(pid)

        # 2. 从 binding 的 default_project 获取
        binding = (
            db.query(FeishuUserBinding)
            .filter(
                FeishuUserBinding.system_user_id == system_user_id,
                FeishuUserBinding.status == 1,
            )
            .first()
        )
        if binding and binding.default_project_id:
            project_ids.add(binding.default_project_id)

        return list(project_ids) if project_ids else []

    async def _wait_for_generated_article(
        self,
        db: Session,
        article_id: int,
        timeout_seconds: int = 180,
        interval_seconds: int = 3,
    ) -> Optional[GeoArticle]:
        """等待 n8n 同步或回调写回文章内容，避免把占位草稿送去质检/发布。"""
        deadline = datetime.now().timestamp() + timeout_seconds
        while datetime.now().timestamp() < deadline:
            db.expire_all()
            article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
            if not article:
                return None

            title = article.title or ""
            content = article.content or ""
            if article.publish_status == "failed":
                return None

            is_placeholder = "创作中" in title or "正在努力写作" in content
            if article.publish_status in ("completed", "draft") and not is_placeholder:
                return article

            await asyncio.sleep(interval_seconds)

        return None

    def _find_project(
        self, db: Session, company_name: str,
        system_user_id: int,
        binding=None,
    ) -> Optional[Project]:
        """
        根据公司名查找匹配的项目（用户作用域内）

        解析优先级：
        1. 用户指定 company_name → 模糊匹配（仅在用户可访问的项目内）
        2. binding.default_project_id → 直接返回该项目
        3. 用户唯一可访问的 active 项目 → 返回
        4. 多个或无项目 → 返回 None
        """
        accessible_project_ids = self._get_user_project_ids(db, system_user_id)
        if not accessible_project_ids:
            return None

        base_query = db.query(Project).filter(
            Project.id.in_(accessible_project_ids),
            Project.status == 1,
        )

        if company_name:
            # 精确匹配
            project = base_query.filter(Project.company_name == company_name).first()
            if project:
                return project

            # 模糊匹配
            project = base_query.filter(Project.company_name.contains(company_name)).first()
            if project:
                return project

            # 通过客户名匹配
            client = (
                db.query(Client)
                .filter(
                    (Client.name.contains(company_name) | Client.company_name.contains(company_name)),
                    Client.status == 1,
                )
                .first()
            )
            if client:
                project = base_query.filter(Project.client_id == client.id).first()
                if project:
                    return project

            return None

        # 没有指定公司名：用默认项目
        if binding and binding.default_project_id:
            project = base_query.filter(Project.id == binding.default_project_id).first()
            if project:
                return project

        # 用户唯一可访问项目
        projects = base_query.all()
        if len(projects) == 1:
            return projects[0]

        # 多个项目或无项目
        return None

    async def _resolve_keywords(
        self,
        db: Session,
        project: Optional[Project],
        user_keywords: List[str],
        quantity: int,
        system_user_id: int,
        company_name: str = "",
    ) -> List[Keyword]:
        """
        准备关键词列表（含蒸馏管道）

        优先级：
        1. 用户显式指定关键词 → 直接使用，记录使用历史
        2. 项目有 domain_keyword → 调用蒸馏服务生成候选池
        3. 项目已有 active 关键词 → 加权随机选择
        4. 无任何关键词 → 返回空列表
        """
        # 1. 用户指定了关键词
        if user_keywords:
            keyword_objects = []
            for kw_text in user_keywords:
                kw = db.query(Keyword).filter(Keyword.keyword == kw_text).first()
                if kw:
                    keyword_objects.append(kw)
                else:
                    project_id = project.id if project else None
                    if project_id:
                        new_kw = Keyword(
                            project_id=project_id,
                            keyword=kw_text,
                            status="active",
                        )
                        db.add(new_kw)
                        db.commit()
                        db.refresh(new_kw)
                        keyword_objects.append(new_kw)
            return keyword_objects[:quantity]

        # 2. 尝试关键词蒸馏（异步）
        if project:
            try:
                distilled = await self._distill_keywords(
                    db, project, company_name, system_user_id,
                )
                if distilled:
                    return distilled[:quantity]
            except Exception as e:
                log.warning(f"关键词蒸馏失败，回退到数据库查询: {e}")

            # 3. 从项目已有关键词中加权随机选择
            active_kws = (
                db.query(Keyword)
                .filter(Keyword.project_id == project.id, Keyword.status == "active")
                .all()
            )
            if active_kws:
                return self._weighted_random_select(db, active_kws, quantity, project.id)

        # 4. 无可用关键词
        return []

    async def _distill_keywords(
        self,
        db: Session,
        project: Project,
        company_name: str,
        system_user_id: int,
    ) -> List[Keyword]:
        """
        调用关键词蒸馏服务生成候选关键词
        """
        core_kw = project.domain_keyword or ""
        if not core_kw:
            return []

        try:
            from backend.services.keyword_service import KeywordService
            svc = KeywordService(db)
            result = await svc.distill(
                core_kw=core_kw,
                target_info=company_name or project.company_name or "",
                company_name=project.company_name or "",
                industry=project.industry or "",
                description=project.description or "",
            )
            if result and result.get("keywords"):
                keyword_objects = []
                for kw_data in result["keywords"]:
                    kw_text = kw_data if isinstance(kw_data, str) else kw_data.get("keyword", "")
                    if not kw_text:
                        continue
                    # 查找或创建关键词
                    kw = db.query(Keyword).filter(
                        Keyword.keyword == kw_text,
                        Keyword.project_id == project.id,
                    ).first()
                    if not kw:
                        kw = Keyword(
                            project_id=project.id,
                            keyword=kw_text,
                            status="active",
                        )
                        db.add(kw)
                        db.commit()
                        db.refresh(kw)
                    keyword_objects.append(kw)
                return keyword_objects
        except Exception as e:
            log.warning(f"蒸馏调用失败: {e}")
        return []

    def _weighted_random_select(
        self,
        db: Session,
        keywords: List[Keyword],
        quantity: int,
        project_id: int,
    ) -> List[Keyword]:
        """
        加权随机选择关键词

        考虑因素：
        - 近期使用次数（越多降权越多）
        - 随机因子（避免同质化）
        """
        import random
        from datetime import datetime, timedelta

        if not keywords:
            return []

        # 查询近 30 天使用记录
        thirty_days_ago = datetime.now() - timedelta(days=30)
        usage_counts = {}
        records = (
            db.query(KeywordUsageRecord)
            .filter(
                KeywordUsageRecord.project_id == project_id,
                KeywordUsageRecord.used_at >= thirty_days_ago,
            )
            .all()
        )
        for r in records:
            key = r.keyword_id or r.keyword_text
            usage_counts[key] = usage_counts.get(key, 0) + 1

        # 计算权重
        scored = []
        for kw in keywords:
            usage = usage_counts.get(kw.id, 0) + usage_counts.get(kw.keyword, 0)
            # 权重 = 基础分 * 新鲜度权重 * 随机因子
            freshness = 1.0 / (1.0 + usage)  # 使用越多权重越低
            random_factor = random.uniform(0.8, 1.2)
            score = freshness * random_factor
            scored.append((score, kw))

        # 按权重排序并选择
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [kw for (score, kw) in scored[:quantity]]

        # 如果随机因子导致选择过少，补充
        if len(selected) < min(quantity, len(scored)):
            remaining = [kw for kw in keywords if kw not in selected]
            for kw in remaining[: quantity - len(selected)]:
                selected.append(kw)

        return selected

    def _record_keyword_usage(
        self,
        db: Session,
        project_id: int,
        keyword_id: int,
        keyword_text: str,
        article_id: int,
        used_by_user_id: int,
        source: str = "feishu",
    ):
        """记录关键词使用历史"""
        try:
            record = KeywordUsageRecord(
                project_id=project_id,
                keyword_id=keyword_id,
                keyword_text=keyword_text,
                article_id=article_id,
                source=source,
                used_by_user_id=used_by_user_id,
            )
            db.add(record)
            db.commit()
        except Exception as e:
            db.rollback()
            log.warning(f"记录关键词使用失败: {e}")

    async def _create_and_execute_publish_task(
        self,
        db: Session,
        article_ids: List[int],
        target_platforms: List[str],
        chat_id: str,
        system_user_id: int,
    ):
        """
        创建并执行自动发布任务（按用户作用域过滤账号）

        复用 AutoPublishTask 和 AutoPublishRecord 的创建逻辑
        """
        # 查找目标平台下该用户已授权的账号
        account_ids = []
        for platform in target_platforms:
            accounts = (
                db.query(Account)
                .filter(
                    Account.platform == platform,
                    Account.status == 1,
                    Account.user_id == system_user_id,
                    Account.deleted_at == None,
                )
                .all()
            )
            for acc in accounts:
                if acc.id not in account_ids:
                    account_ids.append(acc.id)

        if not account_ids:
            platform_names = [
                PLATFORMS.get(p, {}).get("name", p) for p in target_platforms
            ]
            await self._feishu.send_progress_card(
                chat_id,
                title="⚠️ 未找到已授权账号",
                status="失败",
                detail=f"你在 {', '.join(platform_names)} 上没有已授权的账号。请先在管理后台授权对应平台的账号。",
            )
            return

        # 创建发布任务
        total_count = len(article_ids) * len(account_ids)
        task = AutoPublishTask(
            name=f"飞书任务-{datetime.now().strftime('%m%d%H%M')}",
            description="由飞书机器人触发",
            article_ids=article_ids,
            account_ids=account_ids,
            exec_type="immediate",
            total_count=total_count,
            completed_count=0,
            failed_count=0,
            status="pending",
            triggered_by_user_id=system_user_id,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 创建子任务记录
        for article_id in article_ids:
            for account_id in account_ids:
                record = AutoPublishRecord(
                    task_id=task.id,
                    article_id=article_id,
                    account_id=account_id,
                    status="pending",
                )
                db.add(record)
        db.commit()

        # 异步执行发布任务（不再传递 db session，让后台任务自己管理）
        from backend.api.auto_publish import execute_auto_publish_task
        asyncio.create_task(execute_auto_publish_task(task.id))

        await self._feishu.send_text_message(
            chat_id,
            f"🚀 发布任务已启动！\n📝 文章数: {len(article_ids)}\n👤 账号数: {len(account_ids)}\n📊 总发布数: {total_count}",
        )


# ==================== 单例 ====================

_instance: Optional[FeishuTaskHandler] = None


def get_feishu_task_handler() -> FeishuTaskHandler:
    global _instance
    if _instance is None:
        _instance = FeishuTaskHandler()
    return _instance
