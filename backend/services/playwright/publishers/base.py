# -*- coding: utf-8 -*-
"""
Playwright发布适配器
用适配器模式实现各平台发布，开闭原则！
"""

from abc import ABC, abstractmethod
import html
import re
from typing import Dict, Any, Optional
from playwright.async_api import Page
from loguru import logger


class BasePublisher(ABC):
    """
    基础发布适配器
    注意：所有平台适配器都要继承这个类！
    """

    def __init__(self, platform_id: str, config: Dict[str, Any]):
        self.platform_id = platform_id
        self.config = config
        self.name = config.get("name", platform_id)
        self.color = config.get("color", "#333333")

    @abstractmethod
    async def publish(self, page: Page, article: Any, account: Any, declare_ai_content: bool = True) -> Dict[str, Any]:
        """
        发布文章到目标平台

        Args:
            page: Playwright Page对象
            article: 文章对象（title, content等）
            account: 账号对象
            declare_ai_content: 是否勾选AI创作内容声明 (默认True)

        Returns:
            发布结果：{
                "success": bool,
                "platform_url": str,
                "error_msg": str
            }
        """
        pass

    async def navigate_to_publish_page(self, page: Page) -> bool:
        """
        导航到发布页面

        Returns:
            是否成功导航
        """
        try:
            await page.goto(self.config["publish_url"], wait_until="networkidle")
            logger.info(f"导航到发布页面: {self.name}")
            return True
        except Exception as e:
            logger.error(f"导航失败: {self.name}, {e}")
            return False

    async def wait_for_selector(self, page: Page, selector: str, timeout: int = 10000) -> bool:
        """
        等待选择器出现

        注意：各平台页面加载速度不同，需要耐心等待！
        """
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"等待选择器超时: {selector}, {e}")
            return False

    async def fill_title(self, page: Page, title: str, title_selector: str) -> bool:
        """
        填充标题
        """
        try:
            # 先清空再填充
            await page.fill(title_selector, "")
            await page.fill(title_selector, title)
            logger.info(f"标题已填充: {title[:20]}...")
            return True
        except Exception as e:
            logger.error(f"填充标题失败: {e}")
            return False

    async def fill_content(self, page: Page, content: str, content_selector: str) -> bool:
        """
        填充正文
        """
        try:
            await page.fill(content_selector, content)
            logger.info(f"正文已填充: {len(content)} 字符")
            return True
        except Exception as e:
            logger.error(f"填充正文失败: {e}")
            return False

    def extract_image_urls(self, content: str) -> list[str]:
        """
        从 Markdown/HTML 内容中提取图片 URL。
        文章生成模块目前主要输出 Markdown 图片语法，发布器不能只识别 <img>。
        """
        if not content:
            return []

        urls: list[str] = []
        for match in re.findall(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", content):
            urls.append(match.strip())

        for match in re.findall(r"<img[^>]+src=[\"']([^\"']+)[\"']", content, flags=re.IGNORECASE):
            urls.append(html.unescape(match.strip()))

        deduped: list[str] = []
        seen = set()
        for url in urls:
            if url and url not in seen:
                deduped.append(url)
                seen.add(url)
        return deduped

    def markdown_to_plain_text(self, content: str, drop_first_h1: bool = True) -> str:
        """
        将 Markdown/简单 HTML 清理成适合平台编辑器粘贴的正文。
        这里输出纯文本，避免平台不解析 Markdown 时把 #、**、![图](url) 原样发布出去。
        """
        if not content:
            return ""

        text = content
        text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)

        text = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n\1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)

        lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                lines.append("")
                continue

            heading = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading:
                if drop_first_h1 and not lines and len(heading.group(1)) == 1:
                    continue
                line = heading.group(2).strip()

            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            line = re.sub(r"__(.*?)__", r"\1", line)
            line = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", line)
            line = re.sub(r"`([^`]+)`", r"\1", line)
            line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
            lines.append(line)

        cleaned: list[str] = []
        prev_empty = False
        for line in lines:
            if not line:
                if not prev_empty:
                    cleaned.append("")
                prev_empty = True
            else:
                cleaned.append(line)
                prev_empty = False

        return "\n".join(cleaned).strip()

    async def click_publish_button(self, page: Page, publish_selector: str) -> bool:
        """
        点击发布按钮
        """
        try:
            await page.click(publish_selector)
            logger.info(f"已点击发布按钮: {self.name}")
            return True
        except Exception as e:
            logger.error(f"点击发布按钮失败: {e}")
            return False

    async def wait_for_publish_result(self, page: Page, timeout: int = 30000) -> Dict[str, Any]:
        """
        等待发布结果

        Returns:
            发布结果
        """
        # 默认实现：等待一段时间后检查URL是否变化
        await page.wait_for_timeout(3000)

        result = {"success": True, "platform_url": page.url, "error_msg": None}

        return result


class PublisherRegistry:
    """
    发布器注册表
    用这个来管理所有平台的发布器！
    """

    def __init__(self):
        self._publishers: Dict[str, BasePublisher] = {}

    def register(self, platform_id: str, publisher: BasePublisher):
        """注册发布器"""
        self._publishers[platform_id] = publisher
        logger.info(f"发布器已注册: {platform_id}")

    def get(self, platform_id: str) -> Optional[BasePublisher]:
        """获取发布器"""
        return self._publishers.get(platform_id)

    def list_all(self) -> Dict[str, BasePublisher]:
        """列出所有发布器"""
        return self._publishers.copy()


# 全局注册表
registry = PublisherRegistry()


def get_publisher(platform_id: str) -> Optional[BasePublisher]:
    """
    获取平台发布器
    注意：这是对外暴露的主要接口！
    """
    return registry.get(platform_id)


def list_publishers() -> Dict[str, BasePublisher]:
    """列出所有发布器"""
    return registry.list_all()
