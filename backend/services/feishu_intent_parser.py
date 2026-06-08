# -*- coding: utf-8 -*-
"""
飞书消息意图解析器
利用 AI（DeepSeek/GLM）将自然语言解析为结构化指令
"""

import json
from typing import Optional, Dict, Any, List

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from backend.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_API_URL,
    GLM_API_KEY,
    GLM_API_URL,
    GLM_MODEL,
    PLATFORMS,
)

log = logger.bind(module="意图解析")


# ==================== 指令模型 ====================


class FeishuCommand(BaseModel):
    """解析后的结构化指令"""

    action: str = Field(
        "unknown",
        description="动作类型: generate_and_publish | generate | publish | query_status | bind | unknown",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="指令参数",
    )
    reply: str = Field(
        "抱歉，我没理解你的意思。",
        description="立即回复用户的文字",
    )


# ==================== 平台名称映射 ====================

# 构建中文名 → 平台ID的反向映射
_PLATFORM_ALIAS: Dict[str, str] = {}
for _pid, _pconf in PLATFORMS.items():
    _PLATFORM_ALIAS[_pconf["name"]] = _pid
    # 添加常见别名
    if _pid == "zhihu":
        _PLATFORM_ALIAS["知乎"] = "zhihu"
    elif _pid == "baijiahao":
        _PLATFORM_ALIAS["百家号"] = "baijiahao"
    elif _pid == "sohu":
        _PLATFORM_ALIAS["搜狐"] = "sohu"
        _PLATFORM_ALIAS["搜狐号"] = "sohu"
    elif _pid == "toutiao":
        _PLATFORM_ALIAS["头条"] = "toutiao"
        _PLATFORM_ALIAS["头条号"] = "toutiao"
    elif _pid == "xiaohongshu":
        _PLATFORM_ALIAS["小红书"] = "xiaohongshu"
    elif _pid == "douyin":
        _PLATFORM_ALIAS["抖音"] = "douyin"
    elif _pid == "weixin":
        _PLATFORM_ALIAS["微信"] = "weixin"
        _PLATFORM_ALIAS["公众号"] = "weixin"
        _PLATFORM_ALIAS["微信公众号"] = "weixin"
    elif _pid == "weibo":
        _PLATFORM_ALIAS["微博"] = "weibo"
        _PLATFORM_ALIAS["新浪微博"] = "weibo"
    elif _pid == "bilibili":
        _PLATFORM_ALIAS["B站"] = "bilibili"
        _PLATFORM_ALIAS["哔哩哔哩"] = "bilibili"


# ==================== 意图解析器 ====================


