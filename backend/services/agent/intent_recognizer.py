# -*- coding: utf-8 -*-
"""Intent recognition for the AutoGEO backend Agent."""

import json
import re
from typing import Any, Dict, List, Optional

import httpx

from backend.config import (
    AUTOGEO_CONVERSATION_LLM_API_KEY,
    AUTOGEO_CONVERSATION_LLM_BASE_URL,
    AUTOGEO_CONVERSATION_LLM_MODEL,
    AUTOGEO_CONVERSATION_LLM_PROVIDER,
    AUTOGEO_CONVERSATION_USE_LLM,
    DEEPSEEK_API_KEY,
    GLM_API_KEY,
)
from backend.services.agent.schemas import IntentResult


class IntentRecognizer:
    async def recognize(
        self,
        message: str,
        slots: Dict[str, Any],
        recent_messages: Optional[List[Dict[str, str]]] = None,
    ) -> IntentResult:
        if self._llm_enabled():
            parsed = await self._call_structured_llm(message, slots, recent_messages or [])
            if parsed and parsed.intent != "unknown":
                parsed.slots = self._enrich_slots(message, parsed.slots)
                parsed = self._normalize_parsed_by_message(message, parsed)
                if parsed.intent == "general_chat":
                    parsed = await self._attach_general_chat_answer(parsed, message, recent_messages or [])
                return parsed

        fallback = self._rule_based(message, slots)
        if fallback:
            if fallback.intent == "general_chat" and self._llm_enabled():
                fallback = await self._attach_general_chat_answer(fallback, message, recent_messages or [])
            return fallback

        return IntentResult(
            intent="unknown",
            slots={},
            confidence=0.0,
            reply="我还没有明确识别到要执行的 AutoGEO 任务。你可以告诉我：要生成什么主题、属于哪个项目、发布到哪个平台。",
        )

    def parser_status(self) -> Dict[str, Any]:
        provider = "local_rules"
        if self._llm_enabled():
            provider = AUTOGEO_CONVERSATION_LLM_PROVIDER
        return {
            "provider": provider,
            "llm_enabled": self._llm_enabled(),
            "llm_configured": self._llm_configured(),
            "llm_switch_on": AUTOGEO_CONVERSATION_USE_LLM,
            "model": AUTOGEO_CONVERSATION_LLM_MODEL if self._llm_enabled() else None,
        }

    def _llm_enabled(self) -> bool:
        return AUTOGEO_CONVERSATION_USE_LLM and self._llm_configured()

    def _llm_configured(self) -> bool:
        return bool(AUTOGEO_CONVERSATION_LLM_API_KEY or DEEPSEEK_API_KEY or GLM_API_KEY)

    def _api_key(self) -> str:
        return AUTOGEO_CONVERSATION_LLM_API_KEY or DEEPSEEK_API_KEY or GLM_API_KEY

    async def _call_structured_llm(
        self,
        message: str,
        slots: Dict[str, Any],
        recent_messages: List[Dict[str, str]],
    ) -> Optional[IntentResult]:
        api_key = self._api_key()
        if not api_key:
            return None

        context_payload = {
            "current_slots": slots,
            "recent_messages": recent_messages[-8:],
            "current_message": message,
        }
        payload = {
            "model": AUTOGEO_CONVERSATION_LLM_MODEL,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": json.dumps(context_payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{AUTOGEO_CONVERSATION_LLM_BASE_URL.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in {400, 422}:
                    relaxed_payload = dict(payload)
                    relaxed_payload.pop("response_format", None)
                    resp = await client.post(url, headers=headers, json=relaxed_payload)
                resp.raise_for_status()
                data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return self._parse_llm_json(content)
        except Exception:
            return None

    def _parse_llm_json(self, content: str) -> Optional[IntentResult]:
        clean = (content or "").strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        if not clean:
            return None

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", clean, flags=re.S)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

        return IntentResult(
            intent=self._normalize_intent(str(data.get("intent") or data.get("action") or "unknown")),
            slots=data.get("slots") or data.get("params") or {},
            confidence=float(data.get("confidence") or 0.75),
            reply=data.get("reply") or "我已经理解你的任务。",
        )

    async def _attach_general_chat_answer(
        self,
        parsed: IntentResult,
        message: str,
        recent_messages: List[Dict[str, str]],
    ) -> IntentResult:
        answer = await self._call_general_chat_llm(message, recent_messages)
        if not answer:
            answer = self._general_chat_reply(message)
        parsed.reply = answer
        parsed.slots = {"question": message, "answer": answer}
        return parsed

    async def _call_general_chat_llm(
        self,
        message: str,
        recent_messages: List[Dict[str, str]],
    ) -> Optional[str]:
        api_key = self._api_key()
        if not api_key:
            return None

        messages = [
            {"role": "system", "content": self._general_chat_system_prompt()},
            *recent_messages[-8:],
            {"role": "user", "content": message},
        ]
        payload = {
            "model": AUTOGEO_CONVERSATION_LLM_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 1200,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{AUTOGEO_CONVERSATION_LLM_BASE_URL.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() or None
        except Exception:
            return None

    def _system_prompt(self) -> str:
        return """你是 AutoGEO 后台 Agent 的意图解析器，只负责把用户自然语言解析成严格 JSON，不直接执行任务。

可用 intent：
- generate_article：生成文章草稿
- generate_and_publish：生成文章并准备发布
- publish_existing_article：发布已有文章
- query_task_status：查询任务状态
- confirm_task：用户确认执行待确认任务
- cancel_task：取消当前任务
- general_chat：普通问答、闲聊或询问智能体身份/模型/能力
- unknown：无法识别

可用平台 ID：
- zhihu：知乎
- xiaohongshu：小红书
- toutiao：今日头条
- baijiahao：百家号
- sohu：搜狐号
- douyin：抖音
- weixin：微信公众号

输出 JSON schema：
{
  "intent": "generate_and_publish",
  "slots": {
    "topic": "文章主题，可为空",
    "project_hint": "用户提到的项目、客户或公司名，可为空",
    "platforms": ["zhihu"],
    "quantity": 1,
    "publish_strategy": "immediate"
  },
  "confidence": 0.0,
  "reply": "一句简短中文回复"
}

规则：
1. 不要编造 project_id、account_id、article_id。
2. 用户说发布、发到某平台、自动发布时，设置 publish_strategy=immediate；真正发布仍由后端权限、账号和质检校验决定。
3. 如果用户只是在补充主题、项目或平台，要结合 current_slots 延续原任务。
4. 如果用户说确认、可以、开始发布，intent=confirm_task。
5. 信息不完整时，只提取用户明确表达过的字段。
6. “关于XX项目的文章”“XX项目的文章”“用XX项目”“这个项目是XX的”中的 XX 是 project_hint，不要只放到 topic。
7. 如果用户说“发布一篇/一个文章到某平台”，且没有给文章 ID 或“已有文章/这篇文章”等指代，intent=generate_and_publish。
8. AutoGEO 的文章生成优先围绕项目/公司蒸馏关键词；没有明确业务主题时 topic 可以为空。
9. 用户问“你是谁/你是什么模型/你能做什么/你好”等普通问题时，intent=general_chat，不要沿用上一轮任务意图。
10. 只输出 JSON，不要输出 Markdown。"""

    def _general_chat_system_prompt(self) -> str:
        return """你是 AutoGEO 后台智能体。
你可以自然回答用户的普通问题，也可以说明 AutoGEO 的能力边界。
当用户只是闲聊、询问模型、询问你能做什么时，直接用简洁中文回答。
不要假装已经执行任务；涉及项目、账号、发布权限、文章 ID 等事实时，不要编造。
如果用户提出生成文章、发布文章、查询任务进度等明确命令，只说明你可以帮助执行，并提示用户给出项目/公司和发布平台。"""

    def _rule_based(self, message: str, slots: Dict[str, Any]) -> Optional[IntentResult]:
        text = message.strip()
        platforms = self._extract_platforms(text)
        topic = self._extract_topic(text)
        project_hint = self._extract_project_hint(text)
        company_name = self._extract_company_name(text)
        quantity = self._extract_quantity(text)

        if self._is_general_chat(text):
            return IntentResult(
                intent="general_chat",
                slots={"question": text},
                confidence=0.9,
                reply=self._general_chat_reply(text),
            )

        if self._is_confirmation(text):
            return IntentResult(
                intent="confirm_task",
                slots={},
                confidence=0.9,
                reply="收到确认，正在准备执行。",
            )

        if any(word in text for word in ("取消", "停止", "不要发", "终止")):
            return IntentResult(
                intent="cancel_task",
                slots={},
                confidence=0.8,
                reply="收到，我会取消当前待确认任务。",
            )

        has_generate = any(word in text for word in ("写", "生成", "创作", "撰写", "起草", "来一篇"))
        has_publish = any(word in text for word in ("发布", "发到", "发表", "推送", "分发", "自动发"))
        has_status = any(word in text for word in ("进度", "状态", "结果", "怎么样"))
        has_article_request = any(word in text for word in ("文章", "稿子", "内容", "一篇", "一个文章"))
        explicit_existing_article = bool(re.search(r"(文章|稿子)\s*(ID|id|编号)?\s*[:：]?\s*\d+", text)) or any(
            word in text for word in ("已有文章", "现有文章", "刚才那篇", "这篇文章", "最近文章")
        )

        extracted: Dict[str, Any] = {
            "platforms": platforms,
            "topic": topic,
            "project_hint": project_hint,
            "company_name": company_name,
            "quantity": quantity,
            "publish_strategy": "immediate" if has_publish else "review_first",
        }
        extracted = {k: v for k, v in extracted.items() if v not in (None, "", [])}

        if (has_generate and has_publish) or (has_publish and has_article_request and not explicit_existing_article):
            return IntentResult(
                intent="generate_and_publish",
                slots=extracted,
                confidence=0.78,
                reply="我理解为生成文章并发布。",
            )
        if has_generate:
            return IntentResult(
                intent="generate_article",
                slots=extracted,
                confidence=0.76,
                reply="我理解为生成文章草稿。",
            )
        if has_publish:
            return IntentResult(
                intent="publish_existing_article",
                slots=extracted,
                confidence=0.7,
                reply="我理解为发布已有文章。",
            )
        if has_status:
            return IntentResult(
                intent="query_task_status",
                slots={},
                confidence=0.75,
                reply="我会查询你的最近任务进度。",
            )

        if slots.get("waiting_for"):
            return IntentResult(
                intent=slots.get("intent") or "unknown",
                slots=extracted,
                confidence=0.55,
                reply="我会把这条补充信息合并到当前任务里。",
            )

        return None

    def _normalize_parsed_by_message(self, message: str, parsed: IntentResult) -> IntentResult:
        text = message.strip()
        if self._is_general_chat(text):
            parsed.intent = "general_chat"
            parsed.slots = {"question": text}
            return parsed
        has_publish = any(word in text for word in ("发布", "发到", "发表", "推送", "分发", "自动发"))
        has_article_request = any(word in text for word in ("文章", "稿子", "内容", "一篇", "一个文章"))
        explicit_existing_article = bool(re.search(r"(文章|稿子)\s*(ID|id|编号)?\s*[:：]?\s*\d+", text)) or any(
            word in text for word in ("已有文章", "现有文章", "刚才那篇", "这篇文章", "最近文章")
        )
        if parsed.intent == "publish_existing_article" and has_publish and has_article_request and not explicit_existing_article:
            parsed.intent = "generate_and_publish"
            parsed.reply = "我理解为生成文章并发布。"
        if parsed.intent == "generate_and_publish":
            parsed.slots["publish_strategy"] = "immediate"
        return parsed

    def _normalize_intent(self, action: str) -> str:
        mapping = {
            "generate": "generate_article",
            "generate_article": "generate_article",
            "generate_and_publish": "generate_and_publish",
            "publish": "publish_existing_article",
            "publish_existing_article": "publish_existing_article",
            "query_status": "query_task_status",
            "query_task_status": "query_task_status",
            "confirm": "confirm_task",
            "confirm_task": "confirm_task",
            "cancel": "cancel_task",
            "cancel_task": "cancel_task",
            "bind": "bind_external_account",
            "chat": "general_chat",
            "general_chat": "general_chat",
            "smalltalk": "general_chat",
        }
        return mapping.get(action, action)

    def _is_general_chat(self, message: str) -> bool:
        text = message.strip()
        task_words = ("生成", "写", "发布", "发到", "查询", "进度", "状态", "项目是", "公司是", "确认", "取消")
        general_patterns = (
            "你是谁",
            "你是什么",
            "什么模型",
            "哪个模型",
            "你能做什么",
            "你可以做什么",
            "你的能力",
            "介绍一下你",
            "你好",
            "在吗",
        )
        if any(pattern in text for pattern in general_patterns):
            return not any(word in text for word in task_words)
        return False

    def _general_chat_reply(self, message: str) -> str:
        if "模型" in message:
            return (
                "我是 AutoGEO 后台智能体。自然语言字段识别优先使用已配置的 DeepSeek，"
                "同时会用本地规则做兜底和纠偏；真正的项目、账号和发布权限由后端查库确认。"
            )
        if "能做什么" in message or "可以做什么" in message or "能力" in message:
            return "我可以根据项目或公司识别发布需求，蒸馏关键词，生成文章，并按你指定的平台自动发布。"
        return "你好，我是 AutoGEO 后台智能体。你可以告诉我要使用哪个项目或公司，以及要发布到哪个平台。"

    def _enrich_slots(self, message: str, params: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(params or {})
        platforms = self._extract_platforms(message)
        topic = self._extract_topic(message)
        project_hint = self._extract_project_hint(message)
        company_name = self._extract_company_name(message)
        quantity = self._extract_quantity(message)

        if platforms:
            enriched["platforms"] = platforms
        if topic:
            enriched["topic"] = topic
        if project_hint:
            enriched["project_hint"] = project_hint
        if company_name:
            enriched["company_name"] = company_name
        if quantity:
            enriched["quantity"] = quantity
        if "publish_strategy" not in enriched:
            enriched["publish_strategy"] = "immediate" if self._extract_platforms(message) and any(
                word in message for word in ("发布", "发到", "发表", "推送", "分发", "自动发")
            ) else "review_first"
        return enriched

    def _extract_platforms(self, message: str) -> List[str]:
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
        platforms = [value for alias, value in platform_aliases.items() if alias in message]
        return list(dict.fromkeys(platforms))

    def _extract_topic(self, message: str) -> Optional[str]:
        patterns = [
            r"关于(.+?)的(?:文章|内容|稿子)",
            r"主题(?:是|为|：|:)\s*(.+?)(?:，|。|,|$)",
            r"写一篇(.+?)(?:文章|内容|稿子)",
            r"生成一篇(.+?)(?:文章|内容|稿子)",
            r"来一篇(.+?)(?:文章|内容|稿子)?(?:，|。|,|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                topic = match.group(1).strip(" ，。,.")
                return topic[:80] if topic else None
        return None

    def _extract_project_hint(self, message: str) -> Optional[str]:
        patterns = [
            r"关于(.+?)(?:项目|客户|公司)的(?:文章|内容|稿子)",
            r"给(.+?)(?:生成|写|创作|撰写|起草|发|发布)",
            r"用(.+?)(?:项目|客户)",
            r"(?:这个|该|当前)?(?:项目|客户)(?:是|为|叫|：|:)\s*(.+?)(?:，|。|,|$)",
            r"(.+?)(?:项目)(?:，|。|,|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                value = self._clean_entity_hint(match.group(1))
                return value[:80] if value else None
        return None

    def _extract_company_name(self, message: str) -> Optional[str]:
        patterns = [
            r"(?:这个|该|当前)?(?:公司|企业)(?:是|为|叫|：|:)\s*(.+?)(?:，|。|,|$)",
            r"(.+?)(?:公司|企业)(?:，|。|,|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                value = self._clean_entity_hint(match.group(1))
                return value[:80] if value else None
        return None

    def _clean_entity_hint(self, value: str) -> str:
        value = (value or "").strip(" ，。,.")
        for prefix in ("我说的", "我要用", "这个", "该", "当前", "项目是", "公司是"):
            if value.startswith(prefix):
                value = value[len(prefix):].strip(" ，。,.")
        while len(value) > 1 and value.endswith(("的", "项目", "公司", "客户")):
            for suffix in ("项目", "公司", "客户", "的"):
                if value.endswith(suffix) and len(value) > len(suffix):
                    value = value[: -len(suffix)].strip(" ，。,.")
                    break
            else:
                break
        if value.startswith("我"):
            value = value[1:].strip(" ，。,.")
        return value

    def _extract_quantity(self, message: str) -> Optional[int]:
        match = re.search(r"(\d+)\s*[篇个条]", message)
        if match:
            return max(1, min(int(match.group(1)), 10))
        return 1 if any(word in message for word in ("写", "生成", "来一篇")) else None

    def _is_confirmation(self, message: str) -> bool:
        text = message.strip()
        return text in {"确认", "确认发布", "可以", "执行", "开始发布", "同意", "是的"} or text.startswith("确认")


_instance: Optional[IntentRecognizer] = None


def get_intent_recognizer() -> IntentRecognizer:
    global _instance
    if _instance is None:
        _instance = IntentRecognizer()
    return _instance
