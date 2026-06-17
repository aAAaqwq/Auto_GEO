# -*- coding: utf-8 -*-
"""
CDP连接管理器
用于连接本地浏览器（通过内网穿透暴露的CDP端口）
"""

import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from backend.config import LOCAL_BROWSER_URL, LOCAL_BROWSER_CDP_PORT


class CDPBrowserManager:
    """
    CDP浏览器连接管理器

    用于连接本地浏览器（通过CDP协议）
    本地浏览器由Electron端启动，通过内网穿透暴露到公网
    """

    _instance: Optional["CDPBrowserManager"] = None
    _playwright = None
    _browser: Optional[Browser] = None
    _contexts: Dict[str, BrowserContext] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._browser is not None and self._browser.is_connected()

    def get_cdp_url(self) -> str:
        """
        获取CDP连接地址

        Returns:
            CDP URL
        """
        if LOCAL_BROWSER_URL:
            # 使用配置的公网地址
            return f"{LOCAL_BROWSER_URL.rstrip('/')}/"
        else:
            # 默认本地地址
            return f"http://localhost:{LOCAL_BROWSER_CDP_PORT}"

    async def connect(self, cdp_url: Optional[str] = None) -> bool:
        """
        通过CDP连接本地浏览器

        Args:
            cdp_url: CDP地址，默认使用配置中的地址

        Returns:
            是否连接成功
        """
        if self._browser and self._browser.is_connected():
            logger.info("浏览器已连接，复用现有连接")
            return True

        target_url = cdp_url or self.get_cdp_url()
        logger.info(f"🔗 正在通过CDP连接本地浏览器: {target_url}")

        try:
            # 保持 playwright 实例，不能用 async with (context manager 退出后会 stop)
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            # 通过CDP连接到已有浏览器
            self._browser = await self._playwright.chromium.connect_over_cdp(target_url)

            if self._browser.is_connected():
                logger.info("✅ CDP浏览器连接成功！")
                return True
            else:
                logger.error("❌ CDP浏览器连接失败")
                self._browser = None
                return False

        except Exception as e:
            logger.error(f"❌ CDP连接失败: {e}")
            self._browser = None
            return False

    async def disconnect(self) -> bool:
        """
        断开CDP连接

        Returns:
            是否成功断开
        """
        try:
            # 关闭所有上下文
            for ctx_id in list(self._contexts.keys()):
                await self.close_context(ctx_id)

            # CDP连接不关闭远程浏览器, 只断开连接
            if self._browser:
                self._browser = None
                logger.info("✅ CDP浏览器连接已断开")

            # 停止 playwright 实例
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            return True
        except Exception as e:
            logger.error(f"断开CDP连接失败: {e}")
            return False

    async def create_context(self, storage_state: Optional[Dict] = None) -> Optional[BrowserContext]:
        """
        创建浏览器上下文

        Args:
            storage_state: 可选的存储状态（cookies等）

        Returns:
            BrowserContext实例
        """
        if not self._browser or not self._browser.is_connected():
            logger.error("浏览器未连接，无法创建上下文")
            return None

        try:
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "locale": "zh-CN",
            }

            if storage_state:
                context_options["storage_state"] = storage_state

            context = await self._browser.new_context(**context_options)
            context_id = f"context_{id(context)}"
            self._contexts[context_id] = context

            logger.info(f"✅ 创建浏览器上下文: {context_id}")
            return context

        except Exception as e:
            logger.error(f"创建浏览器上下文失败: {e}")
            return None

    async def close_context(self, context_id: str) -> bool:
        """
        关闭浏览器上下文

        Args:
            context_id: 上下文ID

        Returns:
            是否成功关闭
        """
        if context_id in self._contexts:
            try:
                await self._contexts[context_id].close()
                del self._contexts[context_id]
                logger.info(f"✅ 关闭浏览器上下文: {context_id}")
                return True
            except Exception as e:
                logger.error(f"关闭上下文失败: {e}")
                return False
        return False

    def get_status(self) -> Dict[str, Any]:
        """
        获取连接状态

        Returns:
            状态信息
        """
        return {
            "connected": self.is_connected,
            "cdp_url": self.get_cdp_url(),
            "context_count": len(self._contexts),
        }


# 全局单例
cdp_browser_manager = CDPBrowserManager()
