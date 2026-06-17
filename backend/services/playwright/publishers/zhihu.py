# -*- coding: utf-8 -*-
"""
知乎发布适配器 - v4.5 格式优化版

修复内容:
1. 【重要】HTML标签清理 + 转换为markdown格式
2. 【重要】保留加粗：<strong> → **粗体**
3. 【重要】标题转markdown：<h3> → ###
4. 【优化】表格智能处理：转为markdown表格格式
5. 【优化】段落紧凑化：减少多余空行
6. 【修复】图片提取：从HTML <img>标签提取
7. 【修复】本地图片处理：从后端获取
"""

import asyncio
import re
import os
import httpx
import tempfile
import base64
import random
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, List
from playwright.async_api import Page
from loguru import logger

from .base import BasePublisher, registry


class ZhihuPublisher(BasePublisher):
    # 发布历史记录（用于频率限制）
    _publish_history = []

    # 频率限制配置
    MAX_PER_HOUR = 3  # 每小时最多发布次数
    MAX_PER_DAY = 10  # 每天最多发布次数
    MIN_INTERVAL_MINUTES = 10  # 两次发布之间的最小间隔（分钟）

    def _check_rate_limit(self) -> Dict[str, Any]:
        """
        检查发布频率限制

        Returns:
            dict: {'allowed': bool, 'reason': str}
        """
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        # 清理超过24天的历史记录（避免内存泄漏）
        self._publish_history = [t for t in self._publish_history if t > now - timedelta(days=7)]

        # 检查过去1小时的发布次数
        count_last_hour = len([t for t in self._publish_history if t > one_hour_ago])
        if count_last_hour >= self.MAX_PER_HOUR:
            return {
                "allowed": False,
                "reason": f"过去1小时已发布{count_last_hour}次，超过限制{self.MAX_PER_HOUR}次/小时",
            }

        # 检查过去24小时的发布次数
        count_last_day = len([t for t in self._publish_history if t > one_day_ago])
        if count_last_day >= self.MAX_PER_DAY:
            return {"allowed": False, "reason": f"过去24小时已发布{count_last_day}次，超过限制{self.MAX_PER_DAY}次/天"}

        # 检查距离上次发布的间隔
        if self._publish_history:
            last_publish_time = self._publish_history[-1]
            minutes_since_last = (now - last_publish_time).total_seconds() / 60
            if minutes_since_last < self.MIN_INTERVAL_MINUTES:
                return {
                    "allowed": False,
                    "reason": f"距离上次发布仅{int(minutes_since_last)}分钟，需要至少{self.MIN_INTERVAL_MINUTES}分钟间隔",
                }

        return {"allowed": True, "reason": "频率检查通过"}

    def _extract_image_urls_from_html(self, html_content: str) -> List[str]:
        """
        从HTML内容中提取图片URL

        匹配 <img src="/static/uploads/xxx.jpg"> 格式的本地图片
        也匹配外部http/https图片
        """
        return self.extract_image_urls(html_content)

    def _deep_clean_content(self, text: str) -> str:
        """
        清理正文内容 - v4.5 优化版

        清理步骤：
        1. 保留加粗效果：<strong> → **，<b> → **
        2. 标题转markdown：<h3> → ###
        3. 表格优化处理
        4. 段落紧凑化：减少空行
        """
        # 1. 移除markdown图片
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

        # 2. HTML strong/b 保留文本，不再转回 markdown，避免知乎原样显示 **
        text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"\1", text)
        text = re.sub(r"<b[^>]*>(.*?)</b>", r"\1", text)

        # 3. HTML 标题保留标题文本，不再转回 ###，避免知乎原样显示标题符号
        text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n\1\n\n", text)
        text = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n\n\1\n\n", text)
        text = re.sub(r"<h5[^>]*>(.*?)</h5>", r"\n\n\1\n\n", text)

        # 4. 【段落】p标签保留，但不要额外换行
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text)

        # 5. 【列表】优化列表格式
        text = re.sub(r"<ul[^>]*>|</ul>", "\n", text)
        text = re.sub(r"<ol[^>]*>|</ol>", "\n", text)
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", text)

        # 6. 【表格】智能处理表格
        # 先提取表格内容，再转换为markdown表格格式
        def convert_table(match):
            table_content = match.group(0)
            # 提取所有行
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_content, re.DOTALL)
            if not rows:
                return ""
            # 处理每行的单元格
            md_rows = []
            for i, row in enumerate(rows):
                cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
                # 清理单元格内容
                clean_cells = []
                for cell in cells:
                    # 移除内部HTML标签
                    clean_cell = re.sub(r"<[^>]+>", "", cell).strip()
                    clean_cells.append(clean_cell)
                if clean_cells:
                    md_rows.append("| " + " | ".join(clean_cells) + " |")
                    # 在第一行后添加分隔线
                    if i == 0:
                        md_rows.append("| " + " | ".join(["---"] * len(clean_cells)) + " |")
            return "\n\n" + "\n".join(md_rows) + "\n\n" if md_rows else "\n\n"

        text = re.sub(r"<table[^>]*>.*?</table>", convert_table, text, flags=re.DOTALL)

        # 7. 【其他标签清理】
        text = re.sub(r"<br\s*/?>|<br>", "\n", text)
        text = re.sub(r"<div[^>]*>|</div>", "", text)
        text = re.sub(r"<span[^>]*>|</span>", "", text)
        text = re.sub(r"<img[^>]+>", "", text)
        text = re.sub(r"<tbody[^>]*>|</tbody>", "", text)
        text = re.sub(r"<thead[^>]*>|</thead>", "", text)
        text = re.sub(r"<[^>]+>", "", text)  # 移除所有剩余HTML标签

        # 8. 【清理多余空行】但保留段落间距
        lines = text.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_empty:
                    cleaned_lines.append("")
                    prev_empty = True
            else:
                cleaned_lines.append(stripped)
                prev_empty = False

        text = "\n".join(cleaned_lines)

        return self.markdown_to_plain_text(text)

    async def publish(self, page: Page, article: Any, account: Any, declare_ai_content: bool = True) -> Dict[str, Any]:
        temp_files = []
        try:
            logger.info("🚀 开始知乎发布 (v4.5 格式优化版)...")

            # 0. 【新增】检查发布频率限制
            rate_limit_check = self._check_rate_limit()
            if not rate_limit_check["allowed"]:
                logger.warning(f"⚠️ 发布频率限制: {rate_limit_check['reason']}")
                return {"success": False, "error_msg": f"发布频率限制: {rate_limit_check['reason']}"}
            logger.success(f"✅ 频率检查通过: {rate_limit_check['reason']}")

            # 1. 导航
            await page.goto(self.config["publish_url"], wait_until="networkidle", timeout=60000)
            await asyncio.sleep(5)

            # 2. 【修复】从HTML中提取图片URL
            image_urls = self._extract_image_urls_from_html(article.content)
            logger.info(f"📷 从文章中提取到 {len(image_urls)} 张图片")

            # 3. 提取keyword用于生成默认图片（如果没有图片的话）
            keyword = article.title[:10] if article.title else "technology"

            # 4. 下载图片（本地图片从后端获取）
            downloaded_paths = await self._download_images(image_urls, keyword=keyword)
            temp_files.extend(downloaded_paths)

            # 5. 检查图片结果
            if not downloaded_paths:
                logger.warning("⚠️ 无法获得任何图片，继续发布（无图模式）")
            else:
                logger.success(f"✅ 图片准备完成: {len(downloaded_paths)} 张")

            # 6. 按 Markdown 原始顺序构建发布块，避免图片被放到错误位置
            content_blocks = self._build_content_blocks(article.content, downloaded_paths)
            text_length = sum(len(block["content"]) for block in content_blocks if block["type"] == "text")
            logger.info(f"📝 内容已拆分为 {len(content_blocks)} 个发布块，文本长度: {text_length} 字符")

            # 7. 填充标题
            await self._fill_title(page, article.title)

            # 8. 按顺序填充正文和图片
            await self._fill_content_blocks(page, content_blocks)

            # 9. 【条件】根据参数决定是否设置 AI 声明
            if declare_ai_content:
                await self._set_ai_declaration(page)
            else:
                logger.info("⏭️ 跳过AI声明设置")

            # 10. 发布流程
            topic_word = getattr(article, "keyword_text", article.title[:4])
            if not await self._handle_publish_process(page, topic_word):
                return {"success": False, "error_msg": "发布确认环节失败"}

            return await self._wait_for_publish_result(page)

        except Exception as e:
            logger.exception(f"❌ 知乎脚本致命故障: {str(e)}")
            return {"success": False, "error_msg": str(e)}
        finally:
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass

    async def _download_images(self, urls: List[str], keyword: str = "technology") -> List[str]:
        """
        下载图片，如果失败则使用AI生成默认图片

        v4.4 修复：
        - 正确处理本地图片路径 (/static/uploads/...)
        - 从后端 http://localhost:8001 获取本地图片

        Args:
            urls: 图片URL列表
            keyword: 关键词，用于生成默认图片

        Returns:
            下载的图片路径列表（至少1张）
        """
        paths = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # 后端地址（用于获取本地图片）
        backend_base_url = "http://localhost:8001"

        # 第一阶段：尝试下载原始图片
        async with httpx.AsyncClient(headers=headers, verify=False, follow_redirects=True, timeout=30.0) as client:
            for i, original_url in enumerate(urls[:3]):
                url = original_url

                # 处理本地图片路径
                if original_url.startswith("/static/uploads/"):
                    # 从后端获取本地图片
                    url = f"{backend_base_url}{original_url}"
                    logger.info(f"📷 本地图片，从后端获取: {url}")
                elif original_url.startswith("/"):
                    logger.warning(f"⚠️ 跳过其他本地路径: {original_url}")
                    continue

                for attempt in range(2):
                    try:
                        resp = await client.get(url, timeout=30.0)
                        if resp.status_code == 200:
                            if len(resp.content) < 1000:
                                logger.warning(f"⚠️ 图片 {i + 1} 太小，跳过")
                                continue
                            tmp_path = os.path.join(tempfile.gettempdir(), f"zh_v44_{random.randint(1000, 9999)}.jpg")
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            paths.append(tmp_path)
                            logger.success(f"✅ 图片 {i + 1} 下载成功: {len(resp.content)} bytes")
                            break
                        else:
                            logger.warning(f"⚠️ 图片 {i + 1} HTTP状态码: {resp.status_code}")
                    except Exception as e:
                        logger.warning(f"⚠️ 图片 {i + 1} 下载失败 (尝试 {attempt + 1}/2): {e}")
                        pass

        # 第二阶段：如果没有图片，尝试备用图片来源
        if not paths:
            logger.warning("⚠️ 所有图片下载失败，尝试备用图片来源...")
            seed = random.randint(1, 1000)

            fallback_urls = []

            # 1. 尝试 pollinations.ai (AI生成图片)
            encoded_keyword = urllib.parse.quote(keyword)
            fallback_urls.append(
                f"https://image.pollinations.ai/prompt/{encoded_keyword}%20seed%20{seed}?width=1200&height=630&nologo=true"
            )

            # 2. 尝试 Picsum（随机图片）
            fallback_urls.append(f"https://picsum.photos/1200/630?random={seed}")

            # 依次尝试每个备用源
            for idx, fallback_url in enumerate(fallback_urls, 1):
                try:
                    logger.info(f"🔄 尝试备用源 {idx}/{len(fallback_urls)}: {fallback_url[:70]}...")
                    async with httpx.AsyncClient(
                        headers=headers, verify=False, follow_redirects=True, timeout=30.0
                    ) as client:
                        resp = await client.get(fallback_url)

                        if resp.status_code == 200 and len(resp.content) > 1000:
                            tmp_path = os.path.join(
                                tempfile.gettempdir(), f"zh_v44_fallback_{random.randint(1000, 9999)}.jpg"
                            )
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            paths.append(tmp_path)
                            logger.success(f"✅ 备用源 {idx} 成功: {len(resp.content)} bytes")
                            break
                        else:
                            logger.warning(
                                f"⚠️ 备用源 {idx} 失败: status={resp.status_code}, size={len(resp.content) if resp.content else 0}"
                            )
                except Exception as e:
                    logger.warning(f"⚠️ 备用源 {idx} 异常: {e}")

        logger.info(f"📊 最终获得 {len(paths)} 张图片")
        return paths

    def _build_content_blocks(self, content: str, image_paths: List[str]) -> List[Dict[str, str]]:
        """按 Markdown 图片位置拆成文本/图片块，尽量保持后台预览中的排版顺序。"""
        blocks: List[Dict[str, str]] = []
        image_index = 0
        last_end = 0

        image_pattern = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
        for match in image_pattern.finditer(content or ""):
            before = content[last_end : match.start()]
            clean_before = self.markdown_to_plain_text(before, drop_first_h1=not blocks)
            if clean_before:
                blocks.append({"type": "text", "content": clean_before})

            if image_index < len(image_paths):
                blocks.append({"type": "image", "content": image_paths[image_index]})
            image_index += 1
            last_end = match.end()

        after = (content or "")[last_end:]
        clean_after = self.markdown_to_plain_text(after, drop_first_h1=not blocks)
        if clean_after:
            blocks.append({"type": "text", "content": clean_after})

        while image_index < len(image_paths):
            blocks.append({"type": "image", "content": image_paths[image_index]})
            image_index += 1

        return blocks

    async def _handle_multi_image_upload(self, page: Page, paths: List[str]):
        """多图排版逻辑"""
        try:
            # Step 1: 上传封面（关键！必须有封面图）
            logger.info("🖼️ 正在设置文章封面...")
            cover_input = page.locator("input.UploadPicture-input").first
            if await cover_input.count() > 0:
                await cover_input.set_input_files(paths[0])
                logger.success(f"✅ 封面图文件已设置: {paths[0]}")
                await asyncio.sleep(5)  # 增加等待时间，确保上传完成

                # 验证封面图是否上传成功（检查是否有预览图）
                try:
                    cover_preview = page.locator(".UploadPicture-preview img, .UploadPicture-image").first
                    if await cover_preview.is_visible(timeout=3000):
                        logger.success("✅ 封面图上传成功（检测到预览图）")
                    else:
                        logger.warning("⚠️ 未检测到封面图预览，可能上传失败")
                except:
                    logger.warning("⚠️ 无法验证封面图上传状态")
            else:
                logger.error("❌ 找不到封面图上传输入框")
                return

            # Step 2: 遍历插入正文
            editor = page.locator(".public-DraftEditor-content").first
            await editor.click()

            for i, image_path in enumerate(paths):
                logger.info(f"📝 正在插入第 {i + 1}/{len(paths)} 张图片...")

                if i == 0:
                    await page.keyboard.press("Control+Home")
                    await page.keyboard.press("Enter")
                    await page.keyboard.press("ArrowUp")
                else:
                    for _ in range(4):
                        await page.keyboard.press("PageDown")
                        await asyncio.sleep(0.2)
                    await page.keyboard.press("Enter")

                await self._paste_image_via_js(page, image_path)
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"多图上传流程部分失败: {e}")

    async def _paste_image_via_js(self, page: Page, image_path: str):
        """剪贴板注入技术"""
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")

        await page.evaluate(
            """(data) => {
            const { b64 } = data;
            const byteCharacters = atob(b64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'image/jpeg' });
            const file = new File([blob], "auto_inserted.jpg", { type: 'image/jpeg' });

            const dt = new DataTransfer();
            dt.items.add(file);

            const editor = document.querySelector(".public-DraftEditor-content");
            const event = new ClipboardEvent("paste", {
                clipboardData: dt,
                bubbles: true,
                cancelable: true
            });
            editor.dispatchEvent(event);
        }""",
            {"b64": b64_data},
        )

    async def _fill_title(self, page: Page, title: str):
        sel = "input[placeholder*='标题'], .WriteIndex-titleInput textarea"
        await page.wait_for_selector(sel)
        await page.fill(sel, title)

    async def _fill_content_and_clean_ui(self, page: Page, content: str):
        editor = ".public-DraftEditor-content"
        await page.wait_for_selector(editor)
        await page.click(editor)

        await page.evaluate(
            """(text) => {
            const dt = new DataTransfer();
            dt.setData("text/plain", text);
            const ev = new ClipboardEvent("paste", { clipboardData: dt, bubbles: true });
            document.querySelector(".public-DraftEditor-content").dispatchEvent(ev);
        }""",
            content,
        )

        await asyncio.sleep(2)
        try:
            confirm = page.locator("button:has-text('确认并解析')").first
            if await confirm.is_visible(timeout=3000):
                await confirm.click()
        except:
            pass

    async def _fill_content_blocks(self, page: Page, blocks: List[Dict[str, str]]):
        editor = ".public-DraftEditor-content"
        await page.wait_for_selector(editor)
        await page.click(editor)

        for index, block in enumerate(blocks):
            if block["type"] == "text":
                await self._paste_text(page, block["content"])
            elif block["type"] == "image":
                await self._paste_image_via_js(page, block["content"])
                await asyncio.sleep(5)

            if index < len(blocks) - 1:
                await page.keyboard.press("Enter")
                await page.keyboard.press("Enter")
                await asyncio.sleep(0.2)

    async def _paste_text(self, page: Page, text: str):
        if not text:
            return

        await page.evaluate(
            """(text) => {
            const dt = new DataTransfer();
            dt.setData("text/plain", text);
            const ev = new ClipboardEvent("paste", { clipboardData: dt, bubbles: true });
            document.querySelector(".public-DraftEditor-content").dispatchEvent(ev);
        }""",
            text,
        )
        await asyncio.sleep(1)

    async def _set_ai_declaration(self, page: Page):
        """设置 AI 创作声明 (移植自 Upstream)"""
        try:
            logger.info("正在设置 AI 声明...")
            # 查找并点击 AI 助手按钮
            ai_btn = page.locator("button:has-text('AI助手'), .ToolbarButton:has-text('AI')").first
            if await ai_btn.is_visible(timeout=3000):
                await ai_btn.click()
                await asyncio.sleep(1)
                # 选择 AI 辅助创作
                option = page.locator("text=AI辅助创作, [role='menuitem']:has-text('AI')").first
                if await option.is_visible(timeout=2000):
                    await option.click()
                    logger.info("✅ 已勾选 AI 辅助创作声明")
        except:
            logger.warning("未找到 AI 声明入口，跳过此步")

    async def _handle_publish_process(self, page: Page, topic: str) -> bool:
        logger.info("📌 开始处理发布流程...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        try:
            add_topic = page.locator("button:has-text('添加话题')").first
            if await add_topic.is_visible(timeout=2000):
                await add_topic.click()
                logger.info("✅ 点击添加话题")

            topic_input = page.locator("input[placeholder*='话题']").first
            await topic_input.fill(topic)
            await asyncio.sleep(2)
            suggestion = page.locator(".Suggestion-item, .PublishPanel-suggestionItem").first
            if await suggestion.is_visible(timeout=2000):
                await suggestion.click()
                logger.info(f"✅ 选择话题: {topic}")
            else:
                await page.keyboard.press("Enter")
                logger.info(f"✅ 输入话题: {topic}")
        except Exception as e:
            logger.warning(f"⚠️ 话题添加失败（非致命）: {e}")

        # 发布流程：重复尝试直到不再是编辑页面
        max_attempts = 5
        for attempt in range(max_attempts):
            current_url = page.url
            is_edit_page = "/edit" in current_url or "write" in current_url

            logger.info(f"🔄 发布尝试 {attempt + 1}/{max_attempts}, 当前URL: {current_url}, 编辑页: {is_edit_page}")

            if is_edit_page:
                # 在编辑页面，点击发布按钮
                publish_btn_selectors = [
                    "button.PublishPanel-submitButton",
                    ".WriteIndex-publishButton",
                    "button:has-text('发布')",
                ]

                publish_btn = None
                for selector in publish_btn_selectors:
                    try:
                        btn = page.locator(selector).last
                        if await btn.is_visible(timeout=2000) and await btn.is_enabled():
                            publish_btn = btn
                            logger.info(f"✅ 找到发布按钮: {selector}")
                            break
                    except:
                        continue

                if not publish_btn:
                    logger.error(f"❌ 第{attempt + 1}次尝试：找不到可用的发布按钮")
                    await asyncio.sleep(3)
                    continue

                # 点击发布按钮
                await publish_btn.click(force=True)
                logger.info(f"✅ 第{attempt + 1}次点击发布按钮")
                await asyncio.sleep(2)  # 减少等待时间，快速检测限流警告

                # 【新增】检测限流警告（优先级最高！）
                try:
                    # 检查是否有alert弹窗（限流警告）
                    alert_locator = page.locator(
                        "generic:has-text('近期发布频率过高'), generic:has-text('请24小时后重试'), generic:has-text('发布频率过高')"
                    ).first
                    if await alert_locator.is_visible(timeout=2000):
                        error_text = await alert_locator.inner_text()
                        logger.error(f"❌ 检测到知乎限流警告: {error_text}")
                        return False  # 立即停止，不再重试
                except:
                    pass  # 没有限流警告，继续处理

                await asyncio.sleep(3)  # 额外等待，确保确认对话框出现

                # 处理确认弹窗（关键！）
                # 知乎的确认对话框会显示，需要点击其中的"发布"按钮
                handled_confirm = False

                # 等待确认对话框出现并查找其中的发布按钮
                try:
                    # 查找确认对话框中的发布按钮（通常是蓝色主按钮）
                    # 使用更精确的选择器：在可见的Button--primary中查找包含"发布"文字的
                    confirm_btn = page.locator("button.Button--primary:visible").filter(has_text="发布").first

                    if await confirm_btn.is_visible(timeout=3000):
                        await confirm_btn.click()
                        logger.info("✅ 点击确认对话框中的发布按钮")
                        handled_confirm = True
                        # 关键！增加等待时间，让页面有足够时间跳转
                        await asyncio.sleep(10)
                    else:
                        logger.warning(f"⚠️ 第{attempt + 1}次尝试：未找到确认对话框")
                except Exception as e:
                    logger.warning(f"⚠️ 第{attempt + 1}次尝试：处理确认对话框失败 - {e}")
                    # 如果找不到主按钮，尝试通用的发布按钮
                    try:
                        fallback_btn = page.locator("button:has-text('发布')").last
                        if await fallback_btn.is_visible(timeout=1000):
                            await fallback_btn.click()
                            logger.info("✅ 使用备用选择器点击发布按钮")
                            handled_confirm = True
                            await asyncio.sleep(10)
                    except:
                        pass

                if not handled_confirm:
                    logger.warning(f"⚠️ 第{attempt + 1}次尝试：未找到确认弹窗")

                # 等待页面响应
                await asyncio.sleep(5)

                # 检查是否还在编辑页面
                new_url = page.url
                is_still_edit = "/edit" in new_url or "write" in new_url
                logger.info(f"🔍 第{attempt + 1}次尝试后检查: URL={new_url}, 仍在编辑页={is_still_edit}")

                if not is_still_edit:
                    logger.success(f"🎉 第{attempt + 1}次尝试：已离开编辑页面，可能发布成功！")
                    return True
                else:
                    logger.warning(f"⚠️ 第{attempt + 1}次尝试：仍在编辑页面，继续尝试...")
                    await asyncio.sleep(3)
            else:
                logger.success("🎉 当前不在编辑页面，可能已经发布成功！")
                return True

        logger.error(f"❌ 发布失败：尝试{max_attempts}次后仍在编辑页面")
        return False

    async def _wait_for_publish_result(self, page: Page) -> Dict[str, Any]:
        logger.info("⏳ 等待发布结果...")
        for i in range(60):  # 增加到60秒
            current_url = page.url
            logger.debug(f"第{i + 1}秒，当前URL: {current_url}")

            # 检查URL中是否包含文章ID（/p/数字格式）
            # 编辑模式 /p/xxx/edit 也算发布成功，说明文章已创建
            if "/p/" in current_url and "/p/" in current_url.split("/edit")[0]:
                # 提取文章URL（去掉/edit）
                article_url = current_url.split("/edit")[0] if "/edit" in current_url else current_url
                logger.success(f"🎉 发布成功！文章URL: {article_url}")
                # 【新增】记录发布时间
                self._publish_history.append(datetime.now())
                logger.info(f"📊 已记录发布时间，当前历史记录数: {len(self._publish_history)}")
                return {"success": True, "platform_url": article_url}

            # 检查是否有成功提示
            try:
                success_msg = page.locator("text=发布成功, text=已发布, .Toast-success, .Message-success").first
                if await success_msg.is_visible(timeout=500):
                    logger.success("🎉 检测到发布成功提示")
                    # 再等一下跳转
                    await asyncio.sleep(3)
                    if "/p/" in page.url:
                        article_url = page.url.split("/edit")[0] if "/edit" in page.url else page.url
                        # 【新增】记录发布时间
                        self._publish_history.append(datetime.now())
                        logger.info(f"📊 已记录发布时间，当前历史记录数: {len(self._publish_history)}")
                        return {"success": True, "platform_url": article_url}
            except:
                pass

            await asyncio.sleep(1)

        # 即使超时，也检查是否在文章编辑页（说明已创建）
        logger.warning("⚠️ 检测超时，但可能已发布，检查最终URL...")
        if "/p/" in page.url:
            article_url = page.url.split("/edit")[0] if "/edit" in page.url else page.url
            logger.info(f"✅ 检测到文章页URL，认为发布成功: {article_url}")
            # 【新增】记录发布时间
            self._publish_history.append(datetime.now())
            logger.info(f"📊 已记录发布时间，当前历史记录数: {len(self._publish_history)}")
            return {"success": True, "platform_url": article_url}

        logger.error(f"❌ 发布超时，最终URL: {page.url}")
        return {"success": False, "error_msg": f"发布超时，最终URL: {page.url}"}


# 注册
ZHIHU_CONFIG = {
    "name": "知乎",
    "publish_url": "https://zhuanlan.zhihu.com/write",
    "color": "#0084FF",
    "version": "v4.5",
}
registry.register("zhihu", ZhihuPublisher("zhihu", ZHIHU_CONFIG))
