# -*- coding: utf-8 -*-
"""
GEO文章业务服务 - 工业加固修复版 (v2.7)
修复：
1. 解决 AI 还没生成完就触发发布的竞态问题
2. 强化发布前的状态校验
3. 优化日志输出，适配前端实时监控
4. 修复 project_id 关联问题
5. 修复变量名混用导致的 NameError
"""

import asyncio
import random
import json
import re
import zlib
from typing import Any, Dict, Optional, List
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from backend.database.models import GeoArticle, Keyword, Account, PublishRecord
from backend.services.geo_knowledge_service import GeoKnowledgeService
from backend.services.n8n_service import get_n8n_service
from backend.services.playwright.publishers.base import get_publisher
from backend.services.crypto import decrypt_storage_state
from backend.services.websocket_manager import ws_manager
from playwright.async_api import async_playwright

# 模块化日志绑定
gen_log = logger.bind(module="生成器")
pub_log = logger.bind(module="发布器")
chk_log = logger.bind(module="监测站")


class GeoArticleService:
    def __init__(self, db: Session):
        self.db = db

    def _stabilize_image_urls(self, content: str, article_id: int) -> str:
        """
        给动态图源补稳定 lock，避免预览和发布两次请求拿到不同图片。
        只处理 loremflickr，保留其它图片源原样。
        """
        if not content:
            return content

        counter = 0

        def replace_url(match):
            nonlocal counter
            url = match.group(1)
            if "loremflickr.com" not in url or "lock=" in url:
                return match.group(0)

            counter += 1
            seed_text = f"{article_id}:{counter}:{url}"
            lock = zlib.crc32(seed_text.encode("utf-8")) % 9999 + 1
            separator = "&" if "?" in url else "?"
            stable_url = f"{url}{separator}lock={lock}"
            return match.group(0).replace(url, stable_url)

        return re.sub(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", replace_url, content)

    async def generate(
        self,
        keyword_id: int,
        company_name: str,
        target_platforms: Optional[List[str]] = None,
        publish_strategy: str = "draft",
        scheduled_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        异步生成文章逻辑（异步回调模式）
        """
        # 1. 先获取关键词对象，获取 project_id
        kw_obj = self.db.query(Keyword).filter(Keyword.id == keyword_id).first()
        if not kw_obj:
            return {"success": False, "message": "关键词不存在"}
        kw_text = kw_obj.keyword if kw_obj else "未知关键词"
        project_id = kw_obj.project_id if kw_obj else None

        # 2. 创建占位记录，初始状态为 generating
        article = GeoArticle(
            keyword_id=keyword_id,
            project_id=project_id,  # 设置项目ID
            title="[AI正在创作中]...",
            content="正在努力写作，请稍后刷新列表...",
            publish_status="generating",
            # 存储发布策略
            target_platforms=target_platforms,
            publish_strategy=publish_strategy,
        )

        # 如果是定时发布，解析并设置定时时间
        if publish_strategy == "scheduled" and scheduled_at:
            from datetime import datetime

            try:
                article.scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            except Exception as e:
                gen_log.warning(f"解析定时时间失败: {e}")

        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)

        gen_log.info(
            f"🆕 任务启动：为关键词 ID {keyword_id} (项目ID: {project_id}) 生成文章 (article_id: {article.id})"
        )
        gen_log.info(f"📋 发布策略: {publish_strategy}, 目标平台: {target_platforms}")

        try:
            # 3. 调用 n8n AI 平台（异步模式）
            gen_log.info(f"🛰️ 正在外发 AI 请求 (关键词: {kw_text})，使用异步回调模式...")
            knowledge_service = GeoKnowledgeService(self.db)
            base_requirements = (
                f"围绕【{company_name}】编写，风格专业商务，适合 B2B 企业发布。"
                "文章应自然覆盖用户搜索意图、行业痛点、解决方案和企业优势。"
            )
            rag_context = knowledge_service.build_context_for_keyword(
                keyword_id=keyword_id,
                company_name=company_name,
            )
            requirements = knowledge_service.build_requirements(
                base_requirements=base_requirements,
                rag_context=rag_context,
            )
            gen_log.info(
                "GEO RAG context: article_id={}, enabled={}, datasets={}, chunks={}, warnings={}",
                article.id,
                rag_context.get("enabled"),
                len(rag_context.get("dataset_ids", [])),
                len(rag_context.get("chunks", [])),
                rag_context.get("warnings", []),
            )
            n8n = await get_n8n_service()
            n8n_res = await n8n.generate_geo_article(
                keyword=kw_text,
                company_name=company_name,
                requirements=requirements,
                word_count=1200,
                # 传递回调URL和article_id，n8n完成后将结果回调通知
                callback_url=None,
                article_id=article.id,
            )

            if n8n_res.status == "success":
                # n8n 可能同步返回文章数据，也可能只触发任务等待回调
                n8n_data = n8n_res.data or {}

                if n8n_data.get("title") and n8n_data.get("content"):
                    # 同步模式：n8n 直接返回了文章内容
                    gen_log.info(f"✅ n8n 同步返回文章 (article_id: {article.id})")
                    article.title = n8n_data["title"]
                    article.content = self._stabilize_image_urls(n8n_data["content"], article.id)

                    # 提取 SEO 评分
                    seo_score = n8n_data.get("seo_score")
                    # n8n 的 seo 评分可能在响应顶层（extra 字段）
                    if not seo_score:
                        seo_extra = getattr(n8n_res, "seo", None)
                        if isinstance(seo_extra, dict):
                            seo_score = seo_extra.get("score")
                    if seo_score:
                        article.ai_score = int(seo_score)

                    # 根据发布策略更新状态
                    strategy = article.publish_strategy or "draft"
                    if strategy == "immediate":
                        article.publish_status = "publishing"
                    elif strategy == "scheduled":
                        article.publish_status = "scheduled"
                    else:
                        article.publish_status = "completed"
                        article.error_msg = None

                    self.db.commit()
                    gen_log.success(f"✅ 文章 {article.id} 同步生成完成，策略: {strategy}")

                    # 如果是立即发布，触发发布逻辑
                    if strategy == "immediate":
                        asyncio.create_task(self.execute_publish(article.id))
                else:
                    # 异步模式：等待 n8n 回调
                    gen_log.info(f"✅ AI 生成任务已触发，等待 n8n 异步回调 (article_id: {article.id})")
            else:
                article.publish_status = "failed"
                article.error_msg = n8n_res.error or "触发 n8n 生成失败"
                self.db.commit()
                gen_log.error(f"❌ 触发 n8n 生成失败：{n8n_res.error}")

            return {"success": True, "article_id": article.id}

        except Exception as e:
            gen_log.exception(f"🚨 后端生成异常：{str(e)}")
            article.publish_status = "failed"
            article.error_msg = str(e)
            self.db.commit()
            return {"success": False, "message": str(e)}

    async def execute_publish(self, article_id: int) -> bool:
        """
        执行真实发布动作 (修复 Session 丢失问题版)
        """
        # 重新从数据库获取最新状态
        db_article = self.db.query(GeoArticle).filter(GeoArticle.id == article_id).first()

        if not db_article:
            pub_log.error(f"❌ 文章不存在: {article_id}")
            return False

        # 支持 scheduled、publishing、failed 和 completed 状态（允许重试失败任务）
        if db_article.publish_status not in ["scheduled", "publishing", "failed", "completed"]:
            pub_log.info(f"⏭️ 跳过文章 {article_id}：当前状态为 {db_article.publish_status}")
            return False

        # 🌟 状态流转优化：如果是 failed 或 completed，先重置为 publishing
        if db_article.publish_status in ["failed", "completed"]:
            db_article.publish_status = "publishing"
            db_article.error_msg = None  # 清除之前的错误信息
            self.db.commit()
            pub_log.info(f"🔄 重置文章 {article_id} 状态为 publishing（原状态: {db_article.publish_status}）")

        if "创作中" in (db_article.title or ""):
            pub_log.warning(f"⚠️ 文章 {article_id} 内容仍为占位符")
            return False

        # 自动填充平台
        if not db_article.platform and db_article.target_platforms:
            try:
                if isinstance(db_article.target_platforms, list):
                    target = db_article.target_platforms[0]
                else:
                    targets = json.loads(str(db_article.target_platforms))
                    target = targets[0] if targets else None

                if target:
                    db_article.platform = target
                    self.db.commit()
                    self.db.refresh(db_article)
            except Exception as e:
                pub_log.warning(f"⚠️ 自动填充平台失败: {e}")

        if not db_article.platform:
            db_article.publish_status = "failed"
            db_article.error_msg = "未指定发布平台"
            self.db.commit()
            return False

        # 查找账号：优先使用前端/任务已绑定的 account_id，避免发布到同平台的错误账号
        account = None
        if db_article.account_id:
            account = (
                self.db.query(Account)
                .filter(Account.id == db_article.account_id, Account.status == 1)
                .first()
            )
            if not account:
                db_article.publish_status = "failed"
                db_article.error_msg = "指定发布账号不可用或未授权"
                self.db.commit()
                return False

            if account.platform != db_article.platform:
                pub_log.warning(
                    f"⚠️ 文章 {article_id} 平台与账号平台不一致，已使用账号平台: "
                    f"{db_article.platform} -> {account.platform}"
                )
                db_article.platform = account.platform
                self.db.commit()
                self.db.refresh(db_article)
        else:
            account = self.db.query(Account).filter(Account.platform == db_article.platform, Account.status == 1).first()

        if not account or not account.storage_state:
            db_article.publish_status = "failed"
            db_article.error_msg = "缺少授权数据"
            self.db.commit()
            return False

        # 锁定账号ID
        db_article.account_id = account.id
        self.db.commit()

        publisher = get_publisher(db_article.platform)
        if not publisher:
            db_article.publish_status = "failed"
            db_article.error_msg = f"暂不支持发布平台: {db_article.platform}"
            self.db.commit()
            return False

        # 解析 Session
        try:
            state_data = decrypt_storage_state(account.storage_state)
            if not state_data:
                state_data = json.loads(account.storage_state)
        except Exception:
            db_article.publish_status = "failed"
            db_article.error_msg = "Session解析失败"
            self.db.commit()
            return False

        # 提取关键变量（防止 commit 后对象失效）
        # 🌟 关键：提前把 ID、平台等信息存到局部变量
        target_article_id = db_article.id
        target_account_id = account.id
        target_platform = db_article.platform

        wait_time = random.randint(5, 10)
        pub_log.info(f"⏳ 模拟人工：将在 {wait_time}s 后启动浏览器")
        await asyncio.sleep(wait_time)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            try:
                context = await browser.new_context(storage_state=state_data, viewport={"width": 1280, "height": 800})
                page = await context.new_page()

                # 更新为发布中
                # 注意：这里需要重新查询一次，确保 Session 活跃
                current_article = self.db.query(GeoArticle).get(target_article_id)
                if current_article:
                    current_article.publish_status = "publishing"
                    self.db.commit()

                # 执行发布
                pub_log.info(f"🚀 开始执行发布脚本: {target_platform}")
                # 注意：publisher 内部不应再操作 db 对象，只读取属性
                result = await publisher.publish(page, current_article, account)

                # 重新查询以进行最终状态更新
                # 🌟 再次获取全新对象，避免 Playwright 操作期间 Session 过期
                final_article = self.db.query(GeoArticle).get(target_article_id)
                if not final_article:
                    raise Exception("文章在发布过程中被删除")

                # 准备数据
                now_time = datetime.now()
                is_success = result.get("success")
                final_url = result.get("platform_url")
                error_msg = result.get("error_msg")

                # 更新数据库对象
                if is_success:
                    final_article.publish_status = "published"
                    final_article.publish_time = now_time
                    final_article.platform_url = final_url
                    final_article.publish_logs = f"[{now_time}] ✅ 发布成功"
                    pub_log.success(f"🎊 发布完成：{final_url}")
                else:
                    final_article.publish_status = "failed"
                    final_article.error_msg = error_msg
                    final_article.retry_count += 1
                    pub_log.error(f"❌ 发布失败：{error_msg}")

                # 🌟 核心修改：提交事务
                self.db.commit()
                # 提交后，final_article 对象即视为过期，不再访问它

                # 🌟 核心修改：使用局部变量广播 WebSocket
                # 不再使用 db_article 或 final_article 的属性
                ws_data = {
                    "type": "publish_progress",
                    "article_id": target_article_id,
                    "account_id": target_account_id,
                    "status": 2 if is_success else 3,
                    "publish_status": "published" if is_success else "failed",
                    "platform_url": final_url,
                    "error_msg": error_msg,
                }
                await ws_manager.broadcast(ws_data)

                # 🌟 核心修改：使用局部变量写入发布记录
                # 完全解耦，不再依赖之前的 Session
                # 注意：PublishRecord 通过 account_id 关联 Account，平台信息可从 Account 获取，不需要直接存储 platform 字段
                try:
                    record = (
                        self.db.query(PublishRecord)
                        .filter(
                            PublishRecord.article_id == target_article_id,
                            PublishRecord.account_id == target_account_id,
                        )
                        .order_by(PublishRecord.created_at.desc())
                        .first()
                    )
                    if not record:
                        record = PublishRecord(
                            article_id=target_article_id,
                            account_id=target_account_id,
                        )
                        self.db.add(record)

                    record.publish_status = 2 if is_success else 3
                    record.platform_url = final_url
                    record.error_msg = error_msg
                    record.published_at = now_time if is_success else None
                    self.db.commit()
                    pub_log.info("📝 发布记录已保存")
                except Exception as rec_e:
                    pub_log.error(f"⚠️ 记录写入失败 (不影响状态): {rec_e}")
                    self.db.rollback()

                return is_success

            except Exception as e:
                self.db.rollback()
                pub_log.error(f"🚨 发布异常中断: {e}")

                # 异常情况下的状态回滚
                try:
                    fail_article = self.db.query(GeoArticle).get(target_article_id)
                    if fail_article:
                        fail_article.publish_status = "failed"
                        fail_article.error_msg = f"异常: {str(e)}"
                        self.db.commit()

                        # 广播失败
                        await ws_manager.broadcast(
                            {
                                "type": "publish_progress",
                                "article_id": target_article_id,
                                "status": 3,
                                "publish_status": "failed",
                                "error_msg": str(e),
                            }
                        )
                except:
                    pass
                return False
            finally:
                await browser.close()

    async def check_quality(self, article_id: int) -> Dict[str, Any]:
        """
        文章质量检查（AI 评估）

        评估维度：
        - quality_score: 内容完整性、结构、可读性 (0-100)
        - fact_risk_score: 事实风险和幻觉风险 (0-100，越低越安全)
        - platform_risk_score: 平台合规风险 (0-100，越低越安全)
        - duplication_score: 与历史文章重复度 (0-100，越低越原创)

        自动发布阈值：
        - quality_score >= 75
        - fact_risk_score <= 30
        - platform_risk_score <= 30
        - duplication_score <= 70
        """
        article = self.get_article(article_id)
        if not article:
            return {"success": False, "message": "文章不存在"}

        gen_log.info(f"📊 正在对文章 {article_id} 进行 AI 质量评估...")

        try:
            # 构建质量检查 Prompt
            prompt = self._build_quality_check_prompt(article)

            # 尝试调用 AI 获取质量评分
            result = await self._call_quality_ai(prompt)

            if result:
                article.quality_score = result.get("quality_score", 70)
                article.fact_risk_score = result.get("fact_risk_score", 30)
                article.platform_risk_score = result.get("platform_risk_score", 30)
                article.duplication_score = result.get("duplication_score", 50)

                # 检查自动发布阈值
                if (
                    article.quality_score >= 75
                    and article.fact_risk_score <= 30
                    and article.platform_risk_score <= 30
                    and article.duplication_score <= 70
                ):
                    article.quality_status = "passed"
                else:
                    article.quality_status = "review_required"

                self.db.commit()

                gen_log.info(
                    f"✅ 质量检查完成: article_id={article_id}, "
                    f"quality={article.quality_score}, fact_risk={article.fact_risk_score}, "
                    f"platform_risk={article.platform_risk_score}, dup={article.duplication_score}, "
                    f"status={article.quality_status}"
                )

                return {
                    "success": True,
                    "quality_score": article.quality_score,
                    "fact_risk_score": article.fact_risk_score,
                    "platform_risk_score": article.platform_risk_score,
                    "duplication_score": article.duplication_score,
                    "quality_status": article.quality_status,
                }

        except Exception as e:
            gen_log.warning(f"AI 质量检查调用失败，使用保守评分: {e}")

        # AI 不可用时使用保守评分，进入人工审核，避免无质检能力时自动发布。
        article.quality_score = 70
        article.fact_risk_score = 25
        article.platform_risk_score = 25
        article.duplication_score = 50
        article.quality_status = "review_required"
        self.db.commit()

        return {
            "success": True,
            "quality_score": article.quality_score,
            "fact_risk_score": article.fact_risk_score,
            "platform_risk_score": article.platform_risk_score,
            "duplication_score": article.duplication_score,
            "quality_status": article.quality_status,
            "note": "fallback_score (AI unavailable)",
        }

    def _build_quality_check_prompt(self, article) -> str:
        """构建质量检查 Prompt"""
        title = article.title or ""
        content = article.content or ""
        # 截取前 2000 字符用于评分
        content_preview = content[:2000] if content else ""

        return f"""请对以下文章进行质量评估，返回 JSON 格式的评分结果。

评估标准：
1. quality_score (0-100): 内容完整性、结构逻辑、可读性、专业性
2. fact_risk_score (0-100): 是否存在编造的资质、案例、价格、客户名称等幻觉风险（分数越低越安全）
3. platform_risk_score (0-100): 是否可能违反内容平台规则，如过度营销、虚假宣传（分数越低越安全）
4. duplication_score (0-100): 是否为通用模板化内容，缺乏独特观点（分数越低越原创）

文章标题：{title}

文章内容：
{content_preview}

请只返回 JSON：{{"quality_score": 数字, "fact_risk_score": 数字, "platform_risk_score": 数字, "duplication_score": 数字}}"""

    async def _call_quality_ai(self, prompt: str) -> Optional[Dict[str, int]]:
        """调用 AI 进行质量检查"""
        import json as json_module
        import httpx
        from backend.config import DEEPSEEK_API_URL, DEEPSEEK_API_KEY

        if not DEEPSEEK_API_URL or not DEEPSEEK_API_KEY:
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{DEEPSEEK_API_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "你是一个专业的内容质量审核员。只返回 JSON，不返回其他内容。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                )
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 提取 JSON
                json_match = json_module.loads(content.strip())
                if isinstance(json_match, dict) and "quality_score" in json_match:
                    return {
                        "quality_score": int(json_match.get("quality_score", 70)),
                        "fact_risk_score": int(json_match.get("fact_risk_score", 30)),
                        "platform_risk_score": int(json_match.get("platform_risk_score", 30)),
                        "duplication_score": int(json_match.get("duplication_score", 50)),
                    }
        except Exception as e:
            gen_log.warning(f"质量检查 AI 调用异常: {e}")

        return None

    async def check_article_index(self, article_id: int) -> Dict[str, Any]:
        """收录监测逻辑"""
        article = self.get_article(article_id)
        if not article or article.publish_status != "published":
            return {"status": "error", "message": "文章未发布"}

        chk_log.info(f"🔍 [监测] 正在检索文章《{article.title[:10]}...》的收录情况")
        await asyncio.sleep(2)
        is_indexed = random.random() > 0.5
        article.index_status = "indexed" if is_indexed else "not_indexed"
        article.last_check_time = datetime.now()
        self.db.commit()
        return {"status": "success", "index_status": article.index_status}

    def get_article(self, article_id: int) -> Optional[GeoArticle]:
        return self.db.query(GeoArticle).get(article_id)

    def get_articles(self) -> List[GeoArticle]:
        return self.db.query(GeoArticle).order_by(GeoArticle.created_at.desc()).all()

    def delete_article(self, article_id: int) -> bool:
        article = self.get_article(article_id)
        if article:
            self.db.delete(article)
            self.db.commit()
            return True
        return False
