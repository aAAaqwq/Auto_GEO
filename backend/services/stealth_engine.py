# -*- coding: utf-8 -*-
"""
隐身浏览器引擎
基于 playwright-stealth，为 AI 平台操作提供反检测能力
配合浏览器扩展同步的指纹数据，最大化模拟真实用户浏览器
"""

import os
import sys
from typing import Optional, Dict, Any
from loguru import logger

from playwright_stealth import Stealth


def create_stealth_instance(fingerprint: Optional[Dict[str, Any]] = None) -> Stealth:
    """
    创建隐身配置实例

    优先使用浏览器扩展同步的指纹数据，
    确保后端无头浏览器与用户真实浏览器的特征一致。

    Args:
        fingerprint: 浏览器扩展收集的指纹数据，包含:
            - user_agent: 用户真实 UA
            - platform: 操作系统平台
            - languages: 浏览器语言列表
            - viewport: 屏幕分辨率
            - timezone: 时区

    Returns:
        配置好的 Stealth 实例
    """
    kwargs = {
        "navigator_webdriver": True,
        "navigator_hardware_concurrency": True,
        "navigator_platform": True,
        "navigator_user_agent": True,
        "navigator_vendor": True,
        "navigator_languages": True,
        "navigator_plugins": True,
        "navigator_permissions": True,
        "webgl_vendor": True,
        "chrome_app": True,
        "chrome_csi": True,
        "chrome_load_times": True,
        "hairline": True,
        "iframe_content_window": True,
        "media_codecs": True,
        "sec_ch_ua": True,
    }

    if fingerprint:
        ua = fingerprint.get("user_agent")
        if ua and isinstance(ua, str) and "Chrome" in ua:
            # 只传有效的 Chrome UA，避免 Stealth 解析失败
            kwargs["navigator_user_agent_override"] = ua

        platform = fingerprint.get("platform")
        if platform:
            kwargs["navigator_platform_override"] = platform

        languages = fingerprint.get("languages")
        if languages and isinstance(languages, list) and len(languages) >= 2:
            kwargs["navigator_languages_override"] = (languages[0], languages[1])
        elif fingerprint.get("language"):
            lang = fingerprint["language"]
            kwargs["navigator_languages_override"] = (lang, lang.split("-")[0] if "-" in lang else "en")

    try:
        return Stealth(**kwargs)
    except Exception as e:
        logger.warning(f"创建 Stealth 实例失败，使用默认配置: {e}")
        return Stealth()


def extract_fingerprint(storage_state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    从 storage_state 中提取指纹数据

    Args:
        storage_state: Playwright storage_state，可能包含 fingerprint 字段

    Returns:
        指纹字典，不存在则返回 None
    """
    if not storage_state:
        return None
    fp = storage_state.get("fingerprint")
    if fp and isinstance(fp, dict):
        return fp
    return None


def get_user_agent_from_fingerprint(
    fingerprint: Optional[Dict[str, Any]], default_ua: str
) -> str:
    """从指纹中提取 User-Agent，若不存在则返回默认值"""
    if fingerprint:
        ua = fingerprint.get("user_agent")
        if ua:
            return ua
    return default_ua


def get_viewport_from_fingerprint(
    fingerprint: Optional[Dict[str, Any]]
) -> Optional[Dict[str, int]]:
    """从指纹中提取 viewport 尺寸"""
    if fingerprint:
        vp = fingerprint.get("viewport")
        if vp and isinstance(vp, dict):
            return {
                "width": int(vp.get("width", 1920)),
                "height": int(vp.get("height", 1080)),
            }
    return None
