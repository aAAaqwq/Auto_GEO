# -*- coding: utf-8 -*-
"""
AdsPower 指纹浏览器管理器
通过 AdsPower REST API 管理浏览器 Profile，实现独立指纹和 Cookie 隔离
参考文档: docs/architecture/solutions/09-multi-account-browser.md
"""

import httpx
from typing import Optional, List
from dataclasses import dataclass, field
from loguru import logger
from backend.config import ADSPOWER_API_URL, ADSPOWER_ENABLED


@dataclass
class ProfileInfo:
    """AdsPower 配置文件信息"""
    user_id: str
    name: str
    group_id: str = ""
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_type: str = ""  # "http" / "socks5"
    ip_country: str = ""
    status: str = "inactive"  # "active" / "inactive"


@dataclass
class ProfileConnection:
    """配置文件连接信息"""
    ws_endpoint: str
    debug_port: str
    driver_port: str


class AdsPowerManager:
    """AdsPower 指纹浏览器管理器"""

    def __init__(self):
        self.base_url = ADSPOWER_API_URL.rstrip("/")
        self._active_profiles: dict[str, ProfileConnection] = {}

    @property
    def is_available(self) -> bool:
        """检查 AdsPower 是否可用"""
        if not ADSPOWER_ENABLED:
            return False
        try:
            resp = httpx.get(f"{self.base_url}/status", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    async def start_profile(self, profile_id: str) -> Optional[ProfileConnection]:
        """
        启动 AdsPower 配置文件

        调用: GET /api/v1/browser/start?user_id={profile_id}
        返回: {"data": {"ws": {"puppeteer": "ws://..."}, "debug_port": "..."}}
        """
        if profile_id in self._active_profiles:
            logger.info(f"配置文件 {profile_id} 已启动，复用连接")
            return self._active_profiles[profile_id]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/browser/start",
                    params={"user_id": profile_id},
                )

            data = resp.json()

            if data.get("code") != 0:
                logger.error(f"启动配置文件失败: {data.get('msg', '未知错误')}")
                return None

            ws_data = data.get("data", {}).get("ws", {})
            ws_endpoint = ws_data.get("puppeteer", "")

            connection = ProfileConnection(
                ws_endpoint=ws_endpoint,
                debug_port=data.get("data", {}).get("debug_port", ""),
                driver_port=data.get("data", {}).get("driver_port", ""),
            )

            self._active_profiles[profile_id] = connection
            logger.info(f"配置文件 {profile_id} 启动成功, ws={ws_endpoint}")
            return connection

        except Exception as e:
            logger.error(f"启动 AdsPower 配置文件异常: {e}")
            return None

    async def stop_profile(self, profile_id: str) -> bool:
        """
        关闭 AdsPower 配置文件

        调用: GET /api/v1/browser/stop?user_id={profile_id}
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/browser/stop",
                    params={"user_id": profile_id},
                )

            data = resp.json()
            self._active_profiles.pop(profile_id, None)

            if data.get("code") == 0:
                logger.info(f"配置文件 {profile_id} 已关闭")
                return True
            else:
                logger.warning(f"关闭配置文件返回非0: {data.get('msg')}")
                return False

        except Exception as e:
            logger.error(f"关闭配置文件异常: {e}")
            return False

    async def check_active(self, profile_id: str) -> bool:
        """检查配置文件是否活跃"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/browser/active",
                    params={"user_id": profile_id},
                )
            data = resp.json()
            return data.get("data", {}).get("status") == "Active"
        except Exception:
            return False

    async def list_profiles(self, group_id: str = "") -> List[ProfileInfo]:
        """
        获取所有配置文件列表

        调用: GET /api/v1/user/list
        """
        try:
            params = {"page": 1, "limit": 100}
            if group_id:
                params["group_id"] = group_id

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/user/list",
                    params=params,
                )

            data = resp.json()
            profiles = []
            for item in data.get("data", {}).get("list", []):
                profiles.append(ProfileInfo(
                    user_id=item.get("user_id", ""),
                    name=item.get("user_name", ""),
                    group_id=item.get("group_id", ""),
                    proxy_host=item.get("proxy_host", ""),
                    proxy_port=item.get("proxy_port", 0),
                    proxy_type=item.get("proxy_type", ""),
                    ip_country=item.get("ip_country", ""),
                    status="active" if item.get("status") == "Active" else "inactive",
                ))
            return profiles

        except Exception as e:
            logger.error(f"获取配置文件列表失败: {e}")
            return []

    async def create_profile(self, name: str, proxy_config: dict = None) -> Optional[str]:
        """
        创建新配置文件

        Args:
            name: 配置文件名称
            proxy_config: 代理配置 {"host": "...", "port": ..., "type": "socks5"}
        """
        payload = {
            "name": name,
            "repeat_config": ["0"],  # 不重复已有配置
            "browser": ["chrome"],
        }
        if proxy_config:
            payload["proxy"] = proxy_config

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/user/create",
                    json=payload,
                )
            data = resp.json()
            if data.get("code") == 0:
                logger.info(f"AdsPower 配置文件创建成功: {name}")
                return data.get("data", {}).get("id")
            logger.warning(f"创建配置文件失败: {data.get('msg')}")
            return None
        except Exception as e:
            logger.error(f"创建配置文件失败: {e}")
            return None

    async def close_all(self):
        """关闭所有活跃的配置文件"""
        for profile_id in list(self._active_profiles.keys()):
            await self.stop_profile(profile_id)


# 全局单例
adspower_manager = AdsPowerManager()
