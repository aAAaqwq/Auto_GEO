# -*- coding: utf-8 -*-
"""
飞书开放平台 API 客户端
封装消息发送、签名验证、Token 管理等基础能力
"""

import hashlib
import hmac
import base64
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from loguru import logger

from backend.config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_VERIFICATION_TOKEN,
    FEISHU_ENCRYPT_KEY,
)

log = logger.bind(module="飞书客户端")


class FeishuClient:
    """
    飞书开放平台 API 客户端

    负责：
    1. tenant_access_token 获取与缓存
    2. 消息发送（文本、富文本、卡片）
    3. Webhook 签名验证
    """

    # 飞书开放平台 API 基础 URL
    API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(self):
        self._app_id = FEISHU_APP_ID
        self._app_secret = FEISHU_APP_SECRET
        self._verification_token = FEISHU_VERIFICATION_TOKEN
        self._encrypt_key = FEISHU_ENCRYPT_KEY
        self._client: Optional[httpx.AsyncClient] = None

        # Token 缓存
        self._tenant_token: Optional[str] = None
        self._token_expires_at: float = 0

    @property
    def is_configured(self) -> bool:
        """检查飞书配置是否完整"""
        return bool(self._app_id and self._app_secret)

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（懒加载）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ==================== Token 管理 ====================

    async def _get_tenant_token(self) -> str:
        """
        获取 tenant_access_token（带缓存）

        Token 有效期 2 小时，提前 5 分钟刷新
        """
        if self._tenant_token and time.time() < self._token_expires_at:
            return self._tenant_token

        url = f"{self.API_BASE}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self._app_id,
            "app_secret": self._app_secret,
        }

        try:
            resp = await self.client.post(url, json=payload)
            data = resp.json()

            if data.get("code") != 0:
                log.error(f"获取 tenant_access_token 失败: {data.get('msg')}")
                raise Exception(f"获取飞书 token 失败: {data.get('msg')}")

            self._tenant_token = data["tenant_access_token"]
            # 提前 5 分钟过期
            expire_seconds = data.get("expire", 7200)
            self._token_expires_at = time.time() + expire_seconds - 300

            log.debug("飞书 tenant_access_token 刷新成功")
            return self._tenant_token

        except httpx.HTTPError as e:
            log.error(f"飞书 token 请求异常: {e}")
            raise

    # ==================== 签名验证 ====================

    def verify_signature(self, timestamp: str, nonce: str, body: str, signature: str) -> bool:
        """
        验证飞书 Webhook 请求签名

        飞书签名算法：
        signature = sha256(timestamp + nonce + encrypt_key + body)
        """
        if not self._encrypt_key:
            # 未配置加密 key 时跳过验签
            return True

        content = f"{timestamp}{nonce}{self._encrypt_key}{body}"
        expected = hashlib.sha256(content.encode()).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_token(self, token: str) -> bool:
        """验证 Verification Token"""
        if not self._verification_token:
            return True
        return token == self._verification_token

    # ==================== 消息发送 ====================

    async def _get_auth_headers(self) -> Dict[str, str]:
        """获取带认证的请求头"""
        token = await self._get_tenant_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    async def send_text_message(self, chat_id: str, text: str) -> bool:
        """
        发送文本消息

        Args:
            chat_id: 群聊 ID 或用户 open_id
            text: 文本内容

        Returns:
            是否发送成功
        """
        url = f"{self.API_BASE}/im/v1/messages"
        headers = await self._get_auth_headers()
        params = {"receive_id_type": "chat_id"}
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }

        try:
            resp = await self.client.post(url, headers=headers, params=params, json=payload)
            data = resp.json()
            if data.get("code") != 0:
                log.error(f"发送文本消息失败: {data.get('msg')}")
                return False
            log.debug(f"文本消息已发送到 {chat_id}")
            return True
        except Exception as e:
            log.error(f"发送文本消息异常: {e}")
            return False

    async def send_card_message(self, chat_id: str, card: Dict[str, Any]) -> bool:
        """
        发送卡片消息

        Args:
            chat_id: 群聊 ID
            card: 飞书卡片 JSON 结构

        Returns:
            是否发送成功
        """
        url = f"{self.API_BASE}/im/v1/messages"
        headers = await self._get_auth_headers()
        params = {"receive_id_type": "chat_id"}
        payload = {
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card),
        }

        try:
            resp = await self.client.post(url, headers=headers, params=params, json=payload)
            data = resp.json()
            if data.get("code") != 0:
                log.error(f"发送卡片消息失败: {data.get('msg')}")
                return False
            log.debug(f"卡片消息已发送到 {chat_id}")
            return True
        except Exception as e:
            log.error(f"发送卡片消息异常: {e}")
            return False

    async def send_progress_card(
        self,
        chat_id: str,
        title: str,
        status: str,
        detail: str = "",
        progress: Optional[str] = None,
    ) -> bool:
        """
        发送进度通知卡片

        Args:
            chat_id: 群聊 ID
            title: 卡片标题
            status: 状态标签（处理中/已完成/失败）
            detail: 详细描述
            progress: 进度信息，如 "2/5"
        """
        # 状态颜色
        color_map = {
            "处理中": "blue",
            "已完成": "green",
            "失败": "red",
            "生成中": "blue",
            "发布中": "blue",
        }
        tag_color = color_map.get(status, "blue")

        elements = []

        if detail:
            elements.append({
                "tag": "markdown",
                "content": detail,
            })

        if progress:
            elements.append({
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": f"📊 进度: {progress}",
                    }
                ],
            })

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": tag_color,
            },
            "elements": elements,
        }

        return await self.send_card_message(chat_id, card)

    async def send_result_card(
        self,
        chat_id: str,
        title: str,
        success: bool,
        summary: str,
        details: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """
        发送结果汇报卡片

        Args:
            chat_id: 群聊 ID
            title: 标题
            success: 是否成功
            summary: 汇总信息
            details: 详细条目列表 [{"name": "xxx", "status": "成功/失败", "link": "url"}]
        """
        template = "green" if success else "red"
        elements = [
            {
                "tag": "markdown",
                "content": summary,
            }
        ]

        if details:
            lines = []
            for item in details:
                status_icon = "✅" if item.get("status") == "成功" else "❌"
                link = item.get("link", "")
                name = item.get("name", "")
                if link:
                    lines.append(f"{status_icon} [{name}]({link})")
                else:
                    lines.append(f"{status_icon} {name}")
            elements.append({
                "tag": "markdown",
                "content": "\n".join(lines),
            })

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": template,
            },
            "elements": elements,
        }

        return await self.send_card_message(chat_id, card)

    async def send_publish_result_card(
        self,
        chat_id: str,
        success: bool,
        article_title: str = "",
        platform_name: str = "",
        platform_url: str = "",
        project_name: str = "",
        company_name: str = "",
        keyword: str = "",
        account_name: str = "",
        error_msg: str = "",
    ) -> bool:
        """
        发送发布结果卡片（包含完整上下文信息）

        Args:
            chat_id: 群聊 ID
            success: 是否成功
            article_title: 文章标题
            platform_name: 目标平台
            platform_url: 平台链接
            project_name: 项目名
            company_name: 公司名
            keyword: 关键词
            account_name: 发布账号
            error_msg: 错误信息
        """
        template = "green" if success else "red"
        status_text = "✅ 发布成功" if success else "❌ 发布失败"
        title_text = f"{status_text}: {article_title[:30]}{'...' if len(article_title) > 30 else ''}"

        # 卡片元素
        elements = []

        # 基本信息区
        info_lines = []
        if company_name:
            info_lines.append(f"**公司**: {company_name}")
        if project_name:
            info_lines.append(f"**项目**: {project_name}")
        if keyword:
            info_lines.append(f"**关键词**: {keyword}")
        if platform_name:
            info_lines.append(f"**平台**: {platform_name}")
        if account_name:
            info_lines.append(f"**账号**: {account_name}")
        if platform_url:
            info_lines.append(f"\n🔗 [查看文章]({platform_url})")

        elements.append({
            "tag": "markdown",
            "content": "\n".join(info_lines),
        })

        if not success and error_msg:
            elements.append({
                "tag": "markdown",
                "content": f"**错误原因**: {error_msg[:200]}",
            })

        if not success:
            elements.append({
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "💡 提示：请检查账号授权状态，或在管理后台重新授权后再试。",
                    }
                ],
            })

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title_text,
                },
                "template": template,
            },
            "elements": elements,
        }

        return await self.send_card_message(chat_id, card)


# ==================== 单例模式 ====================

_instance: Optional[FeishuClient] = None


def get_feishu_client() -> FeishuClient:
    """获取飞书客户端单例"""
    global _instance
    if _instance is None:
        _instance = FeishuClient()
    return _instance
