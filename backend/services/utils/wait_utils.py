# -*- coding: utf-8 -*-
"""
智能等待工具函数
提供比固定sleep更高效的等待机制
"""

import asyncio
from typing import Optional, Callable, Any
from loguru import logger


async def wait_for_condition(
    condition_fn: Callable[[], Any],
    timeout: float = 10.0,
    interval: float = 0.1,
    description: str = "condition"
) -> bool:
    """
    等待条件满足

    Args:
        condition_fn: 返回True表示条件满足
        timeout: 最大等待时间（秒）
        interval: 检查间隔（秒）
        description: 等待描述（用于日志）

    Returns:
        是否在超时前满足条件
    """
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            if await condition_fn() if asyncio.iscoroutinefunction(condition_fn) else condition_fn():
                return True
        except Exception as e:
            logger.debug(f"等待{description}时发生异常: {e}")
        await asyncio.sleep(interval)
    return False


async def wait_for_element_state(
    page,
    selector: str,
    state: str = "visible",
    timeout: float = 10.0
) -> bool:
    """
    等待元素达到指定状态

    Args:
        page: Playwright page对象
        selector: CSS选择器
        state: 状态（visible, hidden, attached, detached）
        timeout: 超时时间

    Returns:
        是否成功
    """
    try:
        await page.wait_for_selector(selector, state=state, timeout=timeout * 1000)
        return True
    except Exception as e:
        logger.warning(f"等待元素 {selector} 状态 {state} 失败: {e}")
        return False


async def wait_for_network_idle(
    page,
    timeout: float = 10.0,
    min_idle_time: float = 0.5
) -> bool:
    """
    等待网络空闲

    Args:
        page: Playwright page对象
        timeout: 最大等待时间
        min_idle_time: 网络空闲持续时间

    Returns:
        是否成功
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)
        return True
    except Exception as e:
        logger.debug(f"等待网络空闲失败: {e}")
        return False


async def smart_delay(min_delay: float = 0.1, max_delay: float = 0.5, factor: float = 1.0) -> None:
    """
    智能延迟：根据操作类型动态调整等待时间

    Args:
        min_delay: 最小延迟
        max_delay: 最大延迟
        factor: 延迟系数
    """
    import random
    delay = random.uniform(min_delay, max_delay) * factor
    await asyncio.sleep(delay)


class RetryWithBackoff:
    """
    带指数退避的重试装饰器
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, fn: Callable, *args, **kwargs) -> Any:
        """执行带重试的函数"""
        for attempt in range(self.max_retries):
            try:
                if asyncio.iscoroutinefunction(fn):
                    return await fn(*args, **kwargs)
                else:
                    return fn(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise

                # 计算退避延迟
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"操作失败，{delay}秒后重试 ({attempt + 1}/{self.max_retries}): {e}")
                await asyncio.sleep(delay)

        return None
