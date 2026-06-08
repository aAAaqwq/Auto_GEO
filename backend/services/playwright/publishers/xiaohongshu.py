# -*- coding: utf-8 -*-
"""
Xiaohongshu publisher.

This adapter follows the Xiaohongshu long-article flow:
1. Open creator publish page.
2. Switch to the long-article tab.
3. Fill the GEO article title/body.
4. Click "一键排版".
5. Click "一键发布".
6. Wait for a success signal.
"""

import os
import random
import re
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from playwright.async_api import Locator, Page

from .base import BasePublisher, registry


class XiaohongshuPublisher(BasePublisher):
    MAX_IMAGES = 9
    MAX_TITLE_LENGTH = 50
    MAX_BODY_LENGTH = 5000

    async def publish(self, page: Page, article: Any, account: Any, declare_ai_content: bool = True) -> Dict[str, Any]:
        temp_files: List[str] = []
        stage = "init"

        try:
            title = self._clean_title(getattr(article, "title", "") or "未命名笔记")
            raw_content = getattr(article, "content", "") or ""
            content_blocks = self._build_note_blocks(raw_content, title)

            stage = "navigate"
            await self._navigate_to_publisher(page)
            await self._ensure_logged_in(page)

            stage = "select_long_article"
            if not await self._select_long_article(page):
                return await self._fail(page, stage, "未能进入小红书“写长文/新的创作”编辑器")

            stage = "document_import"
            imported = await self._import_markdown_document(page, raw_content, title, temp_files)
            if not imported:
                logger.warning("[xiaohongshu] markdown document import failed; fallback to manual editor fill")
                stage = "fill_title"
                if not await self._fill_text_field(page, self._title_selectors(), title):
                    return await self._fail(page, stage, "未找到小红书标题输入框")

                stage = "fill_content"
                if not await self._fill_content_blocks(page, content_blocks, temp_files):
                    return await self._fail(page, stage, "未找到小红书正文输入框")

            if declare_ai_content:
                stage = "declare_ai"
                await self._try_declare_ai_content(page)

            stage = "one_key_layout"
            if not await self._click_one_key_layout(page):
                return await self._fail(page, stage, "未找到可点击的小红书“一键排版”按钮，或按钮仍处于禁用状态")

            stage = "layout_next"
            if not await self._click_layout_next(page):
                return await self._fail(page, stage, "排版后未找到可点击的小红书“下一步”按钮，或按钮仍处于禁用状态")

            stage = "one_key_publish"
            if not await self._click_one_key_publish(page):
                return await self._fail(page, stage, "未找到可点击的小红书“一键发布”按钮，或按钮仍处于禁用状态")

            stage = "wait_result"
            return await self._wait_for_publish_result(page)

        except Exception as exc:
            logger.exception(f"[xiaohongshu] publish failed at stage={stage}: {exc}")
            return await self._fail(page, stage, str(exc))
        finally:
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as exc:
                    logger.warning(f"[xiaohongshu] failed to remove temp image {file_path}: {exc}")

    async def _navigate_to_publisher(self, page: Page) -> None:
        publish_url = self.config.get("publish_url", "https://creator.xiaohongshu.com/publish/publish")
        await self._prepare_browser_permissions(page)
        try:
            await page.goto(publish_url, wait_until="networkidle", timeout=60000)
        except Exception:
            await page.goto(publish_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        logger.info(f"[xiaohongshu] opened publish page: {page.url}")

    async def _prepare_browser_permissions(self, page: Page) -> None:
        try:
            context = page.context
            await context.set_geolocation({"latitude": 31.2304, "longitude": 121.4737})
            await context.grant_permissions(["geolocation"], origin="https://creator.xiaohongshu.com")
            logger.info("[xiaohongshu] granted browser geolocation permission")
        except Exception as exc:
            logger.debug(f"[xiaohongshu] failed to prepare browser permissions: {exc}")

    async def _ensure_logged_in(self, page: Page) -> None:
        current_url = page.url.lower()
        if "login" in current_url:
            raise RuntimeError("小红书账号登录态已失效，请在账号管理中重新授权")

        login_markers = [
            "text=登录",
            "text=扫码登录",
            "text=验证码登录",
        ]
        for selector in login_markers:
            try:
                marker = page.locator(selector).first
                if await marker.count() > 0 and await marker.is_visible():
                    raise RuntimeError("小红书账号登录态已失效，请在账号管理中重新授权")
            except RuntimeError:
                raise
            except Exception:
                continue

    def _clean_title(self, title: str) -> str:
        text = re.sub(r"\s+", " ", title.replace("#", "")).strip()
        if len(text) > self.MAX_TITLE_LENGTH:
            return text[: self.MAX_TITLE_LENGTH]
        return text or "未命名笔记"

    def _build_note_body(self, content: str, title: str) -> str:
        body = self.markdown_to_plain_text(content, drop_first_h1=True)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        if len(body) > self.MAX_BODY_LENGTH:
            body = body[: self.MAX_BODY_LENGTH].rstrip() + "..."

        topics = self._extract_topics(title, body)
        topic_line = " ".join(f"#{topic}" for topic in topics)
        if topic_line and topic_line not in body:
            body = f"{body}\n\n{topic_line}" if body else topic_line
        return body

    def _build_note_blocks(self, content: str, title: str) -> List[Dict[str, str]]:
        blocks: List[Dict[str, str]] = []
        if not content:
            return [{"type": "text", "value": self._build_note_body("", title)}]

        image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
        position = 0
        for match in image_pattern.finditer(content):
            text_part = content[position : match.start()]
            cleaned_text = self.markdown_to_plain_text(text_part, drop_first_h1=(len(blocks) == 0))
            cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()
            if cleaned_text:
                blocks.append({"type": "text", "value": cleaned_text})

            image_url = match.group(2).strip()
            if image_url:
                blocks.append({"type": "image", "value": image_url})
            position = match.end()

        tail_text = content[position:]
        cleaned_tail = self.markdown_to_plain_text(tail_text, drop_first_h1=(len(blocks) == 0))
        cleaned_tail = re.sub(r"\n{3,}", "\n\n", cleaned_tail).strip()
        if cleaned_tail:
            blocks.append({"type": "text", "value": cleaned_tail})

        topic_line = " ".join(f"#{topic}" for topic in self._extract_topics(title, self.markdown_to_plain_text(content)))
        if topic_line:
            if blocks and blocks[-1]["type"] == "text":
                blocks[-1]["value"] = f"{blocks[-1]['value']}\n\n{topic_line}"
            else:
                blocks.append({"type": "text", "value": topic_line})

        return blocks or [{"type": "text", "value": self._build_note_body(content, title)}]

    def _build_import_markdown(self, content: str, title: str) -> str:
        text = (content or "").strip()
        if not text:
            text = f"# {title}\n\n"
        elif not re.match(r"^\s*#\s+", text):
            text = f"# {title}\n\n{text}"
        return f"{text.rstrip()}\n"

    def _create_import_markdown_file(self, content: str, title: str) -> str:
        safe_name = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", title).strip("_") or "xhs_article"
        safe_name = safe_name[:40]
        path = os.path.join(tempfile.gettempdir(), f"{safe_name}_{random.randint(10000, 99999)}.md")
        with open(path, "w", encoding="utf-8", newline="\n") as file:
            file.write(self._build_import_markdown(content, title))
        return path

    def _extract_topics(self, title: str, body: str) -> List[str]:
        candidates: List[str] = []
        for text in (title, body[:120]):
            for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", text):
                if token not in candidates:
                    candidates.append(token)
        return candidates[:3] or ["商业", "科技"]

    async def _download_article_images(self, urls: List[str], keyword: str) -> List[str]:
        paths: List[str] = []
        if not urls:
            return paths

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        backend_base_url = os.getenv("BACKEND_PUBLIC_BASE_URL", "http://localhost:8001")

        async with httpx.AsyncClient(headers=headers, verify=False, follow_redirects=True, timeout=30.0) as client:
            for index, original_url in enumerate(urls[: self.MAX_IMAGES]):
                url = original_url.strip()
                if not url:
                    continue
                if url.startswith("/static/"):
                    url = f"{backend_base_url}{url}"
                elif url.startswith("//"):
                    url = f"https:{url}"
                elif url.startswith("/"):
                    logger.warning(f"[xiaohongshu] skip unsupported local image path: {url}")
                    continue

                for attempt in range(2):
                    try:
                        response = await client.get(url)
                        if response.status_code == 200 and len(response.content) > 1000:
                            suffix = self._image_suffix(response.headers.get("content-type", ""), url)
                            path = os.path.join(
                                tempfile.gettempdir(),
                                f"xhs_article_{random.randint(10000, 99999)}_{index}{suffix}",
                            )
                            with open(path, "wb") as file:
                                file.write(response.content)
                            paths.append(path)
                            logger.info(f"[xiaohongshu] downloaded article image {index + 1}: {len(response.content)} bytes")
                            break
                        logger.warning(
                            f"[xiaohongshu] image download rejected: status={response.status_code}, size={len(response.content)}"
                        )
                    except Exception as exc:
                        logger.warning(f"[xiaohongshu] image download failed attempt={attempt + 1}: {exc}")

        return paths

    async def _download_single_article_image(self, url: str, index: int) -> Optional[str]:
        paths = await self._download_article_images([url], keyword=f"article_{index}")
        return paths[0] if paths else None

    async def _import_markdown_document(
        self,
        page: Page,
        content: str,
        title: str,
        temp_files: List[str],
    ) -> bool:
        import_path = self._create_import_markdown_file(content, title)
        temp_files.append(import_path)

        if not await self._has_document_import_modal(page):
            opened = await self._open_document_import_modal(page)
            if not opened:
                return False

        file_input = await self._find_document_import_file_input(page)
        if not file_input:
            return False

        try:
            await file_input.set_input_files(import_path)
            logger.info(f"[xiaohongshu] imported markdown document: {import_path}")
            return await self._wait_for_markdown_import_done(page)
        except Exception as exc:
            logger.warning(f"[xiaohongshu] markdown document import failed: {exc}")
            return False

    async def _has_document_import_modal(self, page: Page) -> bool:
        try:
            body_text = await page.locator("body").inner_text(timeout=3000)
            return "文档导入" in body_text and ("点击或拖拽上传" in body_text or "docx" in body_text or "md" in body_text)
        except Exception:
            return False

    async def _open_document_import_modal(self, page: Page) -> bool:
        if await self._click_document_import_by_text(page):
            return await self._wait_for_document_import_modal(page)

        if await self._click_document_import_by_toolbar_scan(page):
            return await self._wait_for_document_import_modal(page)

        return False

    async def _click_document_import_by_text(self, page: Page) -> bool:
        texts = ["文档导入", "导入文档", "导入"]
        for text in texts:
            try:
                target = page.get_by_text(text, exact=False).first
                if await target.count() > 0 and await target.is_visible():
                    await target.click(timeout=3000)
                    logger.info(f"[xiaohongshu] clicked document import text: {text}")
                    return True
            except Exception:
                continue
        return False

    async def _click_document_import_by_toolbar_scan(self, page: Page) -> bool:
        try:
            candidates = await page.evaluate(
                """() => {
                    const candidates = Array.from(document.querySelectorAll("button, [role='button'], .d-icon, svg"))
                        .map(node => node.closest("button, [role='button'], div, span") || node);
                    const unique = Array.from(new Set(candidates));
                    const visible = unique.filter(node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height) return false;
                        if (style.visibility === "hidden" || style.display === "none") return false;
                        if (Number(style.opacity || "1") < 0.1) return false;
                        // Long-article toolbar is near the top center/right.
                        return rect.y > 60 && rect.y < 220 && rect.x > 420 && rect.x < 980;
                    });

                    // The document-import icon is usually one of the rightmost toolbar buttons.
                    visible.sort((a, b) => b.getBoundingClientRect().x - a.getBoundingClientRect().x);
                    return visible.slice(0, 10).map(node => {
                        const rect = node.getBoundingClientRect();
                        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                    });
                }"""
            )
            for candidate in candidates or []:
                try:
                    await page.mouse.click(candidate["x"], candidate["y"])
                    logger.info("[xiaohongshu] clicked document import toolbar candidate")
                    if await self._wait_for_document_import_modal(page, timeout_ms=3000):
                        return True
                except Exception:
                    continue
        except Exception as exc:
            logger.debug(f"[xiaohongshu] toolbar document import scan failed: {exc}")
        return False

    async def _wait_for_document_import_modal(self, page: Page, timeout_ms: int = 10000) -> bool:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            if await self._has_document_import_modal(page):
                return True
            await page.wait_for_timeout(500)
        return False

    async def _find_document_import_file_input(self, page: Page) -> Optional[Locator]:
        file_inputs = page.locator('input[type="file"]')
        count = await file_inputs.count()
        for index in range(count):
            candidate = file_inputs.nth(index)
            try:
                accept = ((await candidate.get_attribute("accept")) or "").lower()
                if any(ext in accept for ext in [".md", ".txt", ".docx", "text"]):
                    return candidate
            except Exception:
                continue

        if count > 0:
            return file_inputs.nth(count - 1)
        return None

    async def _wait_for_markdown_import_done(self, page: Page, timeout_ms: int = 90000) -> bool:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            if await self._has_long_article_editor(page) and not await self._has_document_import_modal(page):
                await page.wait_for_timeout(2000)
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _download_fallback_image(self, keyword: str, headers: Dict[str, str]) -> Optional[str]:
        encoded = urllib.parse.quote(f"{keyword} business technology article cover")
        seed = random.randint(1, 100000)
        urls = [
            f"https://image.pollinations.ai/prompt/{encoded}%20{seed}?width=1080&height=1440&nologo=true",
            f"https://picsum.photos/1080/1440?random={seed}",
        ]
        async with httpx.AsyncClient(headers=headers, verify=False, follow_redirects=True, timeout=30.0) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    if response.status_code == 200 and len(response.content) > 1000:
                        path = os.path.join(tempfile.gettempdir(), f"xhs_fallback_{random.randint(10000, 99999)}.jpg")
                        with open(path, "wb") as file:
                            file.write(response.content)
                        logger.warning("[xiaohongshu] using fallback image because article images were unavailable")
                        return path
                except Exception as exc:
                    logger.warning(f"[xiaohongshu] fallback image download failed: {exc}")
        return None

    def _image_suffix(self, content_type: str, url: str) -> str:
        if "png" in content_type:
            return ".png"
        if "webp" in content_type:
            return ".webp"
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            return ext
        return ".jpg"

    async def _select_long_article(self, page: Page) -> bool:
        if await self._has_long_article_editor(page):
            return True

        if not await self._click_creator_tab(page, ["写长文", "长文"]):
            if not await self._click_visible_text(page, ["写长文", "长文"]):
                await self._click_text_by_dom(page, ["写长文", "长文"])
        await self._wait_for_long_article_home(page)

        if await self._has_long_article_editor(page):
            return True

        if not await self._click_new_long_article(page):
            return False

        return await self._wait_for_long_article_editor(page)

    async def _wait_for_long_article_home(self, page: Page, timeout_ms: int = 30000) -> bool:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            if await self._has_long_article_editor(page):
                return True
            if await self._has_long_article_home(page):
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _wait_for_long_article_editor(self, page: Page, timeout_ms: int = 60000) -> bool:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            if await self._has_long_article_editor(page):
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _has_long_article_home(self, page: Page) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const bodyText = document.body.innerText || "";
                        return bodyText.includes("新的创作") || bodyText.includes("新建长文合集");
                    }"""
                )
            )
        except Exception:
            return False

    async def _click_new_long_article(self, page: Page) -> bool:
        texts = ["新的创作", "新建长文合集", "新创作", "开始创作", "立即创作"]
        for _ in range(20):
            if await self._click_main_button_by_text(page, texts, exclude_texts=["发布笔记"]):
                logger.info("[xiaohongshu] clicked new long-article creation")
                await self._wait_after_button_click(page)
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _click_creator_tab(self, page: Page, texts: List[str]) -> bool:
        tab_selectors = [".creator-tab", "[class*='creator-tab']", "[role='tab']", "button", "a"]
        for text in texts:
            for selector in tab_selectors:
                try:
                    tabs = page.locator(selector).filter(has_text=text)
                    count = await tabs.count()
                    for index in range(count):
                        tab = tabs.nth(index)
                        if not await self._is_effectively_visible(tab):
                            continue
                        await tab.scroll_into_view_if_needed()
                        await tab.click(timeout=5000)
                        logger.info(f"[xiaohongshu] clicked creator tab: {text}")
                        return True
                except Exception:
                    continue

        try:
            box = await page.evaluate(
                """(texts) => {
                    const candidates = Array.from(document.querySelectorAll(".creator-tab, [class*='creator-tab'], [role='tab'], button, a"));
                    for (const node of candidates) {
                        const text = (node.innerText || node.textContent || "").trim();
                        if (!texts.some(label => text === label || text.includes(label))) continue;
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height || style.visibility === "hidden" || style.display === "none") continue;
                        if (node.getAttribute("aria-hidden") === "true") continue;
                        if (Number(style.opacity || "1") < 0.1) continue;
                        if (Number(style.zIndex || "0") < 0) continue;
                        if (rect.right < 0 || rect.bottom < 0 || rect.left > window.innerWidth || rect.top > window.innerHeight) continue;
                        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
                    }
                    return null;
                }""",
                texts,
            )
            if box:
                await page.mouse.click(box["x"], box["y"])
                logger.info("[xiaohongshu] clicked creator tab by coordinates")
                return True
        except Exception as exc:
            logger.debug(f"[xiaohongshu] creator tab coordinate click failed: {exc}")

        return False

    async def _is_effectively_visible(self, locator: Locator) -> bool:
        try:
            if not await locator.is_visible():
                return False
            return bool(
                await locator.evaluate(
                    """node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height) return false;
                        if (style.visibility === "hidden" || style.display === "none") return false;
                        if (node.getAttribute("aria-hidden") === "true") return false;
                        if (Number(style.opacity || "1") < 0.1) return false;
                        if (Number(style.zIndex || "0") < 0) return false;
                        if (rect.right < 0 || rect.bottom < 0 || rect.left > window.innerWidth || rect.top > window.innerHeight) return false;
                        return true;
                    }"""
                )
            )
        except Exception:
            return False

    async def _has_long_article_editor(self, page: Page) -> bool:
        for selector in self._title_selectors() + self._content_selectors():
            try:
                field = page.locator(selector).first
                if await field.count() > 0 and await field.is_visible():
                    return True
            except Exception:
                continue
        try:
            return bool(
                await page.evaluate(
                    """() => {
                        const bodyText = document.body.innerText || "";
                        const hasEditorAction = bodyText.includes("一键排版") || bodyText.includes("暂存离开");
                        const hasEditable = document.querySelector('[contenteditable="true"], textarea, input[placeholder*="标题"], textarea[placeholder*="正文"]');
                        return Boolean(hasEditorAction && hasEditable);
                    }"""
                )
            )
        except Exception:
            pass
        return False

    async def _click_visible_text(self, page: Page, texts: List[str]) -> bool:
        for text in texts:
            try:
                target = page.get_by_text(text, exact=True).first
                if await target.count() > 0 and await target.is_visible():
                    await target.click(timeout=3000)
                    logger.info(f"[xiaohongshu] clicked visible text: {text}")
                    return True
            except Exception:
                continue
            try:
                target = page.get_by_text(text, exact=False).first
                if await target.count() > 0 and await target.is_visible():
                    await target.click(timeout=3000)
                    logger.info(f"[xiaohongshu] clicked visible partial text: {text}")
                    return True
            except Exception:
                continue
        return False

    async def _click_text_by_dom(self, page: Page, texts: List[str]) -> bool:
        try:
            return bool(
                await page.evaluate(
                    """(texts) => {
                        const nodes = Array.from(document.querySelectorAll("button, div, span, a"));
                        for (const node of nodes) {
                            const text = (node.innerText || node.textContent || "").trim();
                            if (!texts.some(label => text === label || text.includes(label))) continue;
                            const clickable = node.closest(".creator-tab, [class*='creator-tab'], button, a, [role='tab'], [role='button']") || node;
                            clickable.click();
                            return true;
                        }
                        return false;
                    }""",
                    texts,
                )
            )
        except Exception as exc:
            logger.debug(f"[xiaohongshu] DOM text click failed: {exc}")
            return False

    async def _select_image_note(self, page: Page) -> bool:
        if await self._has_image_file_input(page):
            return True

        text_candidates = ["上传图文", "图文", "发布图文"]
        for text in text_candidates:
            try:
                target = page.get_by_text(text, exact=True).first
                if await target.count() > 0 and await target.is_visible():
                    await target.click(timeout=3000)
                    await page.wait_for_timeout(1500)
                    logger.info(f"[xiaohongshu] selected image-note mode by text: {text}")
                    if await self._has_image_file_input(page):
                        return True
            except Exception:
                continue

        try:
            clicked = await page.evaluate(
                """() => {
                    const labels = ["上传图文", "图文", "发布图文"];
                    const nodes = Array.from(document.querySelectorAll("button, div, span, a"));
                    for (const node of nodes) {
                        const text = (node.innerText || node.textContent || "").trim();
                        if (!labels.some(label => text === label || text.includes(label))) continue;
                        const clickable = node.closest(".creator-tab, [class*='creator-tab'], button, a, [role='tab'], [role='button']") || node;
                        clickable.click();
                        return true;
                    }
                    return false;
                }"""
            )
            if clicked:
                await page.wait_for_timeout(1800)
                if await self._has_image_file_input(page):
                    logger.info("[xiaohongshu] selected image-note mode by DOM text fallback")
                    return True
        except Exception as exc:
            logger.debug(f"[xiaohongshu] DOM fallback failed when selecting image-note mode: {exc}")

        return await self._has_image_file_input(page)

    async def _upload_images(self, page: Page, image_paths: List[str]) -> bool:
        await page.wait_for_timeout(1000)

        target = await self._find_image_file_input(page)
        if not target:
            target = await self._open_editor_image_upload(page)
            if target:
                try:
                    await target.set_files(image_paths[: self.MAX_IMAGES])
                    await self._wait_for_upload_settle(page)
                    return True
                except Exception as exc:
                    logger.warning(f"[xiaohongshu] file chooser image upload failed: {exc}")
            return False

        try:
            await target.set_input_files(image_paths[: self.MAX_IMAGES])
            await self._wait_for_upload_settle(page)
            logger.info(f"[xiaohongshu] uploaded {len(image_paths[: self.MAX_IMAGES])} image(s)")
            return True
        except Exception as exc:
            logger.warning(f"[xiaohongshu] set_input_files failed: {exc}")
            return False

    async def _open_editor_image_upload(self, page: Page):
        toolbar_texts = ["图片", "上传图片", "选择图片", "插入图片"]
        for text in toolbar_texts:
            try:
                button = page.get_by_text(text, exact=False).first
                if await button.count() > 0 and await button.is_visible():
                    async with page.expect_file_chooser(timeout=5000) as chooser_info:
                        await button.click()
                    return await chooser_info.value
            except Exception:
                continue

        try:
            image_buttons = page.locator('button:has(svg), [role="button"]:has(svg)')
            count = await image_buttons.count()
            for index in range(count):
                button = image_buttons.nth(index)
                try:
                    label = " ".join(
                        filter(
                            None,
                            [
                                await button.get_attribute("aria-label"),
                                await button.get_attribute("title"),
                                await button.inner_text(),
                            ],
                        )
                    )
                    if label and not any(keyword in label for keyword in toolbar_texts):
                        continue
                    async with page.expect_file_chooser(timeout=3000) as chooser_info:
                        await button.click()
                    return await chooser_info.value
                except Exception:
                    continue
        except Exception:
            pass

        return None

    async def _has_image_file_input(self, page: Page) -> bool:
        return await self._find_image_file_input(page) is not None

    async def _find_image_file_input(self, page: Page) -> Optional[Locator]:
        file_inputs = page.locator('input[type="file"]')
        count = await file_inputs.count()
        for index in range(count):
            candidate = file_inputs.nth(index)
            accept = ""
            try:
                accept = (await candidate.get_attribute("accept")) or ""
            except Exception:
                pass
            normalized = accept.lower()
            if "image" in normalized:
                return candidate
        return None

    async def _wait_for_upload_settle(self, page: Page) -> None:
        await page.wait_for_timeout(5000)
        for _ in range(24):
            if await self._has_uploading_marker(page):
                await page.wait_for_timeout(1000)
                continue
            await page.wait_for_timeout(1500)
            return

    async def _has_uploading_marker(self, page: Page) -> bool:
        markers = ["上传中", "处理中", "加载中", "正在上传"]
        for marker in markers:
            try:
                locator = page.get_by_text(marker, exact=False).first
                if await locator.count() > 0 and await locator.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _title_selectors(self) -> List[str]:
        return [
            'input[placeholder*="输入标题"]',
            'input[placeholder*="填写标题"]',
            'input[placeholder*="标题"]',
            'textarea[placeholder*="输入标题"]',
            'textarea[placeholder*="标题"]',
            'input.max-title',
            ".title-input input",
            ".titleInput input",
            ".title textarea",
            ".title input",
        ]

    def _content_selectors(self) -> List[str]:
        return [
            'textarea[placeholder*="输入正文"]',
            'textarea[placeholder*="添加正文"]',
            'textarea[placeholder*="正文"]',
            'textarea[placeholder*="分享"]',
            'textarea[placeholder*="描述"]',
            'div[contenteditable="true"]',
            ".ql-editor",
            ".ProseMirror",
            ".editor-content",
            ".article-editor",
            ".note-content textarea",
        ]

    async def _fill_text_field(self, page: Page, selectors: List[str], text: str, timeout_ms: int = 60000) -> bool:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            for selector in selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() == 0 or not await field.is_visible():
                        continue
                    await field.scroll_into_view_if_needed()
                    tag_name = (await field.evaluate("el => el.tagName.toLowerCase()")).lower()
                    await field.click()
                    if tag_name in {"input", "textarea"}:
                        await field.fill("")
                        await field.fill(text)
                    else:
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        await self._paste_text(page, text)
                    await page.wait_for_timeout(500)
                    return True
                except Exception as exc:
                    logger.debug(f"[xiaohongshu] fill selector failed {selector}: {exc}")
                    continue
            await page.wait_for_timeout(1000)
        return False

    async def _fill_content_blocks(
        self,
        page: Page,
        blocks: List[Dict[str, str]],
        temp_files: List[str],
        timeout_ms: int = 60000,
    ) -> bool:
        field = await self._find_text_field(page, self._content_selectors(), timeout_ms=timeout_ms)
        if not field:
            return False

        await field.scroll_into_view_if_needed()
        await field.click()
        tag_name = (await field.evaluate("el => el.tagName.toLowerCase()")).lower()
        if tag_name in {"input", "textarea"}:
            text_only = "\n\n".join(block["value"] for block in blocks if block["type"] == "text")
            await field.fill("")
            await field.fill(text_only)
            return True

        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(500)

        image_index = 0
        for block in blocks:
            if block["type"] == "text":
                value = block["value"].strip()
                if value:
                    await self._paste_text(page, f"{value}\n\n")
                    await page.wait_for_timeout(300)
                continue

            if block["type"] == "image":
                image_index += 1
                image_path = await self._download_single_article_image(block["value"], image_index)
                if not image_path:
                    logger.warning(f"[xiaohongshu] skip unavailable inline image: {block['value']}")
                    continue
                temp_files.append(image_path)
                uploaded = await self._upload_images(page, [image_path])
                if uploaded:
                    await page.wait_for_timeout(800)
                    try:
                        await field.click()
                        await page.keyboard.press("End")
                    except Exception:
                        pass
                else:
                    logger.warning(f"[xiaohongshu] inline image upload failed: {image_path}")

        return True

    async def _find_text_field(
        self,
        page: Page,
        selectors: List[str],
        timeout_ms: int = 60000,
    ) -> Optional[Locator]:
        deadline = datetime.now().timestamp() + timeout_ms / 1000
        while datetime.now().timestamp() < deadline:
            for selector in selectors:
                try:
                    field = page.locator(selector).first
                    if await field.count() > 0 and await field.is_visible():
                        return field
                except Exception:
                    continue
            await page.wait_for_timeout(1000)
        return None

    async def _paste_text(self, page: Page, text: str) -> None:
        await page.evaluate(
            """(text) => {
                const target = document.activeElement;
                const data = new DataTransfer();
                data.setData("text/plain", text);
                const event = new ClipboardEvent("paste", { clipboardData: data, bubbles: true });
                target.dispatchEvent(event);
            }""",
            text,
        )

    async def _try_declare_ai_content(self, page: Page) -> None:
        candidates = ["AI辅助创作", "AI生成", "人工智能生成", "含AI"]
        for text in candidates:
            try:
                target = page.get_by_text(text, exact=False).first
                if await target.count() > 0 and await target.is_visible():
                    await target.click(timeout=3000)
                    logger.info(f"[xiaohongshu] clicked AI declaration option: {text}")
                    return
            except Exception:
                continue

    async def _click_one_key_layout(self, page: Page) -> bool:
        clicked = False
        for _ in range(60):
            clicked = await self._click_main_button_by_text(page, ["一键排版"], exclude_texts=["暂存", "离开", "发布"])
            if clicked:
                break
            await page.wait_for_timeout(1000)
        if not clicked:
            return False

        logger.info("[xiaohongshu] clicked one-key layout")
        await self._wait_after_button_click(page)
        return True

    async def _click_layout_next(self, page: Page) -> bool:
        for _ in range(90):
            if await self._click_main_button_by_text(page, ["下一步"], exclude_texts=["上一步", "发布笔记"]):
                logger.info("[xiaohongshu] clicked layout next")
                await self._wait_after_button_click(page)
                return True
            if await self._has_one_key_publish_button(page):
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _click_one_key_publish(self, page: Page) -> bool:
        await self._prepare_browser_permissions(page)
        publish_texts = ["一键发布", "发布"]
        for _ in range(90):
            await self._prepare_browser_permissions(page)
            if await self._click_main_button_by_text(page, ["下一步"], exclude_texts=["上一步", "发布笔记"]):
                logger.info("[xiaohongshu] clicked extra publish-step next")
                await self._wait_after_button_click(page)
                continue
            if await self._click_main_button_by_text(page, publish_texts, exclude_texts=["发布笔记", "暂存", "离开", "排版"]):
                logger.info("[xiaohongshu] clicked one-key publish")
                await self._click_confirm_if_needed(page)
                await self._wait_after_button_click(page)
                return True
            if await self._click_submit_button_by_class(page):
                logger.info("[xiaohongshu] clicked final submit button")
                await self._click_confirm_if_needed(page)
                await self._wait_after_button_click(page)
                return True
            if await self._click_bottom_publish_by_dom(page):
                logger.info("[xiaohongshu] clicked bottom publish button")
                await self._click_confirm_if_needed(page)
                await self._wait_after_button_click(page)
                return True
            await page.wait_for_timeout(1000)
        return False

    async def _click_submit_button_by_class(self, page: Page) -> bool:
        if await self._click_xhs_publish_component(page):
            return True

        selectors = [
            "xhs-publish-btn",
            "button.submit",
            ".custom-button.submit",
            "button[class*='submit']",
            "button[class*='publish']",
        ]
        for selector in selectors:
            try:
                buttons = page.locator(selector)
                count = await buttons.count()
                for index in range(count):
                    button = buttons.nth(index)
                    if (
                        await self._button_text_allowed(button, ["发布笔记", "暂存", "离开", "排版", "下一步"])
                        and await self._is_clickable(button)
                        and await self._is_in_main_publish_area(button)
                    ):
                        await button.scroll_into_view_if_needed()
                        await button.click(timeout=5000)
                        return True
            except Exception:
                continue
        return False

    async def _click_xhs_publish_component(self, page: Page) -> bool:
        try:
            clicked = await page.evaluate(
                """() => {
                    const candidates = Array.from(document.querySelectorAll("xhs-publish-btn"));
                    for (const node of candidates) {
                        const submitText = node.getAttribute("submit-text") || "";
                        const disabled = node.getAttribute("submit-disabled");
                        if (submitText && !submitText.includes("发布")) continue;
                        if (disabled === "true") continue;

                        const shadowButton = node.shadowRoot && Array.from(node.shadowRoot.querySelectorAll("button, [role='button']"))
                            .find(btn => ((btn.innerText || btn.textContent || "").trim()).includes("发布"));
                        if (shadowButton) {
                            shadowButton.click();
                            return true;
                        }

                        const rect = node.getBoundingClientRect();
                        if (!rect.width || !rect.height) continue;
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        const target = document.elementFromPoint(x, y);
                        if (target) {
                            target.click();
                            return true;
                        }
                    }
                    return false;
                }"""
            )
            return bool(clicked)
        except Exception as exc:
            logger.debug(f"[xiaohongshu] xhs-publish-btn click failed: {exc}")
            return False

    async def _has_one_key_publish_button(self, page: Page) -> bool:
        try:
            body_text = await page.locator("body").inner_text(timeout=3000)
            return "一键发布" in body_text
        except Exception:
            return False

    async def _click_main_button_by_text(
        self,
        page: Page,
        texts: List[str],
        exclude_texts: Optional[List[str]] = None,
    ) -> bool:
        exclude_texts = exclude_texts or []

        for text in texts:
            exact_pattern = re.compile(rf"^\s*{re.escape(text)}\s*$")
            partial_pattern = re.compile(re.escape(text))
            for pattern in [exact_pattern, partial_pattern]:
                try:
                    buttons = page.get_by_role("button", name=pattern)
                    count = await buttons.count()
                    for index in range(count):
                        button = buttons.nth(index)
                        if not await self._button_text_allowed(button, exclude_texts):
                            continue
                        if await self._is_clickable(button) and await self._is_in_main_publish_area(button):
                            await button.scroll_into_view_if_needed()
                            await button.click(timeout=5000)
                            logger.info(f"[xiaohongshu] clicked button by role: {text}")
                            return True
                except Exception:
                    continue

                try:
                    button = page.locator(f'button:has-text("{text}")').first
                    if (
                        await self._button_text_allowed(button, exclude_texts)
                        and await self._is_clickable(button)
                        and await self._is_in_main_publish_area(button)
                    ):
                        await button.scroll_into_view_if_needed()
                        await button.click(timeout=5000)
                        logger.info(f"[xiaohongshu] clicked button selector: {text}")
                        return True
                except Exception:
                    continue

        return await self._click_main_button_by_dom(page, texts, exclude_texts)

    async def _click_main_button_by_dom(self, page: Page, texts: List[str], exclude_texts: List[str]) -> bool:
        try:
            clicked = await page.evaluate(
                """({texts, excludeTexts}) => {
                    const nodes = Array.from(document.querySelectorAll("button, [role='button'], div, span, xhs-publish-btn"));
                    for (const node of nodes) {
                        const text = (node.innerText || node.textContent || "").trim();
                        if (!texts.some(label => text === label || text.includes(label))) continue;
                        if (excludeTexts.some(label => text.includes(label))) continue;
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height || style.visibility === "hidden" || style.display === "none") continue;
                        if (node.getAttribute("aria-hidden") === "true") continue;
                        if (Number(style.opacity || "1") < 0.1) continue;
                        if (Number(style.zIndex || "0") < 0) continue;
                        if (rect.x <= 220) continue;
                        if (node.disabled || node.getAttribute("aria-disabled") === "true") continue;
                        const clickable = node.closest("button, [role='button'], xhs-publish-btn") || node;
                        clickable.click();
                        return true;
                    }
                    return false;
                }""",
                {"texts": texts, "excludeTexts": exclude_texts},
            )
            return bool(clicked)
        except Exception as exc:
            logger.debug(f"[xiaohongshu] DOM main button click failed: {exc}")
            return False

    async def _click_bottom_publish_by_dom(self, page: Page) -> bool:
        try:
            clicked = await page.evaluate(
                """() => {
                    const nodes = Array.from(document.querySelectorAll("button, [role='button'], div, span, xhs-publish-btn"));
                    const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
                    for (const node of nodes) {
                        const text = (node.innerText || node.textContent || node.getAttribute("submit-text") || "").trim();
                        if (text !== "发布" && !text.includes("发布")) continue;
                        if (text.includes("发布笔记") || text.includes("定时发布")) continue;
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height || style.visibility === "hidden" || style.display === "none") continue;
                        if (rect.x <= 220 || rect.y < viewportHeight * 0.55) continue;
                        if (node.getAttribute("aria-hidden") === "true") continue;
                        if (node.disabled || node.getAttribute("aria-disabled") === "true" || node.getAttribute("submit-disabled") === "true") continue;
                        const clickable = node.closest("button, [role='button'], xhs-publish-btn") || node;
                        clickable.click();
                        return true;
                    }
                    return false;
                }"""
            )
            return bool(clicked)
        except Exception as exc:
            logger.debug(f"[xiaohongshu] bottom publish DOM click failed: {exc}")
            return False

    async def _button_text_allowed(self, locator: Locator, exclude_texts: List[str]) -> bool:
        try:
            if await locator.count() == 0:
                return False
            text = (await locator.inner_text()).strip()
            return not any(excluded in text for excluded in exclude_texts)
        except Exception:
            return False

    async def _wait_after_button_click(self, page: Page) -> None:
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass
        await page.wait_for_timeout(3000)

    async def _is_clickable(self, locator: Locator) -> bool:
        try:
            if await locator.count() == 0 or not await locator.is_visible():
                return False
            disabled = await locator.get_attribute("disabled")
            aria_disabled = await locator.get_attribute("aria-disabled")
            class_name = (await locator.get_attribute("class")) or ""
            return disabled is None and aria_disabled != "true" and "disabled" not in class_name.lower()
        except Exception:
            return False

    async def _is_in_main_publish_area(self, locator: Locator) -> bool:
        try:
            box = await locator.bounding_box()
            if not box:
                return True
            return box["x"] > 220
        except Exception:
            return True

    async def _click_confirm_if_needed(self, page: Page) -> None:
        await page.wait_for_timeout(1000)
        for text in ["确定", "确认", "继续发布", "我知道了"]:
            try:
                button = page.get_by_role("button", name=re.compile(text)).first
                if await self._is_clickable(button):
                    await button.click(timeout=3000)
                    await page.wait_for_timeout(800)
                    return
            except Exception:
                continue

    async def _wait_for_publish_result(self, page: Page) -> Dict[str, Any]:
        success_markers = ["发布成功", "提交成功", "已发布", "发布完成"]
        error_markers = ["发布失败", "请上传", "请输入", "违规", "异常", "失败"]

        for _ in range(45):
            for marker in success_markers:
                try:
                    node = page.get_by_text(marker, exact=False).first
                    if await node.count() > 0 and await node.is_visible():
                        return {"success": True, "platform_url": page.url}
                except Exception:
                    continue

            for marker in error_markers:
                try:
                    node = page.get_by_text(marker, exact=False).first
                    if await node.count() > 0 and await node.is_visible():
                        text = await node.inner_text()
                        return {"success": False, "error_msg": f"小红书页面提示: {text}"}
                except Exception:
                    continue

            if "publish" not in page.url and "creator.xiaohongshu.com" in page.url:
                return {"success": True, "platform_url": page.url}

            await page.wait_for_timeout(1000)

        return await self._fail(page, "wait_result", "发布后未检测到成功提示或跳转，请检查小红书后台是否已生成草稿/笔记")

    async def _fail(self, page: Page, stage: str, message: str) -> Dict[str, Any]:
        debug_path = await self._save_debug_snapshot(page, stage)
        error = f"小红书发布失败[{stage}]: {message}"
        if debug_path:
            error = f"{error}; debug={debug_path}"
        logger.error(error)
        return {"success": False, "error_msg": error}

    async def _save_debug_snapshot(self, page: Page, stage: str) -> Optional[str]:
        try:
            debug_dir = Path("backend/debug/xiaohongshu")
            debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = debug_dir / f"{stage}_{stamp}"
            await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
            html = await page.content()
            base.with_suffix(".html").write_text(html, encoding="utf-8", errors="ignore")
            return str(base)
        except Exception as exc:
            logger.warning(f"[xiaohongshu] failed to save debug snapshot: {exc}")
            return None


XIAOHONGSHU_CONFIG = {
    "name": "小红书",
    "publish_url": "https://creator.xiaohongshu.com/publish/publish",
    "color": "#FF2442",
}
registry.register("xiaohongshu", XiaohongshuPublisher("xiaohongshu", XIAOHONGSHU_CONFIG))
