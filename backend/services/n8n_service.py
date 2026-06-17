# -*- coding: utf-8 -*-
"""
n8n 服务封装 - v2.1 异步回调版
1. 支持环境变量配置 N8N 地址 (Docker/生产环境必备)
2. 注入 User-Agent 防止被 WAF/Cloudflare 拦截
3. 增强响应解析兼容性
4. 支持异步回调模式，n8n生成完成后通过回调通知
"""

import httpx
import json
import os
from typing import Any, Literal, Optional, List, Dict
from loguru import logger
from pydantic import BaseModel, ConfigDict

from backend.config import N8N_CALLBACK_URL


# ==================== 配置 ====================


class N8nConfig:
    # 🌟 优先读取环境变量，适配 Docker/生产环境
    # 格式示例：http://n8n:5678/webhook 或 http://192.168.1.10:5678/webhook
    WEBHOOK_BASE = os.getenv("N8N_WEBHOOK_URL", "https://n8n.opencaio.cn/webhook")

    # 超时配置
    TIMEOUT_SHORT = 45.0
    TIMEOUT_LONG = 300.0  # 长文章生成

    # 重试配置
    MAX_RETRIES = 1

    # 回调URL（异步回调模式下使用）
    CALLBACK_URL = N8N_CALLBACK_URL


# ==================== 请求模型 (保持不变) ====================


class KeywordDistillRequest(BaseModel):
    keywords: Optional[List[str]] = None
    project_id: Optional[int] = None
    core_kw: Optional[str] = None
    target_info: Optional[str] = None
    prefixes: Optional[str] = None
    suffixes: Optional[str] = None


class GenerateQuestionsRequest(BaseModel):
    question: str
    count: int = 10


class GeoArticleRequest(BaseModel):
    keyword: str
    company_name: str = ""
    requirements: str = ""
    word_count: int = 1200
    # 异步回调模式新增字段
    callback_url: Optional[str] = None
    article_id: Optional[int] = None


class IndexCheckAnalysisRequest(BaseModel):
    keyword: str
    doubao_indexed: bool
    qianwen_indexed: bool
    deepseek_indexed: bool
    history: List[Dict] = []


# ==================== 响应模型 ====================


class N8nResponse(BaseModel):
    """n8n 统一响应格式"""

    status: Literal["success", "error", "processing"]
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


# ==================== 服务类 ====================


