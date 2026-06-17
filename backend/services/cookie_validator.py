# -*- coding: utf-8 -*-
"""
Cookie 验证器 — 基于 HTTP 请求的轻量级授权验证
不依赖浏览器页面元素检测，而是通过以下层次判断：
  Layer 1: Cookie 过期时间戳检查（零网络开销）
  Layer 2: 平台认证 API 端点探测（~1s）
  Layer 3: HTTP 响应内容正向标记检测（~2s）
  Layer 4: 完整浏览器心跳验证（fallback，~10s）
"""

import time
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
from loguru import logger

import httpx

from backend.config import AI_PLATFORMS

# 各平台的认证 API 端点探测列表（按优先级排列）
PLATFORM_AUTH_API_PROBES = {
    "deepseek": [
        "https://chat.deepseek.com/api/v0/users/current",
    ],
    "doubao": [
        "https://www.doubao.com/api/user/info",
    ],
    "qianwen": [
        "https://qianwen.com/api/user/info",
        "https://tongyi.aliyun.com/api/user/info",
    ],
}

# 各平台登录页重定向 URL 特征
PLATFORM_LOGIN_REDIRECT_PATTERNS = {
    "doubao": [
        r"passport\.doubao\.com",
        r"login\.doubao\.com",
        r"doubao\.com/login",
        r"doubao\.com/signin",
        r"passport\.bytedance\.com",
    ],
    "deepseek": [
        r"chat\.deepseek\.com/sign_in",
        r"deepseek\.com/login",
        r"deepseek\.com/signin",
    ],
    "qianwen": [
        r"login\.aliyun\.com",
        r"signin\.aliyun\.com",
        r"passport\.aliyun\.com",
        r"qianwen\.com/login",
    ],
}

# 各平台已登录时的正向 HTML 标记（只有登录后才出现的内容）
PLATFORM_AUTH_POSITIVE_MARKERS = {
    "doubao": [
        "退出登录",
        "退出",
        "user-avatar",
        "avatar-container",
        "profile",
    ],
    "deepseek": [
        "Sign out",
        "sign_out",
        "sidebar",
        "conversation-list",
        "history",
    ],
    "qianwen": [
        "退出登录",
        "退出",
        "user-info",
        "avatar-dropdown",
        "workspace",
    ],
}

# 关键认证 Cookie 名称（用于判断 cookie 类型）
SESSION_COOKIE_NAMES = {
    "session", "token", "auth", "sid", "sessionid", "connect.sid",
    "access_token", "refresh_token", "jwt", "bearer",
    "msToken", "passport", "csrf", "x-csrf",
}

# 各平台"只有登录后才会出现"的 cookie 名称
# 这些 cookie 在未登录状态下绝对不存在，可作为快速判定依据
PLATFORM_LOGIN_ONLY_COOKIES = {
    "doubao": [
        "sessionid", "sessionid_ss", "uid_tt", "uid_tt_ss",
        "odin_tt", "sid_guard", "sid_tt", "sid_ucp_v1",
        "multi_sids", "has_biz_token", "is_staff_user",
    ],
    "deepseek": [
        # deepseek 登录/未登录 cookie 差异极小，无法用 cookie 名判断，走 API 探测
    ],
    "qianwen": [
        "tongyi_sso_ticket", "tongyi_sso_ticket_hash", "login_aliyunid",
    ],
}