class FeishuIntentParser:
    """
    AI 意图解析器

    将用户的自然语言消息解析为结构化指令。
    优先使用 GLM，回退到 DeepSeek。
    """

    # 解析用的 System Prompt
    SYSTEM_PROMPT = """你是一个 GEO 自动化平台的指令解析器。你的任务是将用户的自然语言消息解析为结构化的 JSON 指令。

## 可用的动作类型（action）：
- `bind`: 绑定飞书账号（用户发送"绑定"后面跟着6位字母数字混合的绑定码，如"绑定 ABC123"，提取绑定码放到 params.binding_code 中）
- `generate_and_publish`: 生成文章并发布（用户同时提到写/生成文章和发布/发到某平台）
- `generate`: 仅生成文章（用户只提到写/生成/创作文章，没提到发布）
- `publish`: 发布已有文章（用户提到发布/推送/发表，但没提到生成新文章）
- `query_status`: 查询任务状态（用户问进度/状态/结果/怎么样了）
- `unknown`: 无法理解用户意图

## 可用的发布平台（platforms 字段使用英文 ID）：
- zhihu (知乎)
- baijiahao (百家号)
- sohu (搜狐号/搜狐)
- toutiao (头条号/今日头条)
- xiaohongshu (小红书)
- douyin (抖音)
- weixin (微信公众号/公众号)
- weibo (微博/新浪微博)
- bilibili (B站/哔哩哔哩)
- 其他平台也可以使用，但需要用户明确提到

## 输出格式（严格 JSON，不要包含其他文字）：
{
  "action": "动作类型",
  "params": {
    "company_name": "公司名（用户提到的公司名，可选）",
    "keywords": ["关键词1", "关键词2"],
    "quantity": 3,
    "platforms": ["平台ID列表"],
    "publish_strategy": "immediate 或 draft",
    "scheduled_at": null
  },
  "reply": "用友好的语气告诉用户你理解了他的意思，并简要说明即将做什么（1-2句话）"
}

## 解析规则：
1. 如果用户没有指定数量，默认 quantity = 1
2. 如果用户没有指定平台但有发布意图，platforms 留空数组 []
3. 如果用户没有提到公司名，company_name 留空字符串 ""
4. 如果用户没有提供关键词，keywords 留空数组 []（后续会从项目中获取）
5. publish_strategy 默认 "immediate"（立即发布），除非用户说"草稿"或"先不发布"
6. reply 应该简短友好，用中文回复
7. 如果无法理解用户意图，action 设为 "unknown"，reply 中提示用户正确的使用方式

## 示例：
用户: "帮我写3篇关于极速物流的文章发到知乎和搜狐"
输出: {"action":"generate_and_publish","params":{"company_name":"极速物流","keywords":[],"quantity":3,"platforms":["zhihu","sohu"],"publish_strategy":"immediate","scheduled_at":null},"reply":"好的！正在为极速物流生成3篇文章，完成后会发布到知乎和搜狐，请稍等~"}

用户: "帮我生成5篇文章"
输出: {"action":"generate","params":{"company_name":"","keywords":[],"quantity":5,"platforms":[],"publish_strategy":"draft","scheduled_at":null},"reply":"收到！正在生成5篇文章草稿，生成完成后会通知你~"}

用户: "任务进度怎么样了"
输出: {"action":"query_status","params":{},"reply":"正在查询最新任务进度，请稍等~"}
"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def parse(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> FeishuCommand:
        """
        解析用户消息为结构化指令

        Args:
            user_message: 用户发送的原始消息文本
            context: 附加上下文（如已有的客户/项目列表）

        Returns:
            FeishuCommand 解析后的指令
        """
        # 构建上下文提示
        context_hint = ""
        if context:
            clients = context.get("clients", [])
            if clients:
                client_names = [c["name"] for c in clients[:10]]
                context_hint += f"\n\n## 当前系统中已有的客户/公司：\n{', '.join(client_names)}"

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT + context_hint},
            {"role": "user", "content": user_message},
        ]

        # 尝试用 AI 解析
        result_text = await self._call_ai(messages)

        if result_text:
            command = self._parse_ai_response(result_text)
            if command and command.action != "unknown":
                return command

        # AI 解析失败，尝试规则兜底
        fallback = self._rule_based_fallback(user_message)
        if fallback:
            return fallback

        return FeishuCommand(
            action="unknown",
            reply="抱歉，我没理解你的意思 🤔\n\n试试这样说：\n• 帮我写3篇关于XX公司的文章发到知乎\n• 帮我生成5篇文章\n• 任务进度怎么样了",
        )

    async def _call_ai(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 AI 接口，优先 GLM，回退 DeepSeek"""
        # 优先使用 GLM
        if GLM_API_KEY:
            result = await self._call_glm(messages)
            if result:
                return result

        # 回退到 DeepSeek
        if DEEPSEEK_API_KEY:
            result = await self._call_deepseek(messages)
            if result:
                return result

        log.warning("未配置任何 AI API Key，无法进行意图解析")
        return None

    async def _call_glm(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """调用智谱 GLM API"""
        url = f"{GLM_API_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {GLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GLM_MODEL,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 500,
        }

        try:
            resp = await self.client.post(url, headers=headers, json=payload)
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            log.debug(f"GLM 解析结果: {content[:200]}")
            return content
        except Exception as e:
            log.warning(f"GLM API 调用失败: {e}")
            return None

    async def _call_deepseek(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """调用 DeepSeek API"""
        url = f"{DEEPSEEK_API_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 500,
        }

        try:
            resp = await self.client.post(url, headers=headers, json=payload)
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            log.debug(f"DeepSeek 解析结果: {content[:200]}")
            return content
        except Exception as e:
            log.warning(f"DeepSeek API 调用失败: {e}")
            return None

    def _parse_ai_response(self, text: str) -> Optional[FeishuCommand]:
        """解析 AI 返回的 JSON 文本"""
        # 清理可能的 markdown 代码块标记
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            data = json.loads(clean)
            return FeishuCommand(
                action=data.get("action", "unknown"),
                params=data.get("params", {}),
                reply=data.get("reply", "收到，正在处理..."),
            )
        except json.JSONDecodeError:
            log.warning(f"AI 返回非 JSON 格式: {text[:200]}")
            return None

    def _rule_based_fallback(self, message: str) -> Optional[FeishuCommand]:
        """
        基于规则的兜底解析（当 AI 不可用时的简易匹配）
        """
        msg = message.strip().lower()

        # 检测平台关键词
        platforms = []
        for alias, pid in _PLATFORM_ALIAS.items():
            if alias in message:
                if pid not in platforms:
                    platforms.append(pid)

        # 检测数量
        quantity = 1
        import re
        num_match = re.search(r"(\d+)\s*[篇个条]", message)
        if num_match:
            quantity = int(num_match.group(1))

        # 检测绑定命令
        bind_match = re.search(r"绑定\s*([A-Za-z0-9]+)", message)
        if bind_match:
            return FeishuCommand(
                action="bind",
                params={"binding_code": bind_match.group(1)},
                reply="正在验证绑定码...",
            )

        # 检测动作
        has_generate = any(kw in msg for kw in ["写", "生成", "创作", "帮我写", "帮我生成"])
        has_publish = any(kw in msg for kw in ["发布", "发到", "发表", "推送", "分发"])

        if has_generate and has_publish:
            return FeishuCommand(
                action="generate_and_publish",
                params={
                    "quantity": quantity,
                    "platforms": platforms,
                    "publish_strategy": "immediate",
                },
                reply=f"好的！正在为你生成{quantity}篇文章，完成后将发布到指定平台~",
            )
        elif has_generate:
            return FeishuCommand(
                action="generate",
                params={
                    "quantity": quantity,
                    "platforms": [],
                    "publish_strategy": "draft",
                },
                reply=f"收到！正在生成{quantity}篇文章草稿~",
            )
        elif has_publish:
            return FeishuCommand(
                action="publish",
                params={
                    "platforms": platforms,
                },
                reply="好的，正在为你发布文章~",
            )
        elif any(kw in msg for kw in ["进度", "状态", "怎么样", "结果", "如何"]):
            return FeishuCommand(
                action="query_status",
                params={},
                reply="正在查询最新任务进度~",
            )

        return None


# ==================== 单例 ====================

_instance: Optional[FeishuIntentParser] = None


def get_feishu_intent_parser() -> FeishuIntentParser:
    global _instance
    if _instance is None:
        _instance = FeishuIntentParser()
    return _instance