class N8nService:
    """
    n8n 服务类
    集成日志推送，支持自动化流水线的实时监控
    """

    def __init__(self, config: Optional[N8nConfig] = None):
        self.config = config or N8nConfig()
        self.log = logger.bind(module="AI中台")
        self._client: Optional[httpx.AsyncClient] = None

    @staticmethod
    def _build_geo_article_prompt(keyword: str, company_name: str, requirements: str) -> str:
        """Render the GEO article prompt used by the n8n workflow for debugging."""
        knowledge_requirements = (
            requirements
            or "当前未提供客户知识库资料，请按通用行业知识写作，但不要编造具体资质、客户案例、价格或承诺。"
        )
        return f"""请根据公司【{company_name}】，为关键词”{keyword}”撰写一篇深度、专业的 SEO 优化文章。

### 核心要求：
1. **身份设定**：你是一名拥有 10 年经验的 SEO 营销专家，撰写风格稳重、专业，适合 B2B 企业发布。
2. **公司植入**：文章中需要自然地提及公司【{company_name}】，出现 2-3 次即可，植入位置要合理不突兀（如开篇行业背景介绍、中间案例分析、结尾推荐总结等位置自然带出），严禁生硬堆砌或强行插入公司名。
3. **格式要求**：文章必须使用 **Markdown** 格式进行排版，包含 H1 标题、H2/H3 小标题。
4. **图文并茂（安全加固版）**：
   - 请在文章的第 1、第 2 和第 3 个 H2 小标题下方，分别插入一张相关的配图。
   - 图片语法严格使用：`![描述](https://loremflickr.com/800/450/{{关键词}},business,office/all?lock={{锁定数字}})`
   - **配图关键词约束**：
     *   将 `{{关键词}}` 替换为 1 个具体的英文实物词（如：truck, office, skyscraper, desk, computer）。
     *   将 `{{锁定数字}}` 替换为 1 个 1-9999 的固定数字。同一篇文章内 3 张图使用不同数字，确保预览与发布时图片一致。
     *   **严禁使用**可能引起误解或返回血腥内容的词，如：service, help, blood, surgery, dead。
     *   **强制后缀**：必须保持 `,business,office/all` 结尾，这会确保图片在你的关键词基础上，必须同时带有”商务”和”办公”标签，从而过滤掉非专业画面。
5. **字数要求**：正文内容在 800-1200 字之间。

### 客户知识库参考资料（如有）：
{knowledge_requirements}

### 知识库使用规则：
- 优先使用上述资料中的公司、产品、服务、应用场景、优势等事实信息。
- 资料不足时，可以补充通用行业观点，但不要编造知识库中没有的资质、案例、价格、承诺。
- 不要逐字罗列资料，要自然融入文章。

### 输出格式：
你必须**严格只返回**以下标准的 JSON 格式，不要包含任何多余的解释文字、不要包含 Markdown 的代码块标识符（如 ```json ）：
{{
  "title": "文章标题",
  "content": "这里是完整的 Markdown 正文，图片链接必须按照上述格式插入"
}}"""

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # v2.0: 注入 User-Agent，防止被 Nginx/WAF 拦截
            self._client = httpx.AsyncClient(
                timeout=self.config.TIMEOUT_SHORT,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _call_webhook(
        self, endpoint: str, payload: Dict[str, Any], timeout: Optional[float] = None
    ) -> N8nResponse:
        """底层统一调用逻辑"""
        # 确保 endpoint 格式正确
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        # 移除 WEBHOOK_BASE 可能的尾部斜杠，防止双斜杠
        base = self.config.WEBHOOK_BASE.rstrip("/")
        url = f"{base}{path}"

        timeout_val = timeout or self.config.TIMEOUT_SHORT

        self.log.info(f"🛰️ 正在外发 AI 请求: {url}")

        for attempt in range(self.config.MAX_RETRIES + 1):
            try:
                response = await self.client.post(url, json=payload, timeout=timeout_val)
                raw_text = response.text

                # 1. 检查 HTTP 状态码
                if response.status_code != 200:
                    err_msg = f"HTTP {response.status_code}: {raw_text[:200]}"
                    self.log.error(f"❌ n8n 返回错误: {err_msg}")
                    return N8nResponse(status="error", error=err_msg)

                # 2. 尝试解析 JSON
                try:
                    res_data = response.json()

                    # 如果 n8n 返回的是数组格式（默认行为），取第一个
                    if isinstance(res_data, list):
                        res_data = res_data[0] if len(res_data) > 0 else {}

                    # 兼容性处理：如果返回结果里没有 status 字段，手动包装
                    if isinstance(res_data, dict) and "status" not in res_data:
                        return N8nResponse(status="success", data=res_data)

                    # 按照标准模型解析
                    return N8nResponse(**res_data)

                except json.JSONDecodeError:
                    # v2.0: 增强兼容性 - 如果 n8n 返回纯文本（非 JSON），尝试作为成功数据处理
                    if raw_text and not raw_text.strip().startswith(("{", "[")):
                        self.log.warning("⚠️ n8n 返回了非 JSON 文本，尝试作为纯文本处理")
                        return N8nResponse(status="success", data={"text_content": raw_text})

                    self.log.error("❌ n8n 响应解析失败")
                    self.log.error(f"🔍 原始响应:\n{raw_text[:500]}")

                    if "Workflow was started" in raw_text:
                        return N8nResponse(status="error", error="n8n工作流缺少 'Respond to Webhook' 节点")

                    return N8nResponse(status="error", error=f"JSON解析失败: {raw_text[:100]}")

            except httpx.TimeoutException:
                self.log.warning(
                    f"⏳ n8n Webhook 请求超时 (尝试 {attempt + 1}/{self.config.MAX_RETRIES + 1})，当前设置等待时间为 {timeout_val}s，请检查 AI 模型响应速度"
                )
                if attempt == self.config.MAX_RETRIES:
                    return N8nResponse(
                        status="error",
                        error=f"AI 生成超时 (超时设置: {timeout_val}s)，请检查 n8n 资源占用或 AI 模型响应速度",
                    )

            except Exception as e:
                self.log.error(f"🚨 传输层异常: {str(e)}")
                return N8nResponse(status="error", error=str(e))

        return N8nResponse(status="error", error="未知错误")

    # ==================== 业务方法 (保持不变) ====================

    async def distill_keywords(
        self,
        *,
        core_kw: Optional[str] = None,
        target_info: Optional[str] = None,
        prefixes: Optional[str] = None,
        suffixes: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        project_id: Optional[int] = None,
    ) -> N8nResponse:
        self.log.info("🧹 正在蒸馏提纯关键词...")
        payload = KeywordDistillRequest(
            keywords=keywords,
            project_id=project_id,
            core_kw=core_kw,
            target_info=target_info,
            prefixes=prefixes,
            suffixes=suffixes,
        ).model_dump(exclude_none=True)
        return await self._call_webhook("keyword-distill", payload)

    async def generate_questions(self, question: str, count: int = 10) -> N8nResponse:
        self.log.info("❓ 正在基于原题扩展变体...")
        payload = GenerateQuestionsRequest(question=question, count=count).model_dump()
        return await self._call_webhook("generate-questions", payload)

    async def generate_geo_article(
        self,
        keyword: str,
        company_name: str = "",
        requirements: str = "",
        word_count: int = 1200,
        callback_url: Optional[str] = None,
        article_id: Optional[int] = None,
    ) -> N8nResponse:
        """
        异步生成GEO文章
        n8n将立即返回，生成结果通过callback_url异步回调
        """
        # 使用配置的回调URL，如果未提供则使用默认值
        final_callback_url = callback_url or self.config.CALLBACK_URL

        self.log.info(f"📝 正在撰写GEO文章 (关键词: {keyword}, 公司: {company_name}), 回调URL: {final_callback_url})...")
        payload = GeoArticleRequest(
            keyword=keyword,
            company_name=company_name,
            requirements=requirements,
            word_count=word_count,
            callback_url=final_callback_url,
            article_id=article_id,
        ).model_dump(exclude_none=True)
        # 使用短超时（触发成功即可），生成结果通过回调返回
        debug_prompt = self._build_geo_article_prompt(keyword, company_name, requirements)
        prompt_log = (
            "\n========== GEO ARTICLE N8N PROMPT BEGIN ==========\n"
            f"article_id: {article_id}\n"
            f"keyword: {keyword}\n"
            f"company_name: {company_name}\n"
            f"{debug_prompt}\n"
            "========== GEO ARTICLE N8N PROMPT END =========="
        )
        self.log.info(prompt_log)
        print(prompt_log, flush=True)
        return await self._call_webhook("geo-article-generate", payload, timeout=self.config.TIMEOUT_SHORT)

    async def analyze_index_check(
        self,
        keyword: str,
        doubao_indexed: bool,
        qianwen_indexed: bool,
        deepseek_indexed: bool,
        history: Optional[List[Dict]] = None,
    ) -> N8nResponse:
        self.log.info("📊 正在请求 AI 深度分析收录趋势...")
        payload = IndexCheckAnalysisRequest(
            keyword=keyword,
            doubao_indexed=doubao_indexed,
            qianwen_indexed=qianwen_indexed,
            deepseek_indexed=deepseek_indexed,
            history=history or [],
        ).model_dump()
        return await self._call_webhook("index-check-analysis", payload)


# ==================== 单例模式 ====================

_instance: Optional[N8nService] = None


async def get_n8n_service() -> N8nService:
    global _instance
    if _instance is None:
        _instance = N8nService()
    return _instance
