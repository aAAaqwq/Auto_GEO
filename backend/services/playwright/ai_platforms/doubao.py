# -*- coding: utf-8 -*-
"""
豆包AI检测器
用这个来检测豆包的收录情况！
"""

from typing import Dict, Any
from playwright.async_api import Page
import asyncio

from .base import AIPlatformChecker


class DoubaoChecker(AIPlatformChecker):
    """
    豆包AI检测器

    URL: https://www.doubao.com
    """

    async def navigate_to_page(self, page: Page) -> bool:
        """
        豆包平台导航 — 直接进入聊天页面，避免首页导航栏的"登录"按钮误判
        """
        try:
            # 直接访问聊天页，跳过首页的导航栏
            chat_url = "https://www.doubao.com/chat"
            self._log("info", f"正在导航到豆包聊天页: {chat_url}")

            await page.goto(chat_url, wait_until="domcontentloaded", timeout=60000)

            # 等待关键元素：输入框（已登录）或登录页（未登录）
            try:
                indicators = [
                    "textarea[placeholder*='输入']",
                    "textarea[placeholder*='发消息']",
                    "[contenteditable='true']",
                    "[data-testid*='input']",
                ]
                await self.wait_for_selector(page, indicators, timeout=15000)
                self._log("info", "豆包聊天页已就绪（检测到输入框）")
                return True
            except Exception:
                pass

            # 没找到输入框 → 检查是否被重定向到登录页
            current_url = page.url
            if "passport" in current_url or "login" in current_url.lower():
                self._log("warning", f"豆包重定向到登录页: {current_url}，需要手动登录")
                await asyncio.sleep(30)
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            else:
                self._log("info", f"豆包页面已加载: {current_url}")

            return True
        except Exception as e:
            self._log("error", f"豆包导航失败: {e}")
            return False

    SELECTORS = {
        "input_box": [
            "div[contenteditable='true']",
            "textarea[placeholder*='发消息']",
            "textarea[placeholder*='输入']",
            "textarea[data-testid*='input']",
            "[class*='ProseMirror']",  # 常见的富文本编辑器类名
            "[class*='editor']",
            "[role='textbox']",
        ],
        "submit_button": [
            "button[data-testid*='send']",
            "button[class*='send']",
            "[class*='submit']",
            "button[type='submit']",
        ],
        "new_chat": ["button[data-testid*='new-chat']", "[class*='new-chat']", "[href='/chat']"],
    }

    async def get_answer_content(self, page: Page, question: str) -> Dict[str, Any]:
        """
        豆包专用的回答提取逻辑 - 增强版
        绝不回退到全文抓取，而是通过DOM遍历寻找最佳候选
        """
        self._log("info", "使用豆包专用逻辑获取回答")

        # 1. 尝试标准选择器
        doubao_selectors = [
            "div[data-testid='message-card']",
            "div[class*='message-card']",
            "div[class*='message-item']",
            "div[class*='bubble-content']",
            "div[class*='markdown-body']",
        ]

        for selector in doubao_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    # 从后往前找，找到第一个符合条件的
                    for element in reversed(elements):
                        text = await element.inner_text()
                        if self._is_valid_answer(text, question):
                            return {
                                "success": True,
                                "answer": self._clean_text(text),
                                "selector": selector,
                                "length": len(text),
                            }
            except Exception:
                continue

        # 2. 如果标准选择器失败，进行智能DOM遍历
        # 查找所有文本长度足够的 div，然后通过位置和内容排除侧边栏
        self._log("info", "标准选择器失败，尝试智能DOM遍历")
        try:
            # 获取页面主要区域的文本块
            # 排除侧边栏常见的容器 class 或 id 关键词
            candidates = await page.evaluate("""() => {
                const results = [];
                const blacklist = ['sidebar', 'menu', 'nav', 'history', 'input', 'toolbar'];
                const divs = document.querySelectorAll('div');
                
                for (const div of divs) {
                    // 简单的可见性检查
                    if (div.offsetParent === null) continue;
                    
                    const text = div.innerText;
                    if (text.length < 50) continue;
                    
                    // 检查 class 是否包含黑名单词
                    const className = (div.className || '').toLowerCase();
                    if (blacklist.some(w => className.includes(w))) continue;
                    
                    results.push({
                        text: text,
                        length: text.length,
                        hasSidebarKeywords: text.includes('历史对话') || text.includes('新对话') || text.includes('帮我写作')
                    });
                }
                return results;
            }""")

            # 在 Python 端进行过滤和择优
            best_candidate = ""
            for item in candidates:
                text = item["text"]
                # 排除包含明显侧边栏关键词的块
                if item["hasSidebarKeywords"]:
                    continue

                # 排除包含大量换行的短文本块（可能是菜单列表）
                lines = text.split("\n")
                if len(lines) > 5:
                    avg_len = sum(len(l) for l in lines) / len(lines)
                    if avg_len < 20:  # 菜单项通常很短
                        continue

                if self._is_valid_answer(text, question):
                    # 这里的策略：我们想要最长的那个，且不是全页文本
                    # 通常回答是页面中第二长的块（第一长可能是 body）
                    # 但为了安全，如果这个块比当前最佳块长，且不超过 5000 字（避免选中整个 body），就选它
                    if len(text) > len(best_candidate) and len(text) < 5000:
                        best_candidate = text

            if best_candidate:
                return {
                    "success": True,
                    "answer": self._clean_text(best_candidate),
                    "selector": "smart-dom-traversal",
                    "length": len(best_candidate),
                }

        except Exception as e:
            self._log("warning", f"智能DOM遍历失败: {e}")

        self._log("warning", "豆包所有提取手段均失败")
        return {"success": False, "answer": "", "selector": None, "length": 0}

    def _is_valid_answer(self, text: str, question: str) -> bool:
        """检查文本是否为有效回答"""
        if not text or len(text) < 50:
            return False

        # 排除包含侧边栏关键词的文本
        sidebar_keywords = ["历史对话", "新对话", "帮我写作", "AI 创作", "云盘", "手机版"]
        if any(k in text[:100] for k in sidebar_keywords):  # 只检查开头
            return False

        # 排除纯问题复述
        if text.strip() == question.strip():
            return False

        return True

    def _clean_text(self, text: str) -> str:
        """清理回答文本"""
        # 移除底部的工具栏文本
        if "深度思考" in text and "PPT 生成" in text:
            # 尝试截断到工具栏之前
            # 这里简单处理，如果发现这些词出现在末尾，就切掉
            pass

        # 移除"内容由 AI 生成"
        text = text.replace("内容由 AI 生成", "")
        return text.strip()

    async def check(self, page: Page, question: str, keyword: str, company: str) -> Dict[str, Any]:
        """
        检测豆包收录情况

        Returns:
            检测结果详细信息
        """
        self._log("info", f"开始检测, 问题: {question[:50]}...")
        self._log("info", f"目标关键词: {keyword}, 公司: {company}")

        try:

            async def navigate_operation():
                if await self.navigate_to_page(page):
                    return {"success": True}
                return {"success": False, "error_msg": "导航失败"}

            nav_result = await self._retry_operation(navigate_operation, "导航到豆包", max_retries=2)

            if not nav_result["success"]:
                return {
                    "success": False,
                    "answer": None,
                    "keyword_found": False,
                    "company_found": False,
                    "error_msg": nav_result.get("error_msg", "导航失败"),
                }

            async def clear_operation():
                if await self.clear_chat_history(page):
                    return {"success": True}
                return {"success": False, "error_msg": "清理失败"}

            await self._retry_operation(clear_operation, "清理聊天历史", max_retries=1)

            input_selectors = self.SELECTORS["input_box"]

            success, matched_selector = await self.wait_for_selector(page, input_selectors, timeout=20000)

            if not success:
                self._log("error", "未找到输入框")
                return {
                    "success": False,
                    "answer": None,
                    "keyword_found": False,
                    "company_found": False,
                    "error_msg": "输入框未找到",
                }

            self._log("info", f"找到输入框: {matched_selector}")

            # 使用基类稳健的提交方法
            submit_selectors = self.SELECTORS.get("submit_button", [])
            submit_btn = submit_selectors[0] if submit_selectors else None

            await self.submit_question(
                page=page, question=question, input_selector=matched_selector, submit_button_selector=submit_btn
            )

            self._log("info", "已提交问题")

            initial_content = await page.inner_text("body")

            wait_result = await self.wait_for_answer_generation(
                page, initial_content, timeout=60000, check_interval=2.0
            )

            if wait_result["success"]:
                self._log("info", f"回答生成成功, 长度: {wait_result['content_length']} 字符")
            else:
                self._log("warning", f"回答生成未完成, 长度: {wait_result.get('content_length', 0)} 字符")

            answer_result = await self.get_answer_content(page, question)

            if not answer_result["success"]:
                self._log("warning", "未能获取到AI回答内容")

            answer_text = answer_result.get("answer", "")

            if not answer_text.strip():
                answer_text = await page.inner_text("body")
                self._log("info", f"使用页面全文作为回答, 长度: {len(answer_text)}")

            check_result = self.check_keywords_in_text(answer_text, keyword, company)

            self._log("info", "检测完成")
            self._log("info", f"关键词 '{keyword}' 检测结果: {check_result['keyword_found']}")
            self._log("info", f"公司名 '{company}' 检测结果: {check_result['company_found']}")

            operation_logs = self.get_operation_log()

            return {
                "success": True,
                "answer": answer_text[:5000],
                "keyword_found": check_result["keyword_found"],
                "company_found": check_result["company_found"],
                "keyword_count": check_result.get("keyword_count", 0),
                "company_count": check_result.get("company_count", 0),
                "confidence": check_result.get("confidence", 0.0),
                "answer_length": len(answer_text),
                "wait_info": wait_result,
                "answer_selector": answer_result.get("selector"),
                "operation_logs": operation_logs,
                "error_msg": None,
            }

        except Exception as e:
            self._log("error", f"检测过程发生异常: {e}")
            return {
                "success": False,
                "answer": None,
                "keyword_found": False,
                "company_found": False,
                "error_msg": str(e),
            }
