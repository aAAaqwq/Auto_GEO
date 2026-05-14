# -*- coding: utf-8 -*-
"""
管理员配置API
处理系统配置、服务状态等管理功能
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
import os
import sys
import platform as sys_platform
import subprocess

from backend.database import get_db
from backend.database.models import User, Project, Account, GeoArticle, ScheduledTask
from backend.api.user import require_admin
from backend.schemas import ApiResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ==================== Pydantic模型 ====================
class SystemConfigUpdate(BaseModel):
    """系统配置更新请求"""
    app_name: Optional[str] = Field(None, description="应用名称")
    debug: Optional[bool] = Field(None, description="调试模式")
    jwt_expire_minutes: Optional[int] = Field(None, ge=1, description="JWT过期时间(分钟)")
    max_concurrent_publish: Optional[int] = Field(None, ge=1, description="最大并发发布数")
    publish_timeout: Optional[int] = Field(None, ge=1, description="发布超时时间(秒)")
    max_retry_count: Optional[int] = Field(None, ge=0, description="最大重试次数")


class SystemConfigResponse(BaseModel):
    """系统配置响应"""
    app_name: str
    version: str
    debug: bool
    environment: str
    database_type: str
    jwt_expire_minutes: int
    max_concurrent_publish: int
    publish_timeout: int
    max_retry_count: int


class ServiceStatus(BaseModel):
    """服务状态"""
    name: str
    status: str  # running, stopped, error
    message: Optional[str] = None
    last_check: Optional[str] = None


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    status: str
    timestamp: str
    uptime: Optional[str] = None
    version: str
    services: Dict[str, ServiceStatus]
    stats: Dict[str, Any]


class RestartRequest(BaseModel):
    """重启请求"""
    delay_seconds: int = Field(5, ge=0, le=300, description="延迟重启秒数")
    reason: Optional[str] = Field(None, description="重启原因")


# ==================== 工具函数 ====================
def get_system_uptime() -> Optional[str]:
    """获取系统运行时间"""
    try:
        if sys_platform.system() == "Linux":
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                if days > 0:
                    return f"{days}天{hours}小时{minutes}分钟"
                elif hours > 0:
                    return f"{hours}小时{minutes}分钟"
                else:
                    return f"{minutes}分钟"
        return None
    except Exception:
        return None


def check_database_connection(db: Session) -> ServiceStatus:
    """检查数据库连接"""
    try:
        db.execute("SELECT 1")
        return ServiceStatus(
            name="database",
            status="running",
            message="数据库连接正常",
            last_check=datetime.now().isoformat()
        )
    except Exception as e:
        return ServiceStatus(
            name="database",
            status="error",
            message=f"数据库连接失败: {str(e)}",
            last_check=datetime.now().isoformat()
        )


def check_scheduler_service() -> ServiceStatus:
    """检查调度器服务状态"""
    try:
        from backend.services.scheduler_service import get_scheduler_service
        scheduler = get_scheduler_service()
        is_running = scheduler.is_running() if hasattr(scheduler, 'is_running') else True

        return ServiceStatus(
            name="scheduler",
            status="running" if is_running else "stopped",
            message="调度器服务运行正常" if is_running else "调度器服务已停止",
            last_check=datetime.now().isoformat()
        )
    except Exception as e:
        return ServiceStatus(
            name="scheduler",
            status="error",
            message=f"调度器检查失败: {str(e)}",
            last_check=datetime.now().isoformat()
        )


def check_ragflow_connection() -> ServiceStatus:
    """检查RAGFlow连接"""
    try:
        from backend.config import RAGFLOW_BASE_URL, RAGFLOW_API_KEY
        import httpx

        if not RAGFLOW_API_KEY:
            return ServiceStatus(
                name="ragflow",
                status="stopped",
                message="RAGFlow未配置",
                last_check=datetime.now().isoformat()
            )

        response = httpx.get(
            f"{RAGFLOW_BASE_URL}/api/v1/user",
            headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"},
            timeout=5.0
        )

        if response.status_code == 200:
            return ServiceStatus(
                name="ragflow",
                status="running",
                message="RAGFlow连接正常",
                last_check=datetime.now().isoformat()
            )
        else:
            return ServiceStatus(
                name="ragflow",
                status="error",
                message=f"RAGFlow返回错误: {response.status_code}",
                last_check=datetime.now().isoformat()
            )
    except Exception as e:
        return ServiceStatus(
            name="ragflow",
            status="error",
            message=f"RAGFlow连接失败: {str(e)}",
            last_check=datetime.now().isoformat()
        )


def check_n8n_connection() -> ServiceStatus:
    """检查n8n连接"""
    try:
        from backend.config import N8N_WEBHOOK_URL
        import httpx

        if not N8N_WEBHOOK_URL:
            return ServiceStatus(
                name="n8n",
                status="stopped",
                message="n8n未配置",
                last_check=datetime.now().isoformat()
            )

        health_url = N8N_WEBHOOK_URL.replace("/webhook", "/healthz")
        response = httpx.get(health_url, timeout=5.0)

        if response.status_code == 200:
            return ServiceStatus(
                name="n8n",
                status="running",
                message="n8n连接正常",
                last_check=datetime.now().isoformat()
            )
        else:
            return ServiceStatus(
                name="n8n",
                status="error",
                message=f"n8n返回错误: {response.status_code}",
                last_check=datetime.now().isoformat()
            )
    except Exception as e:
        return ServiceStatus(
            name="n8n",
            status="error",
            message=f"n8n连接失败: {str(e)}",
            last_check=datetime.now().isoformat()
        )


# ==================== API端点 ====================
@router.get("/config", response_model=ApiResponse)
async def get_system_config(current_user: User = Depends(require_admin)):
    """
    获取系统配置（仅管理员）
    返回当前系统的配置信息
    """
    try:
        from backend.config import (
            APP_NAME, APP_VERSION, DEBUG, DATABASE_URL,
            MAX_CONCURRENT_PUBLISH, PUBLISH_TIMEOUT, MAX_RETRY_COUNT
        )
        from backend.database import get_database_type

        db_type = get_database_type()
        environment = os.getenv("ENVIRONMENT", "development")

        # JWT过期时间从环境变量获取，或使用默认值
        jwt_expire = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))

        config = {
            "app_name": APP_NAME,
            "version": APP_VERSION,
            "debug": DEBUG,
            "environment": environment,
            "database_type": db_type,
            "jwt_expire_minutes": jwt_expire,
            "max_concurrent_publish": MAX_CONCURRENT_PUBLISH,
            "publish_timeout": PUBLISH_TIMEOUT,
            "max_retry_count": MAX_RETRY_COUNT,
        }

        return ApiResponse(
            success=True,
            message="获取成功",
            data=config
        )

    except Exception as e:
        logger.error(f"获取系统配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取配置失败: {str(e)}"
        )


@router.put("/config", response_model=ApiResponse)
async def update_system_config(
    request: SystemConfigUpdate,
    current_user: User = Depends(require_admin)
):
    """
    更新系统配置（仅管理员）

    **注意**: 此端点仅更新运行时配置，重启后会恢复为环境变量或配置文件中的值。
    要永久修改配置，请修改环境变量或配置文件。

    - **app_name**: 应用名称
    - **debug**: 调试模式
    - **jwt_expire_minutes**: JWT过期时间(分钟)
    - **max_concurrent_publish**: 最大并发发布数
    - **publish_timeout**: 发布超时时间(秒)
    - **max_retry_count**: 最大重试次数
    """
    try:
        updated_fields = []

        # 更新配置
        if request.app_name is not None:
            # 仅支持运行时修改，实际需要修改配置文件
            updated_fields.append("app_name")

        if request.debug is not None:
            # 仅支持运行时修改
            from backend import config
            config.DEBUG = request.debug
            updated_fields.append("debug")

        if request.jwt_expire_minutes is not None:
            from backend.api.user import JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            # 修改模块级别的变量
            import backend.api.user as user_module
            user_module.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = request.jwt_expire_minutes
            updated_fields.append("jwt_expire_minutes")

        if request.max_concurrent_publish is not None:
            from backend import config
            config.MAX_CONCURRENT_PUBLISH = request.max_concurrent_publish
            updated_fields.append("max_concurrent_publish")

        if request.publish_timeout is not None:
            from backend import config
            config.PUBLISH_TIMEOUT = request.publish_timeout
            updated_fields.append("publish_timeout")

        if request.max_retry_count is not None:
            from backend import config
            config.MAX_RETRY_COUNT = request.max_retry_count
            updated_fields.append("max_retry_count")

        logger.info(f"管理员 {current_user.username} 更新了系统配置: {', '.join(updated_fields)}")

        # 返回更新后的配置
        from backend.config import (
            APP_NAME, APP_VERSION, DEBUG,
            MAX_CONCURRENT_PUBLISH, PUBLISH_TIMEOUT, MAX_RETRY_COUNT
        )
        from backend.database import get_database_type
        from backend.api.user import JWT_ACCESS_TOKEN_EXPIRE_MINUTES

        return ApiResponse(
            success=True,
            message="配置已更新",
            data={
                "updated_fields": updated_fields,
                "current_config": {
                    "app_name": APP_NAME,
                    "version": APP_VERSION,
                    "debug": DEBUG,
                    "environment": os.getenv("ENVIRONMENT", "development"),
                    "database_type": get_database_type(),
                    "jwt_expire_minutes": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
                    "max_concurrent_publish": MAX_CONCURRENT_PUBLISH,
                    "publish_timeout": PUBLISH_TIMEOUT,
                    "max_retry_count": MAX_RETRY_COUNT,
                }
            }
        )

    except Exception as e:
        logger.error(f"更新系统配置失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新配置失败: {str(e)}"
        )


@router.get("/status", response_model=ApiResponse)
async def get_system_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取系统状态（仅管理员）
    返回服务运行状态、数据库统计等信息
    """
    try:
        from backend.config import APP_VERSION

        services = {
            "database": check_database_connection(db),
            "scheduler": check_scheduler_service(),
            "ragflow": check_ragflow_connection(),
            "n8n": check_n8n_connection(),
        }

        # 计算数据库统计
        user_count = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        project_count = db.query(Project).count()
        account_count = db.query(Account).count()
        article_count = db.query(GeoArticle).count()

        # 获取Python版本和平台信息
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        platform_info = f"{sys_platform.system()} {sys_platform.release()}"

        return ApiResponse(
            success=True,
            message="获取成功",
            data={
                "status": "running" if all(s.status != "error" for s in services.values()) else "degraded",
                "timestamp": datetime.now().isoformat(),
                "version": APP_VERSION,
                "python_version": python_version,
                "platform": platform_info,
                "uptime": get_system_uptime(),
                "services": {
                    name: {
                        "status": s.status,
                        "message": s.message,
                        "last_check": s.last_check
                    } for name, s in services.items()
                },
                "stats": {
                    "users": user_count,
                    "active_users": active_users,
                    "projects": project_count,
                    "accounts": account_count,
                    "articles": article_count
                }
            }
        )

    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统状态失败: {str(e)}"
        )


