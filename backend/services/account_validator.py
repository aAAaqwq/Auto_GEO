# -*- coding: utf-8 -*-
"""
账号授权状态验证服务 - 增强版
批量检测所有账号的授权有效性
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
from loguru import logger
from playwright.async_api import async_playwright, Browser, TimeoutError as PlaywrightTimeoutError

from backend.config import PLATFORMS, BROWSER_ARGS
from backend.services.crypto import decrypt_cookies, decrypt_storage_state


class AccountValidator:
    """账号授权验证器"""  # 修复：中文引号→英文引号，删除多余双引号

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def _start_browser(self):
        """启动浏览器实例"""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,  # 保持无头模式以提高性能
                args=BROWSER_ARGS
                + [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--disable-background-networking",
                    "--disable-features=Translate",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-web-security",  # 允许跨域，某些平台需要
                    "--disable-features=IsolateOrigins,site-per-process",  # 共享进程上下文
                ],
            )
            logger.info("验证浏览器已启动")

    async def _stop_browser(self):
        """关闭浏览器实例"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("验证浏览器已关闭")

    def _get_login_url_patterns(self, platform: str) -> List[str]:
        """
        获取平台登录页面的 URL 模式
        如果访问后跳转到这些 URL，说明需要重新登录
        """
        # 更精确的登录URL模式匹配
        platform_patterns = {
            "zhihu": [r"https://www\.zhihu\.com/signin", r"https://zhuanlan\.zhihu\.com/signin"],
            "baijiahao": [r"https://baijiahao\.baidu\.com/.*login", r"https://passport\.baidu\.com/.*"],
            "sohu": [r"https://mp\.sohu\.com/.*login", r"/login"],
            "toutiao": [r"https://mp\.toutiao\.com/.*login", r"/login"],
            "wenku": [r"https://passport\.baidu\.com/.*login", r"/login", r"/signin"],
            "penguin": [r"https://om\.qq\.com/userAuth/index", r"/login"],
            "weixin": [r"https://mp\.weixin\.qq\.com/.*login", r"/login"],
            "wangyi": [r"https://mp\.163\.com/login\.html", r"/login"],
            "zijie": [r"https://mp\.zijie\.com/.*login", r"/login"],  # 修复：子节平台独立URL（原复用头条号）
            "xiaohongshu": [r"https://creator\.xiaohongshu\.com/login", r"/login"],
            "bilibili": [r"https://passport\.bilibili\.com/login", r"/login"],
            "36kr": [r"https://passport\.36kr\.com/.*signin", r"/login", r"/signin"],
            "huxiu": [r"https://www\.huxiu\.com/passport/login", r"/login"],
            "woshipm": [r"https://passport\.woshipm\.com/login", r"/login"],
            # 其他平台使用通用模式
        }

        # 如果没有特定平台的模式，返回通用模式
        if platform not in platform_patterns:
            return [r"/login", r"/signin"]

        return platform_patterns[platform]

    def _is_redirect_to_login(self, url: str, platform: str) -> bool:
        """
        检查 URL 是否跳转到登录页面（使用正则匹配，更精确）
        """
        login_patterns = self._get_login_url_patterns(platform)
        url_lower = url.lower()

        for pattern in login_patterns:
            try:
                if re.search(pattern, url_lower, re.IGNORECASE):
                    logger.debug(f"检测到登录页URL模式: {pattern} 匹配 {url}")
                    return True
            except Exception as e:
                logger.warning(f"正则匹配失败: {pattern}, 错误: {e}")
                continue
        return False

    def _has_login_keywords_in_title(self, title: str) -> bool:
        """
        检查标题中是否包含登录相关关键词
        注意：这里会检查标题是否**完全**是登录页标题
        """
        # 定义明确的登录页标题模式
        login_title_patterns = [
            r"^登录\s*-\s*.*",  # 以"登录-"开头
            r"^\s*登录\s*$",  # 仅有"登录"
            r"^.*登录页$",  # 以"登录页"结尾
            r"^Sign\s+in\s*-\s*.*",  # 英文登录
        ]

        for pattern in login_title_patterns:
            try:
                if re.match(pattern, title, re.IGNORECASE):
                    logger.debug(f"检测到登录页标题: {title} 匹配模式 {pattern}")
                    return True
            except Exception as e:
                logger.warning(f"标题匹配失败: {pattern}, 错误: {e}")
                continue

        return False

    async def _check_authenticated_positive(self, page, platform: str) -> Tuple[Optional[bool], str]:
        """
        正面验证：检查页面上是否存在登录后特有的元素
        返回: (是否已登录, 原因)
        返回None表示无法确定，需要其他方法判断
        """
        try:
            # 平台特定的验证方法
            if platform == "zhihu":
                # 知乎：检查是否有页面标题异常或关键元素
                current_url = page.url
                if "/signin" in current_url or "/login" in current_url:
                    return False, f"当前在登录页: {current_url}"

                # 检查登录按钮（如果存在则未登录）
                login_button = await page.query_selector("button:has-text('登录')")
                if login_button:
                    return False, "检测到登录按钮，未登录"

                # 检查是否有用户头像或用户菜单
                user_avatar = await page.query_selector(".AppHeader-userAvatar")
                user_menu = await page.query_selector(".AppHeader-profileText")
                if user_avatar or user_menu:
                    return True, "检测到用户信息，已登录"

            elif platform == "weixin":
                # 微信公众号：检查URL和特定元素
                current_url = page.url
                if "/login" in current_url:
                    return False, f"当前在登录页: {current_url}"

                # 检查是否有公众号信息
                account_name = await page.query_selector(".weui-desktop-account__name")
                if account_name:
                    return True, "检测到公众号名称，已登录"

            elif platform == "toutiao":
                # 头条号：检查用户信息
                current_url = page.url
                if "/login" in current_url:
                    return False, f"当前在登录页: {current_url}"

                user_name = await page.query_selector(".user-name")
                if user_name:
                    return True, "检测到用户名，已登录"

            elif platform == "baijiahao":
                # 百家号：检查作者中心
                current_url = page.url
                if "login" in current_url or "passport" in current_url:
                    return False, f"可能重定向到登录页: {current_url}"

                user_info = await page.query_selector(".user-info-name")
                if user_info:
                    return True, "检测到用户信息，已登录"

            elif platform == "sohu":
                # 搜狐号
                user_name = await page.query_selector(".user-name")
                if user_name:
                    return True, "检测到用户名，已登录"

            # 检查Cookie数量（至少要有1个）
            cookies = await page.context.cookies()
            if not cookies:
                return False, "没有Cookie，未授权"

        except PlaywrightTimeoutError:
            return None, "元素查询超时，无法验证"
        except Exception as e:
            logger.debug(f"正面验证异常: {e}")

        # 无法确定，返回None让其他方法判断
        return None, "无法确定"

    async def _check_account_auth(self, account: Any, db_session: Any) -> Dict[str, Any]:
        """
        检查单个账号的授权状态
        account: 数据库Account模型实例，db_session: 数据库会话
        """
        result = {
            "account_id": account.id,
            "platform": account.platform,
            "account_name": account.account_name,
            "status_before": account.status,
            "is_valid": False,
            "message": "",
            "check_time": datetime.now().isoformat(),
        }

        # 修复：删除重复的日志打印
        logger.info(f"开始检测账号 {account.account_name} ({account.platform})")

        if not account.cookies or not account.storage_state:
            result["message"] = "账号未授权（缺少cookies或storage_state）"
            logger.warning(f"账号 {account.account_name} 未授权")
            return result

        platform_config = PLATFORMS.get(account.platform)
        if not platform_config:
            result["message"] = f"不支持的平台: {account.platform}"
            logger.warning(f"不支持的平台: {account.platform}")
            return result

        # 优先使用 publish_url，如果没有则使用 home_url
        test_url = platform_config.get("publish_url") or platform_config.get("home_url")
        if not test_url:
            result["message"] = "平台URL未配置"
            logger.warning(f"平台 {account.platform} URL未配置")
            return result

        try:
            await self._start_browser()

            # 解密存储状态
            storage_state = decrypt_storage_state(account.storage_state)
            if not storage_state or not isinstance(storage_state, dict):
                logger.warning("storage_state解密失败或格式错误，尝试使用cookies")
                storage_state = {"cookies": decrypt_cookies(account.cookies)}
            else:
                # 兼容旧数据格式：如果缺少 cookies 字段，从 account.cookies 补充
                if "cookies" not in storage_state and account.cookies:
                    logger.warning("storage_state缺少cookies字段，使用独立cookies")
                    storage_state["cookies"] = decrypt_cookies(account.cookies)

            logger.debug(f"账号 {account.account_name} 准备创建浏览器上下文")

            # 创建上下文和页面
            context = await self._browser.new_context(
                storage_state=storage_state, viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()

            try:
                # 访问测试页面（根据平台设置不同超时时间）
                timeout = 30000
                if account.platform in ["sohu", "wangyi"]:
                    timeout = 60000  # 搜狐和网易超时时间增加到60秒

                logger.info(f"访问测试URL: {test_url} (超时: {timeout}ms)")
                response = await page.goto(test_url, wait_until="domcontentloaded", timeout=timeout)

                # 等待页面稳定
                await asyncio.sleep(2)

                # 获取实际 URL 和标题（添加异常处理，防止页面导航导致上下文销毁）
                try:
                    actual_url = page.url
                    title = await page.title()
                except Exception as e:
                    logger.warning(f"获取页面信息时发生异常（可能是页面导航）: {e}")
                    # 使用导航前的URL作为实际URL
                    actual_url = test_url
                    title = ""

                logger.info(f"账号 {account.account_name} 访问结果:")
                logger.info(f"  URL: {actual_url}")
                logger.info(f"  Title: {title}")
                logger.info(f"  Status: {response.status if response else 'N/A'}")

                # ========== 验证步骤1：URL重定向检测 ==========
                # 先检查URL，如果明显在登录页，直接判定
                if self._is_redirect_to_login(actual_url, account.platform):
                    result["is_valid"] = False
                    result["message"] = f"会话已过期，跳转到登录页面: {actual_url}"
                    account.status = -1
                    logger.warning(f"账号 {account.account_name} 跳转到登录页: {actual_url}")
                    db_session.commit()
                    return result

                # ========== 验证步骤2：页面标题检测 ==========
                if self._has_login_keywords_in_title(title):
                    result["is_valid"] = False
                    result["message"] = f"页面标题显示需要登录: {title}"
                    account.status = -1
                    logger.warning(f"账号 {account.account_name} 页面标题显示需要登录: {title}")
                    db_session.commit()
                    return result

                # ========== 验证步骤3：正面验证 ==========
                # 检查页面上是否有登录后的元素
                is_authenticated, auth_reason = await self._check_authenticated_positive(page, account.platform)

                if is_authenticated is True:
                    result["is_valid"] = True
                    result["message"] = f"授权有效: {auth_reason}"
                    account.status = 1
                    logger.success(f"账号 {account.account_name} 正面验证通过: {auth_reason}")
                    db_session.commit()
                    return result

                elif is_authenticated is False:
                    result["is_valid"] = False
                    result["message"] = f"授权失效: {auth_reason}"
                    account.status = -1
                    logger.warning(f"账号 {account.account_name} 正面验证失败: {auth_reason}")
                    db_session.commit()
                    return result

                # ========== 验证步骤4：Cookie数量检查 ==========
                cookies = await context.cookies()
                logger.info(f"Cookie数量: {len(cookies)}")
                if not cookies:
                    result["is_valid"] = False
                    result["message"] = "没有Cookie，可能未授权"
                    account.status = -1
                    logger.warning(f"账号 {account.account_name} 没有Cookie")
                    db_session.commit()
                    return result

                # ========== 默认：授权有效 ==========
                result["is_valid"] = True
                result["message"] = "授权有效（未检测到失效迹象）"
                account.status = 1
                logger.success(f"账号 {account.account_name} 授权有效")
                db_session.commit()

            finally:
                # 确保上下文无论是否异常都关闭
                await context.close()

        except Exception as e:
            import traceback

            logger.error(f"检测账号 {account.account_name} 时发生错误: {e}")
            logger.error(f"错误堆栈:\n{traceback.format_exc()}")
            result["message"] = f"检测失败: {str(e)}"
            result["is_valid"] = False
            # 检测失败时也将状态设为-1，表示需要重新授权
            try:
                account.status = -1
                db_session.commit()
            except Exception as commit_error:
                logger.error(f"提交数据库变更失败: {commit_error}")
                db_session.rollback()  # 新增：提交失败时回滚，避免数据库会话卡死

        return result

    async def check_all_accounts(self, db_session: Any, progress_callback: Optional[Callable] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        批量检测账号的授权状态

        Args:
            db_session: 数据库会话
            progress_callback: 进度回调函数
            user_id: 可选，只检测指定用户的账号（数据隔离）
        """
        from backend.database.models import Account

        # 构建查询：已激活 + 未软删除
        query = db_session.query(Account).filter(
            Account.status == 1,
            Account.deleted_at.is_(None),
        )

        # 数据隔离：只检测指定用户的账号
        if user_id is not None:
            query = query.filter(Account.user_id == user_id)

        accounts = query.all()
        total = len(accounts)

        if total == 0:
            logger.info("没有需要检测的账号")
            return {"total": 0, "success": 0, "failed": 0, "results": [], "check_time": datetime.now().isoformat()}

        logger.info(f"开始批量检测 {total} 个账号的授权状态")

        results = []
        success_count = 0
        failed_count = 0

        for index, account in enumerate(accounts, 1):
            logger.info(f"[{index}/{total}] 检测账号: {account.account_name} ({account.platform})")

            result = await self._check_account_auth(account, db_session)
            results.append(result)

            if result["is_valid"]:
                success_count += 1
            else:
                failed_count += 1

            # 进度回调兼容同步/异步函数
            if progress_callback:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(index, total, result)
                else:
                    progress_callback(index, total, result)

        await self._stop_browser()

        summary = {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "results": results,
            "check_time": datetime.now().isoformat(),
        }

        logger.info(f"批量检测完成: 总计 {total}, 成功 {success_count}, 失败 {failed_count}")
        return summary


# 全局单例
account_validator = AccountValidator()
