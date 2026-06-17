# -*- coding: utf-8 -*-
"""
AI平台检测器基类
用这个抽象基类定义检测器的统一接口！
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from playwright.async_api import Page
from loguru import logger
import asyncio
import time
import random


class AIPlatformChecker(ABC):
    """
    AI平台检测器基类

    注意：所有AI平台检测器都要继承这个类！
    """

    def __init__(self, platform_id: str, config: Dict[str, Any]):
        """
        初始化检测器

        Args:
            platform_id: 平台ID
            config: 平台配置
        """
        self.platform_id = platform_id
        self.config = config
        self.name = config.get("name", platform_id)
        self.url = config.get("url", "")
        self.color = config.get("color", "#333333")
        self.retry_count = 3
        self.retry_delay = 2
        self.operation_log = []

    def _log(self, level: str, message: str, **kwargs):
        """
        增强的日志记录方法

        Args:
            level: 日志级别 (info, warning, error, debug)
            message: 日志消息
            **kwargs: 额外的上下文信息
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {"timestamp": timestamp, "platform": self.name, "level": level, "message": message, **kwargs}
        self.operation_log.append(log_entry)

        if level == "info":
            logger.info(f"[{self.name}] {message}")
        elif level == "warning":
            logger.warning(f"[{self.name}] {message}")
        elif level == "error":
            logger.error(f"[{self.name}] {message}")
        elif level == "debug":
            logger.debug(f"[{self.name}] {message}")

    async def _retry_operation(
        self, operation, operation_name: str, max_retries: int = None, retry_delay: int = None
    ) -> Dict[str, Any]:
        """
        通用重试机制

        Args:
            operation: 异步操作函数
            operation_name: 操作名称（用于日志）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）

        Returns:
            操作结果
        """
        max_retries = max_retries or self.retry_count
        retry_delay = retry_delay or self.retry_delay

        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                self._log("info", f"开始执行: {operation_name} (尝试 {attempt}/{max_retries})")
                result = await operation()

                if result.get("success"):
                    self._log("info", f"操作成功: {operation_name}")
                    return result
                else:
                    error_msg = result.get("error_msg", "未知错误")
                    self._log("warning", f"操作失败: {operation_name}, 错误: {error_msg}")

                    if attempt < max_retries:
                        delay = retry_delay + random.uniform(0, 1)
                        self._log("info", f"等待 {delay:.2f} 秒后进行第 {attempt + 1} 次重试")
                        await asyncio.sleep(delay)
                    else:
                        self._log("error", f"操作最终失败: {operation_name}, 错误: {error_msg}")
                        return result

            except Exception as e:
                last_error = str(e)
                self._log("error", f"操作异常: {operation_name}, 错误: {e}")

                if attempt < max_retries:
                    delay = retry_delay + random.uniform(0, 1)
                    self._log("info", f"等待 {delay:.2f} 秒后进行第 {attempt + 1} 次重试")
                    await asyncio.sleep(delay)

        return {"success": False, "error_msg": last_error or f"操作失败，已重试 {max_retries} 次"}

    @abstractmethod
    async def check(self, page: Page, question: str, keyword: str, company: str) -> Dict[str, Any]:
        """
        检测AI平台收录情况

        Args:
            page: Playwright Page对象
            question: 检测使用的问题
            keyword: 目标关键词
            company: 公司名称

        Returns:
            检测结果：
            {
                "success": bool,
                "answer": str,
                "keyword_found": bool,
                "company_found": bool,
                "error_msg": str
            }
        """
        pass

    async def navigate_to_page(self, page: Page) -> bool:
        """
        增强的导航到AI平台页面
        优化：减少等待时间，使用智能元素等待

        Returns:
            是否成功导航
        """
        try:
            self._log("info", f"正在导航到平台页面: {self.url}")

            # 使用更灵活的等待策略
            await page.goto(
                self.url,
                wait_until="domcontentloaded",  # 改为domcontentloaded，显著加快速度
                timeout=60000,
            )

            # 智能等待关键元素，替代死等
            # 尝试等待输入框、聊天区域或登录按钮
            try:
                await page.wait_for_selector(
                    "textarea, input[type='text'], [contenteditable='true'], [class*='chat'], [class*='login'], button",
                    timeout=8000,
                    state="visible",
                )
            except Exception:
                # 即使超时也不报错，继续后续检查
                pass

            self._log("info", f"页面加载完成: {self.name}")

            # 检查是否需要登录（通过检测常见的登录元素）
            login_indicators = [
                "[class*='login']",
                "[id*='login']",
                "[class*='auth']",
                "[id*='auth']",
                "button:has-text('登录')",
                "button:has-text('Sign in')",
                "text='登录'",
                "text='Sign in'",
            ]

            has_login = False
            for indicator in login_indicators:
                try:
                    # 使用 query_selector 而不是 query_selector_all，并检查可见性
                    element = await page.query_selector(indicator)
                    if element and await element.is_visible():
                        has_login = True
                        break
                except Exception:
                    continue

            if has_login:
                self._log("info", "检测到登录页面，请手动完成登录")
                # 修复：给用户90秒时间完成登录（原来30秒不够）
                await asyncio.sleep(90)
                # 重新等待页面稳定
                await page.wait_for_load_state("domcontentloaded", timeout=30000)

            return True
        except Exception as e:
            self._log("error", f"导航失败: {e}")
            return False

    async def wait_for_selector(self, page: Page, selectors: List[str], timeout: int = 20000) -> tuple:
        """
        增强的智能等待选择器出现（支持多个备选选择器）
        优化：并行等待所有选择器，而不是分批次

        Args:
            page: Playwright Page对象
            selectors: 选择器列表（按优先级排序）
            timeout: 最大等待时间（毫秒）

        Returns:
            (成功标志, 匹配到的选择器)
        """
        start_time = time.time()
        self._log("info", f"等待选择器: {selectors}, 超时时间: {timeout}ms")

        # 增加更多通用选择器
        enhanced_selectors = selectors + [
            "input[type='text']",
            "input[type='textarea']",
            "[contenteditable='true']",
            "[class*='message-input']",
            "[class*='user-input']",
            "[class*='chat-box']",
            "[id*='input']",
            "[name*='input']",
        ]

        # 去重
        unique_selectors = []
        seen = set()
        for s in enhanced_selectors:
            if s not in seen:
                unique_selectors.append(s)
                seen.add(s)

        # 1. 快速检查是否已经存在
        for selector in unique_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    self._log("info", f"选择器快速匹配成功: {selector}")
                    return True, selector
            except Exception:
                continue

        # 2. 并行等待策略
        # 创建一个复合选择器，用逗号分隔，这样只要任意一个出现就会触发
        # Playwright 支持逗号分隔的选择器列表
        combined_selector = ", ".join(unique_selectors)

        try:
            self._log("debug", "尝试并行等待选择器组合")
            # 等待任意一个选择器出现
            element = await page.wait_for_selector(combined_selector, state="visible", timeout=timeout)

            if element:
                # 找出具体是哪个选择器匹配了（反向查找略复杂，这里只要确认匹配即可）
                # 为了返回具体的selector，我们再次遍历检查哪个是可见的
                for selector in unique_selectors:
                    try:
                        el = await page.query_selector(selector)
                        if el and await el.is_visible():
                            self._log("info", f"选择器匹配成功: {selector}")
                            return True, selector
                    except Exception:
                        continue

                # 如果找不到具体的，就返回组合选择器或第一个
                self._log("info", "选择器组合匹配成功")
                return True, unique_selectors[0]

        except Exception as e:
            elapsed_time = (time.time() - start_time) * 1000
            self._log("warning", f"等待选择器超时或失败: {e}, 耗时: {elapsed_time:.0f}ms")

            # 最后的兜底策略：查找任意可见的 textarea 或 contenteditable
            # 修复：增加更多通用选择器，提高成功率
            try:
                self._log("info", "尝试兜底策略：查找页面上任意可见的输入框")
                fallback_selector = await page.evaluate("""() => {
                    // 辅助函数：获取元素的CSS选择器
                    function getSelector(el) {
                        if (el.id) return '#' + el.id;
                        if (el.className) {
                            const classes = el.className.split(' ').filter(c => c.trim().length > 0);
                            if (classes.length > 0) return el.tagName.toLowerCase() + '.' + classes.join('.');
                        }
                        return el.tagName.toLowerCase();
                    }

                    // 1. 查找所有 textarea
                    const textareas = Array.from(document.querySelectorAll('textarea'));
                    for (const el of textareas) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                            return getSelector(el);
                        }
                    }

                    // 2. 查找 contenteditable
                    const editables = Array.from(document.querySelectorAll('[contenteditable="true"]'));
                    for (const el of editables) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                            return getSelector(el);
                        }
                    }

                    // 3. 查找 input[type=text]
                    const textInputs = Array.from(document.querySelectorAll('input[type="text"]'));
                    for (const el of textInputs) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                            return getSelector(el);
                        }
                    }

                    // 4. 查找带 placeholder 的元素
                    const withPlaceholder = Array.from(document.querySelectorAll('[placeholder*="输入"], [placeholder*="提问"], [placeholder*="发送"]'));
                    for (const el of withPlaceholder) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null) {
                            return getSelector(el);
                        }
                    }

                    return null;
                }""")

                if fallback_selector:
                    self._log("info", f"兜底策略成功，找到输入框: {fallback_selector}")
                    return True, fallback_selector
            except Exception as fallback_e:
                self._log("warning", f"兜底策略失败: {fallback_e}")

            return False, None

        return False, None

    async def wait_for_answer_generation(
        self,
        page: Page,
        initial_content: str,
        selector: str = "body",
        timeout: int = 60000,
        check_interval: float = 1.0,
    ) -> Dict[str, Any]:
        """
        增强的智能等待AI回答生成完成

        Args:
            page: Playwright Page对象
            initial_content: 初始页面内容
            selector: 要监控的选择器
            timeout: 最大等待时间（毫秒）
            check_interval: 检查间隔（秒）

        Returns:
            等待结果信息
        """
        self._log("info", f"开始智能等待回答生成, 超时时间: {timeout}ms")

        start_time = time.time()
        last_content = initial_content
        stable_count = 0
        required_stable_checks = 5  # 增加稳定检查次数，防止回答还在生成中就截断
        min_content_length = 100  # 增加最小内容长度要求

        while (time.time() - start_time) < timeout / 1000:
            try:
                current_content = await page.inner_text(selector)

                content_length = len(current_content.strip())

                if content_length > min_content_length and current_content != last_content:
                    self._log("debug", f"检测到内容更新, 长度: {content_length} 字符")

                    stable_count = 0

                    last_content = current_content

                    await asyncio.sleep(check_interval)

                elif content_length > min_content_length and current_content == last_content:
                    stable_count += 1
                    self._log("debug", f"内容稳定检查: {stable_count}/{required_stable_checks}")

                    if stable_count >= required_stable_checks:
                        elapsed_time = (time.time() - start_time) * 1000
                        self._log("info", f"回答生成完成, 耗时: {elapsed_time:.0f}ms, 内容长度: {content_length}")

                        return {
                            "success": True,
                            "content_length": content_length,
                            "elapsed_time": elapsed_time,
                            "stable": True,
                        }

                    await asyncio.sleep(check_interval)

                else:
                    await asyncio.sleep(check_interval * 0.5)

            except Exception as e:
                self._log("warning", f"等待回答时发生异常: {e}")
                await asyncio.sleep(check_interval)

        elapsed_time = (time.time() - start_time) * 1000
        current_content = await page.inner_text(selector)
        content_length = len(current_content.strip())

        self._log("warning", f"等待回答超时, 耗时: {elapsed_time:.0f}ms, 内容长度: {content_length}")

        return {
            "success": content_length > min_content_length,
            "content_length": content_length,
            "elapsed_time": elapsed_time,
            "stable": stable_count >= required_stable_checks,
        }

    async def get_answer_content(self, page: Page, question: str) -> Dict[str, Any]:
        """
        增强的获取AI回答内容

        Args:
            page: Playwright Page对象
            question: 用户问题（用于过滤）

        Returns:
            获取结果
        """
        self._log("info", "开始获取AI回答内容")

        answer_selectors = [
            "[class*='assistant']",
            "[class*='ai-message']",
            "[data-role='assistant']",
            "[class*='answer-content']",
            "[class*='chat-answer']",
            ".markdown-body",
            "[class*='response']",
            "[class*='result']",
            "[class*='content-body']",
            "[class*='message-content']",
            "[class*='bot-message']",
            "[class*='reply-content']",
            "[class*='conversation-turn']",
            "[class*='chat-message']:last-of-type",
            "[class*='message-item']:last-child [class*='content']",
        ]

        answer_text = ""
        matched_selector = None

        for selector in answer_selectors:
            try:
                self._log("debug", f"尝试选择器: {selector}")

                elements = await page.query_selector_all(selector)

                if elements:
                    self._log("debug", f"选择器 {selector} 找到 {len(elements)} 个元素")

                    for element in reversed(elements):
                        try:
                            element_text = await element.inner_text()
                            element_text = element_text.strip()

                            if len(element_text) > 100:
                                if question not in element_text[:50]:
                                    answer_text = element_text
                                    matched_selector = selector
                                    self._log("info", f"找到AI回答, 选择器: {selector}, 长度: {len(answer_text)}")
                                    break

                        except Exception as e:
                            self._log("debug", f"获取元素文本失败: {e}")
                            continue

                    if answer_text:
                        break

            except Exception as e:
                self._log("debug", f"选择器 {selector} 处理失败: {e}")
                continue

        if not answer_text:
            self._log("warning", "标准选择器未找到回答, 尝试备用方法")

            # 获取页面所有文本
            page_text = await page.inner_text("body")

            # 分割成行
            lines = [line.strip() for line in page_text.split("\n") if line.strip()]

            # 过滤掉常见的菜单和无关内容
            ignored_keywords = [
                "AI回答",
                "豆包",
                "新对话",
                "帮我写作",
                "AI 创作",
                "云盘",
                "更多",
                "历史对话",
                "登录",
                "注册",
                "关于",
                "帮助",
                "设置",
                "退出",
                "反馈",
                "Terms",
                "Privacy",
                "最近对话",
                "对话分组",
                "我的空间",
                "手机版",
                "下载",
                "APP",
                "智能体",
                "发现",
                "深度思考",
                "联网搜索",
                "重新生成",
                "复制",
                "点赞",
                "点踩",
                "分享",
                "PPT 生成",
                "图像生成",
                "AI 写作",
                "文档处理",
                "网页摘要",
                "视频理解",
                "图片理解",
                "录音笔",
                "快捷方式",
                "正在思考",
                "参考来源",
            ]

            potential_answers = []
            current_block = []
            consecutive_short = 0

            for line in lines:
                # 过滤极短行
                if len(line) < 5:
                    consecutive_short += 1
                    continue

                # 检测是否为 UI 菜单项（短行 + 匹配忽略关键词）
                is_ignored = False
                if len(line) < 100:
                    for keyword in ignored_keywords:
                        if keyword in line:
                            is_ignored = True
                            break

                # 检测是否为纯 UI 元素：很短（< 20 字符）且看起来像菜单项
                is_ui_element = False
                if len(line) < 20 and not any(c in line for c in '，。！？；：、'):
                    # 中文短词组，大概率是菜单/按钮
                    is_ui_element = True

                if is_ignored or is_ui_element:
                    consecutive_short += 1
                    # 连续超过 3 个 UI 行 → 分割块
                    if consecutive_short >= 3 and current_block:
                        potential_answers.append("\n".join(current_block))
                        current_block = []
                    continue

                consecutive_short = 0

                # 过滤掉包含问题的行
                if question in line:
                    continue

                current_block.append(line)

            # 添加最后一个块
            if current_block:
                potential_answers.append("\n".join(current_block))

            # 寻找最长且质量最好的文本块
            longest_block = ""
            for block in potential_answers:
                lines_in_block = block.split("\n")
                # 跳过疑似侧边栏/菜单块
                if len(lines_in_block) > 5:
                    avg_len = sum(len(l) for l in lines_in_block) / len(lines_in_block)
                    if avg_len < 30:
                        self._log("debug", f"跳过疑似侧边栏块: 行数={len(lines_in_block)}, 平均长度={avg_len:.1f}")
                        continue

                if len(block) > len(longest_block):
                    longest_block = block

            if len(longest_block) > 100:
                answer_text = longest_block
                matched_selector = "body-text-filtered"
                self._log("info", f"使用过滤后的备用方法找到回答, 长度: {len(answer_text)}")

        if answer_text:
            self._log("info", f"成功获取回答内容, 长度: {len(answer_text)} 字符")
            return {
                "success": True,
                "answer": answer_text[:5000],
                "selector": matched_selector,
                "length": len(answer_text),
            }
        else:
            self._log("warning", "未能获取到回答内容")
            return {"success": False, "answer": "", "selector": None, "length": 0}

    @staticmethod
    def _extract_company_layers(company: str):
        """从完整公司名提取分层匹配词"""
        locations = [
            "北京", "上海", "深圳", "广州", "杭州", "南京", "成都", "武汉",
            "重庆", "西安", "天津", "苏州", "东莞", "佛山", "合肥", "长沙",
            "郑州", "济南", "青岛", "大连", "厦门", "福州", "无锡", "宁波",
            "温州", "石家庄", "哈尔滨", "沈阳", "昆明", "贵阳", "南宁",
            "海口", "珠海", "惠州", "中山", "中国", "香港", "澳门", "台湾",
        ]
        suffixes = [
            "股份有限公司", "有限责任公司", "集团有限公司",
            "科技有限公司", "信息技术有限公司", "网络技术有限公司",
            "实业有限公司", "贸易有限公司", "投资有限公司", "控股有限公司",
            "发展有限公司", "有限公司",
        ]
        industries = [
            "信息技术", "网络技术", "生物医药", "新能源",
            "科技", "实业", "贸易", "投资", "控股", "发展",
            "信息", "软件", "数据", "智能", "互联", "电子", "通信",
            "医药", "医疗", "教育", "文化", "传媒", "广告", "咨询",
            "服务", "房地产", "建筑", "装饰", "环保", "农业",
            "食品", "餐饮", "旅游", "物流", "金融", "保险", "证券",
        ]

        name = company.strip()
        core = name
        for loc in sorted(locations, key=len, reverse=True):
            if core.startswith(loc):
                core = core[len(loc):]
                break
        for suf in sorted(suffixes, key=len, reverse=True):
            if core.endswith(suf):
                core = core[:-len(suf)]
                break
        industry_matched = ""
        for ind in sorted(industries, key=len, reverse=True):
            if core.endswith(ind):
                industry_matched = ind
                core = core[:-len(ind)]
                break

        core = core.strip()
        layers = []
        seen = set()
        def add(s):
            if s and len(s) >= 2 and s not in seen:
                seen.add(s); layers.append(s)
        add(core)
        if core and industry_matched:
            add(core + industry_matched)
        add(name)
        return layers

    def check_keywords_in_text(self, text: str, keyword: str, company: str) -> Dict[str, Any]:
        """
        检查文本中是否包含关键词和公司名

        Args:
            text: 待检测文本
            keyword: 目标关键词
            company: 公司名称

        Returns:
            检测结果详细信息
        """
        self._log("info", f"开始关键词检测, 文本长度: {len(text)}")

        import re

        def clean_str(s: str) -> str:
            # 统一清理逻辑：替换非字字符为空格，合并空格，转小写
            s = re.sub(r"[^\w\s\u4e00-\u9fa5]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s.lower()

        text_lower = clean_str(text)
        keyword_lower = clean_str(keyword)

        keyword_count = text_lower.count(keyword_lower)
        keyword_positions = [m.start() for m in re.finditer(re.escape(keyword_lower), text_lower)]

        # 公司名分层匹配
        company_layers = self._extract_company_layers(company)
        self._log("info", f"公司名分层: {' > '.join(company_layers)}")

        company_found = False
        company_count = 0
        company_matched = ""
        company_positions = []

        for layer in company_layers:
            layer_lower = clean_str(layer)
            if len(layer_lower) < 2:
                continue
            count = text_lower.count(layer_lower)
            if count > 0:
                company_found = True
                company_count = count
                company_matched = layer
                company_positions = [m.start() for m in re.finditer(re.escape(layer_lower), text_lower)]
                self._log("info", f"公司名命中: '{layer}' (第{company_layers.index(layer)+1}/{len(company_layers)}层)")
                break

        result = {
            "keyword_found": keyword_count > 0,
            "keyword_count": keyword_count,
            "keyword_positions": keyword_positions[:5],
            "company_found": company_found,
            "company_count": company_count,
            "company_matched": company_matched,
            "confidence": 0.0,
            "reason": "",
        }

        if keyword_count > 0:
            result["keyword_found"] = True
            result["confidence"] = min(0.5 + keyword_count * 0.1, 0.9)
            result["reason"] = f"关键词'{keyword}'出现{keyword_count}次"

        if company_found:
            result["confidence"] = min(result["confidence"] + 0.2, 0.95)
            note = f" (匹配为'{company_matched}')" if company_matched != company else ""
            result["reason"] += f", 公司名出现{company_count}次{note}"

        if len(text) < 100 and keyword_count > 0:
            result["confidence"] = min(result["confidence"] + 0.1, 0.85)

        self._log(
            "info",
            f"检测完成: 关键词={result['keyword_found']}({keyword_count}次), "
            f"公司={result['company_found']}({company_count}次, 层:'{company_matched}'), "
            f"置信度={result['confidence']:.2f}",
        )

        return result

    async def clear_chat_history(self, page: Page) -> bool:
        """
        清理聊天历史记录（如果支持）

        Returns:
            是否成功清理
        """
        self._log("info", "尝试清理聊天历史")

        try:
            clear_selectors = [
                "[class*='new-chat']",
                "[class*='new-conversation']",
                "[class*='clear-history']",
                "button[title*='新对话']",
                "[class*='refresh'] button",
            ]

            for selector in clear_selectors:
                try:
                    elements = await page.query_selector_all(selector)

                    if elements:
                        for element in elements[:1]:
                            try:
                                await element.click(timeout=3000)
                                await asyncio.sleep(1)
                                self._log("info", f"成功点击清理按钮: {selector}")
                                return True
                            except Exception:
                                continue
                except Exception:
                    continue

            self._log("info", "未找到清理按钮或无需清理")
            return True

        except Exception as e:
            self._log("error", f"清理聊天历史失败: {e}")
            return False

    def get_operation_log(self) -> List[Dict]:
        """
        获取操作日志

        Returns:
            操作日志列表
        """
        return self.operation_log.copy()

    async def clear_operation_log(self):
        """
        清空操作日志
        """
        self.operation_log.clear()

    async def submit_question(
        self, page: Page, question: str, input_selector: str, submit_button_selector: str = None
    ) -> bool:
        """
        稳健的提问提交方法
        优化：优先使用模拟键盘输入，解决React/Vue组件状态同步问题

        Args:
            page: Playwright页面对象
            question: 问题内容
            input_selector: 输入框选择器
            submit_button_selector: 提交按钮选择器（可选）

        Returns:
            是否成功提交
        """
        try:
            self._log("info", f"开始输入问题，长度: {len(question)}")

            # 1. 聚焦并点击输入框 (确保激活)
            try:
                await page.focus(input_selector)
                await page.click(input_selector)
                await asyncio.sleep(0.5)
            except Exception as e:
                self._log("warning", f"聚焦/点击输入框失败: {e}")

            # 2. 模拟真实键盘输入 (最稳健的方式)
            # 避免使用 fill，因为它可能不会触发某些前端框架的 change 事件
            try:
                # 先尝试清空内容 (如果是 input/textarea)
                await page.evaluate(
                    """(selector) => {
                    const el = document.querySelector(selector);
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                        el.value = '';
                    } else if (el) {
                        el.innerText = '';
                    }
                }""",
                    input_selector,
                )

                # 模拟打字
                await page.keyboard.type(question, delay=30)

            except Exception as e:
                self._log("error", f"模拟输入失败: {e}")
                return False

            # 3. 验证输入结果
            input_value = await page.evaluate(
                """(selector) => {
                const el = document.querySelector(selector);
                if (!el) return null;
                return el.value || el.innerText || el.textContent;
            }""",
                input_selector,
            )

            if not input_value or len(input_value.strip()) == 0:
                self._log("warning", "检测到输入框为空，尝试使用 fill 作为回退方案")
                await page.fill(input_selector, question)

            await asyncio.sleep(0.5)
            self._log("info", "问题输入完成，准备提交")

            # 4. 提交
            submitted = False

            # 方案A: 点击发送按钮 (如果存在且可见)
            if submit_button_selector:
                try:
                    # 使用 wait_for_selector 确保按钮出现 (短超时)
                    btn = await page.wait_for_selector(submit_button_selector, state="visible", timeout=2000)
                    if btn and await btn.is_enabled():
                        self._log("info", "点击发送按钮提交")
                        await btn.click()
                        submitted = True
                except Exception:
                    self._log("debug", "发送按钮不可用或未找到")

            # 方案B: 回车提交
            if not submitted:
                self._log("info", "使用回车键提交")
                await page.press(input_selector, "Enter")

            return True

        except Exception as e:
            self._log("error", f"提问提交失败: {e}")
            return False