class CookieValidator:
    """基于 HTTP 的 Cookie 验证器"""

    def __init__(self, timeout: float = 10.0):
        self._timeout = timeout

    # ==================== 公开接口 ====================

    async def validate(
        self, platform: str, storage_state: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        验证 Cookie 是否有效

        Returns:
            (is_valid, reason, probe_info)
            probe_info 包含探测详情，用于日志和调试
        """
        if platform not in AI_PLATFORMS:
            return False, f"未知平台: {platform}", None

        cookies = storage_state.get("cookies", [])
        if not cookies:
            return False, "没有Cookie数据", None

        # Layer 1: Cookie 过期时间戳检查
        is_valid, reason = self._check_cookie_expiry(cookies)
        if not is_valid:
            return False, reason, {"layer": 1, "method": "cookie_expiry"}

        # Layer 2: 平台特有"登录后才出现"的 cookie 检查
        is_valid, reason, check_result = self._check_login_only_cookies(platform, cookies)
        if check_result:
            return is_valid, reason, {"layer": 2, "method": "login_only_cookies", **check_result}

        # Layer 3: API 端点探测
        is_valid, reason, probe_info = await self._probe_auth_api(platform, storage_state)
        if probe_info and probe_info.get("conclusive"):
            return is_valid, reason, {"layer": 3, "method": "api_probe", **probe_info}

        # Layer 4: HTTP 内容正向标记
        is_valid, reason, probe_info = await self._check_positive_markers(platform, storage_state)
        if probe_info and probe_info.get("conclusive"):
            return is_valid, reason, {"layer": 4, "method": "positive_markers", **probe_info}

        # Layer 5: 无法判断
        return True, "HTTP检查无法判断", {"layer": 5, "method": "fallback"}

    async def validate_fast(
        self, platform: str, storage_state: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        快速验证（Layer 1 + Layer 2），不进行 HTML 分析和 API 探测
        """
        cookies = storage_state.get("cookies", [])
        if not cookies:
            return False, "没有Cookie数据"

        is_valid, reason = self._check_cookie_expiry(cookies)
        if not is_valid:
            return False, reason

        # Layer 2: 登录专有 cookie 检查
        is_valid, reason, check_result = self._check_login_only_cookies(platform, cookies)
        if check_result:
            return is_valid, reason

        return True, "快速检查通过"

    # ==================== Layer 1: Cookie 过期检查 ====================

    def _check_cookie_expiry(self, cookies: list) -> Tuple[bool, str]:
        """
        检查 Cookie 过期时间戳。
        - 如果列表为空 → (False, reason)
        - 如果所有 session cookie 都已过期 → (False, reason)
        - 如果有未过期的 session cookie → (True, "ok")
        """
        if not cookies:
            return False, "Cookie列表为空"

        now = time.time()
        session_cookies = []
        other_cookies = []

        for c in cookies:
            name_lower = c.get("name", "").lower()
            is_session = any(sn in name_lower for sn in SESSION_COOKIE_NAMES)
            if is_session:
                session_cookies.append(c)
            else:
                other_cookies.append(c)

        # 检查 session cookie 过期情况
        expired_count = 0
        for c in session_cookies:
            expires = c.get("expires", 0)
            if expires and isinstance(expires, (int, float)) and expires > 0:
                if expires < now:
                    expired_count += 1

        if session_cookies and expired_count == len(session_cookies):
            return False, f"所有认证Cookie已过期 ({expired_count}/{len(session_cookies)})"

        # 如果完全没有 session cookie，检查普通 cookie
        if not session_cookies:
            if not other_cookies:
                return False, "没有有效Cookie"
            all_expired = True
            for c in other_cookies:
                expires = c.get("expires", 0)
                if not expires or expires > now:
                    all_expired = False
                    break
            if all_expired:
                return False, "所有Cookie已过期"

        return True, "ok"

    # ==================== Layer 2: 登录专有 Cookie 检查 ====================

    def _check_login_only_cookies(
        self, platform: str, cookies: list
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        检查是否存在"只有登录后才会出现"的 cookie。
        这些 cookie 在未登录状态下绝对不存在，可快速判定。

        Returns:
            (is_valid, reason, result_dict or None)
            result_dict 为 None 表示无法判断（没有配置该平台的登录专有 cookie）
        """
        required_names = PLATFORM_LOGIN_ONLY_COOKIES.get(platform, [])
        if not required_names:
            return True, "无登录专有cookie配置", None  # 无结论

        cookie_names = {c.get("name", "") for c in cookies}
        found = [name for name in required_names if name in cookie_names]

        if not found:
            return False, f"缺少登录专有cookie（需{required_names[:3]}...）", {
                "conclusive": True,
                "found": found,
                "required_count": len(required_names),
            }

        # 至少 1 个登录专有 cookie 即可确认
        if len(found) >= 1:
            now = time.time()
            # 确认这些登录专有 cookie 没过期
            expired_count = 0
            for c in cookies:
                if c.get("name") in found:
                    expires = c.get("expires", 0)
                    if expires and isinstance(expires, (int, float)) and expires > 0 and expires < now:
                        expired_count += 1

            if expired_count > 0:
                logger.info(f"平台 {platform}: 找到登录专有cookie {found}，但 {expired_count} 个已过期")
                return True, f"登录专有cookie存在但部分过期: {found}", None  # 无结论，继续后续检查

            return True, f"检测到登录专有cookie: {found}", {
                "conclusive": True,
                "found": found,
            }

        return True, f"登录专有cookie不足: {found}", None  # 无结论

    # ==================== Layer 3: API 端点探测 ====================

    async def _probe_auth_api(
        self, platform: str, storage_state: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        探测平台认证 API 端点。
        用存储的 Cookie 请求 API，根据响应判断认证状态。

        Returns:
            (is_valid, reason, probe_info)
            probe_info 含 'conclusive' 字段表示结果是否确定
        """
        probes = PLATFORM_AUTH_API_PROBES.get(platform, [])
        if not probes:
            return True, "无API探测端点", {"conclusive": False}

        headers = self._build_request_headers(storage_state)
        cookie_kv = self._build_cookie_dict(storage_state)

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            for probe_url in probes:
                try:
                    response = await client.get(probe_url, cookies=cookie_kv, headers=headers)
                    logger.debug(f"API探测 {probe_url}: status={response.status_code}, "
                                 f"len={len(response.text)}, redirect={response.headers.get('location', 'none')}")

                    # 401/403 → 明确未认证
                    if response.status_code in (401, 403):
                        return False, f"API返回{response.status_code}", {
                            "conclusive": True,
                            "url": probe_url,
                            "status": response.status_code,
                        }

                    # 200 → 检查响应体
                    if response.status_code == 200:
                        body = response.text
                        body_lower = body.lower()

                        # 包含用户数据 → 已登录
                        if self._is_api_user_response(body):
                            return True, "API返回用户数据", {
                                "conclusive": True,
                                "url": probe_url,
                                "status": 200,
                            }

                        # 包含认证失败标记 → 未登录
                        auth_fail_markers = [
                            "missing token", "unauthorized", "unauthenticated",
                            "not logged in", "login required", "请先登录",
                            "no auth", "invalid token", "token expired",
                        ]
                        for marker in auth_fail_markers:
                            if marker in body_lower:
                                return False, f"API返回认证失败: {marker}", {
                                    "conclusive": True,
                                    "url": probe_url,
                                    "status": 200,
                                }

                        logger.debug(f"API返回200但非用户数据: {body[:200]}")
                        continue

                    # 302/301 → 检查是否是重定向到登录页
                    if response.status_code in (301, 302, 303, 307, 308):
                        redirect = response.headers.get("location", "")
                        if self._is_login_redirect(platform, redirect):
                            return False, f"重定向到登录页: {redirect}", {
                                "conclusive": True,
                                "url": probe_url,
                                "status": response.status_code,
                                "redirect": redirect,
                            }
                        continue

                except httpx.TimeoutException:
                    continue
                except Exception as e:
                    logger.debug(f"API探测失败 {probe_url}: {e}")
                    continue

        return True, "API探测无结论", {"conclusive": False}

    # ==================== Layer 3: HTTP 内容正向标记检测 ====================

    async def _check_positive_markers(
        self, platform: str, storage_state: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        HTTP GET 平台首页 + 正向标记检测。
        **不检测登录按钮**，而是检测只有登录后才出现的元素。

        Returns:
            (is_valid, reason, probe_info)
        """
        platform_config = AI_PLATFORMS.get(platform, {})
        platform_url = platform_config.get("url", "")
        if not platform_url:
            return True, "无平台URL", {"conclusive": False}

        headers = self._build_request_headers(storage_state)
        cookie_kv = self._build_cookie_dict(storage_state)
        markers = PLATFORM_AUTH_POSITIVE_MARKERS.get(platform, [])

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            try:
                response = await client.get(platform_url, cookies=cookie_kv, headers=headers)

                # 检查 HTTP 重定向
                if response.status_code in (301, 302, 303, 307, 308):
                    redirect = response.headers.get("location", "")
                    if self._is_login_redirect(platform, redirect):
                        return False, f"重定向到登录页: {redirect}", {
                            "conclusive": True,
                            "url": platform_url,
                            "redirect": redirect,
                        }
                    # 非登录重定向 → 不确定
                    return True, f"重定向到非登录URL: {redirect}", {"conclusive": False}

                if response.status_code == 200:
                    body = response.text.lower()

                    # 正向标记检测：查找已登录后才会出现的内容
                    found_markers = []
                    for marker in markers:
                        if marker.lower() in body:
                            found_markers.append(marker)

                    if found_markers:
                        return True, f"检测到已登录标记: {found_markers}", {
                            "conclusive": True,
                            "markers_found": found_markers,
                        }

                    # 如果有明确的"未登录"标记（如仅首页可见的登录入口）
                    # 注意：这里不检测"登录按钮"，只检测全局登录墙
                    if self._has_login_wall(platform, response.text):
                        return False, "检测到登录墙", {"conclusive": True}

                    logger.debug(f"正向标记检测 {platform_url}: 未找到标记{markers}, 页面长度={len(body)}")
                    return True, "HTTP检查无结论", {"conclusive": False}

                return True, f"HTTP状态码{response.status_code}", {"conclusive": False}

            except httpx.TimeoutException:
                return True, "HTTP请求超时", {"conclusive": False}
            except Exception as e:
                return True, f"HTTP请求异常: {e}", {"conclusive": False}

    # ==================== 辅助方法 ====================

    def _build_cookie_dict(self, storage_state: Dict[str, Any]) -> Dict[str, str]:
        """将 storage_state 中的 cookies 转为 httpx 可用的 dict"""
        result = {}
        for c in storage_state.get("cookies", []):
            name = c.get("name", "")
            value = c.get("value", "")
            if name:
                result[name] = value
        return result

    def _build_request_headers(self, storage_state: Dict[str, Any]) -> Dict[str, str]:
        """构建 HTTP 请求头，匹配原始浏览器指纹"""
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        fingerprint = storage_state.get("fingerprint", {})
        if fingerprint and fingerprint.get("user_agent"):
            headers["User-Agent"] = fingerprint["user_agent"]

        # 尝试从 localStorage 提取 userToken 作为 Bearer token
        user_token = self._extract_local_storage_value(storage_state, "userToken")
        if user_token:
            headers["Authorization"] = f"Bearer {user_token}"

        return headers

    def _extract_local_storage_value(
        self, storage_state: Dict[str, Any], key: str
    ) -> Optional[str]:
        """从 storage_state 的 origins 中提取指定 localStorage key 的值"""
        origins = storage_state.get("origins", [])
        for origin in origins:
            entries = origin.get("localStorage", [])
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict) and entry.get("name") == key:
                        return entry.get("value")
        return None

    def _is_login_redirect(self, platform: str, redirect_url: str) -> bool:
        """判断重定向目标是否为登录页面"""
        patterns = PLATFORM_LOGIN_REDIRECT_PATTERNS.get(platform, [])
        for pattern in patterns:
            if re.search(pattern, redirect_url, re.IGNORECASE):
                return True
        return False

    def _is_api_user_response(self, body: str) -> bool:
        """
        判断 API 响应是否为有效的用户数据。
        大部分用户 API 返回 JSON，包含 user_id、username、email 等字段。
        """
        if not body or len(body) < 10:
            return False
        try:
            import json

            data = json.loads(body)
            # 直接是用户对象
            if isinstance(data, dict):
                if any(k in data for k in ("user_id", "userId", "username", "email", "phone", "nickname", "name")):
                    return True
                # 嵌套在 data/user 字段中
                inner = data.get("data") or data.get("user") or data.get("result") or {}
                if isinstance(inner, dict):
                    if any(k in inner for k in ("user_id", "userId", "username", "email", "phone", "nickname", "name")):
                        return True
        except (json.JSONDecodeError, ValueError):
            pass
        return False

    def _has_login_wall(self, platform: str, html: str) -> bool:
        """
        检测页面是否为"登录墙"——即不登录就无法看到任何内容的页面。
        注意：不是检测"登录按钮"，而是检测页面是否主要由登录表单组成。
        """
        html_lower = html.lower()
        # 登录墙特征：页面很小 + 有登录表单核心元素
        if len(html) < 5000:
            has_password_input = 'type="password"' in html_lower or "type='password'" in html_lower
            has_submit = 'type="submit"' in html_lower or "type='submit'" in html_lower
            if has_password_input and has_submit:
                return True
        return False


# 全局单例
cookie_validator = CookieValidator()