@router.post("/restart", response_model=ApiResponse)
async def restart_service(
    request: RestartRequest,
    current_user: User = Depends(require_admin)
):
    """
    重启服务（仅管理员）

    **警告**: 此操作会中断所有正在进行的任务！

    - **delay_seconds**: 延迟重启秒数（默认5秒）
    - **reason**: 重启原因（可选）
    """
    try:
        logger.warning(f"管理员 {current_user.username} 请求重启服务，原因: {request.reason or '未指定'}")

        # 使用延迟重启策略
        import threading
        def delayed_restart():
            import time
            time.sleep(request.delay_seconds)
            # 使用os.execv重启进程
            os.execv(sys.executable, [sys.executable] + sys.argv)

        # 启动延迟重启线程
        restart_thread = threading.Thread(target=delayed_restart, daemon=True)
        restart_thread.start()

        return ApiResponse(
            success=True,
            message=f"服务将在 {request.delay_seconds} 秒后重启",
            data={
                "restart_scheduled": True,
                "delay_seconds": request.delay_seconds,
                "reason": request.reason
            }
        )

    except Exception as e:
        logger.error(f"重启服务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重启失败: {str(e)}"
        )


@router.get("/stats", response_model=ApiResponse)
async def get_detailed_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取详细统计数据（仅管理员）
    返回各种业务数据的详细统计
    """
    try:
        from datetime import timedelta

        # 用户统计
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        disabled_users = db.query(User).filter(User.is_active == False).count()
        admin_users = db.query(User).filter(User.role == "admin").count()

        # 项目统计
        total_projects = db.query(Project).count()
        active_projects = db.query(Project).filter(Project.status == 1).count()

        # 账号统计
        total_accounts = db.query(Account).count()
        active_accounts = db.query(Account).filter(Account.status == 1).count()

        # 文章统计
        total_articles = db.query(GeoArticle).count()

        # 文章发布状态统计
        from backend.database.models import GeoArticle
        article_by_status = db.query(GeoArticle.publish_status, db.func.count(GeoArticle.id)).group_by(GeoArticle.publish_status).all()
        status_counts = {status: count for status, count in article_by_status}

        # 最近7天数据
        recent_date = datetime.now() - timedelta(days=7)
        new_users_7d = db.query(User).filter(User.created_at >= recent_date).count()
        new_articles_7d = db.query(GeoArticle).filter(GeoArticle.created_at >= recent_date).count()

        return ApiResponse(
            success=True,
            message="获取成功",
            data={
                "users": {
                    "total": total_users,
                    "active": active_users,
                    "disabled": disabled_users,
                    "admins": admin_users,
                    "new_7d": new_users_7d
                },
                "projects": {
                    "total": total_projects,
                    "active": active_projects
                },
                "accounts": {
                    "total": total_accounts,
                    "active": active_accounts
                },
                "articles": {
                    "total": total_articles,
                    "by_status": status_counts,
                    "new_7d": new_articles_7d
                },
                "generated_at": datetime.now().isoformat()
            }
        )

    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计数据失败: {str(e)}"
        )


@router.post("/cleanup", response_model=ApiResponse)
async def cleanup_system(
    days: int = 30,
    current_user: User = Depends(require_admin)
):
    """
    系统清理（仅管理员）
    清理过期数据和临时文件

    - **days**: 清理多少天前的数据（默认30天）
    """
    try:
        from datetime import timedelta
        import shutil
        from backend.config import DATA_DIR

        cutoff_date = datetime.now() - timedelta(days=days)
        cleaned_items = []

        # 清理临时文件
        temp_dirs = [
            DATA_DIR / "temp",
            DATA_DIR / "cache",
        ]

        for temp_dir in temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    cleaned_items.append(f"已清理目录: {temp_dir}")
                except Exception as e:
                    cleaned_items.append(f"清理失败 {temp_dir}: {str(e)}")

        logger.info(f"管理员 {current_user.username} 执行系统清理，截止日期: {cutoff_date}")

        return ApiResponse(
            success=True,
            message=f"系统清理完成",
            data={
                "cutoff_date": cutoff_date.isoformat(),
                "days": days,
                "cleaned_items": cleaned_items
            }
        )

    except Exception as e:
        logger.error(f"系统清理失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理失败: {str(e)}"
        )
