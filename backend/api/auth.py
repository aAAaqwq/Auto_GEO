# -*- coding: utf-8 -*-
"""
授权相关的API端点
处理AI平台的授权流程
"""

import time

from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List
from loguru import logger

import bcrypt

from backend.database.models import User, Project
from backend.database import get_db
from backend.services.auth_service import auth_service
from backend.services.session_manager import secure_session_manager

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    responses={404: {"description": "Not found"}},
)


from pydantic import BaseModel


class AuthStartFlowRequest(BaseModel):
    user_id: int
    project_id: int
    platforms: List[str]


@router.post("/start-flow")
async def start_auth_flow(request: Request, db: Session = Depends(get_db)):
    """
    开始授权流程

    Args:
        request: Request对象
        db: 数据库会话

    Returns:
        授权流程信息
    """
    try:
        # 手动解析参数，避免 Pydantic 422 错误，并打印日志
        try:
            body = await request.json()
            logger.info(f"收到授权请求数据: {body}")
        except Exception as e:
            logger.error(f"解析请求体失败: {e}")
            raise HTTPException(status_code=400, detail="无效的 JSON 数据")

        user_id = body.get("user_id")
        project_id = body.get("project_id")
        platforms = body.get("platforms")

        # 兼容性处理：如果前端传了 None，默认设为 1
        if user_id is None:
            user_id = 1
            logger.warning("user_id 为空，使用默认值 1")

        if project_id is None:
            project_id = 1
            logger.warning("project_id 为空，使用默认值 1")

        # 简单的参数校验
        if user_id is None or project_id is None:
            error_msg = f"缺少 user_id 或 project_id. 收到数据: {body}"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

        if not platforms or not isinstance(platforms, list):
            raise HTTPException(status_code=400, detail="platforms 必须是非空列表")

        # 宽松验证：如果用户不存在，创建默认用户
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            # 创建默认用户
            default_password = bcrypt.hashpw("autogeo123".encode(), bcrypt.gensalt()).decode()
            user = User(
                id=user_id,
                username=f"user_{user_id}",
                email=f"user_{user_id}@example.com",
                password_hash=default_password,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 宽松验证：如果项目不存在，创建默认项目
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.info(f"项目 {project_id} 不存在，准备创建默认项目")
            try:
                # 创建默认项目
                # 注意：Project 模型不需要 user_id
                project = Project(id=project_id, name=f"默认项目_{project_id}", company_name=f"默认公司_{project_id}")
                db.add(project)
                db.commit()
                db.refresh(project)
                logger.info(f"默认项目 {project_id} 创建成功")
            except Exception as e:
                logger.error(f"创建默认项目失败: {e}")
                # 如果是 TypeError，尝试打印更多信息
                if isinstance(e, TypeError):
                    logger.error(f"TypeError 详情: {str(e)}")
                raise HTTPException(status_code=500, detail=f"创建默认项目失败: {str(e)}")

        # 开始授权流程
        result = await auth_service.start_auth_flow(user_id=user_id, project_id=project_id, platforms=platforms)

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "开始授权流程失败"),
                headers={"X-Error-Code": result.get("error_code", "UNKNOWN_ERROR")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"授权流程异常: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/status/{auth_session_id}")
async def get_auth_status(auth_session_id: str):
    """
    获取授权状态

    Args:
        auth_session_id: 授权会话ID

    Returns:
        授权状态
    """
    try:
        result = await auth_service.get_auth_status(auth_session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=404,
                detail=result.get("error", "授权会话不存在"),
                headers={"X-Error-Code": result.get("error_code", "SESSION_NOT_FOUND")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/start-platform/{auth_session_id}")
async def start_platform_auth(auth_session_id: str, platform: str = Query(..., description="平台标识")):
    """
    开始单个平台的授权

    Args:
        auth_session_id: 授权会话ID
        platform: 平台标识

    Returns:
        授权URL和状态
    """
    try:
        result = await auth_service.start_platform_auth(auth_session_id=auth_session_id, platform=platform)

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "开始平台授权失败"),
                headers={"X-Error-Code": result.get("error_code", "INTERNAL_ERROR")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/complete-platform/{auth_session_id}")
async def complete_platform_auth(auth_session_id: str, platform: str = Query(..., description="平台标识")):
    """
    完成平台授权

    Args:
        auth_session_id: 授权会话ID
        platform: 平台标识

    Returns:
        授权结果
    """
    try:
        result = await auth_service.complete_platform_auth(auth_session_id=auth_session_id, platform=platform)

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "完成平台授权失败"),
                headers={"X-Error-Code": result.get("error_code", "INTERNAL_ERROR")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/cancel/{auth_session_id}")
async def cancel_auth_flow(auth_session_id: str):
    """
    取消授权流程

    Args:
        auth_session_id: 授权会话ID

    Returns:
        取消结果
    """
    try:
        result = await auth_service.cancel_auth_flow(auth_session_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "取消授权流程失败"),
                headers={"X-Error-Code": result.get("error_code", "INTERNAL_ERROR")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/sessions")
async def list_sessions(
    user_id: int = Query(..., description="用户ID"), project_id: int = Query(None, description="项目ID")
):
    """
    列出用户/项目的所有会话

    Args:
        user_id: 用户ID
        project_id: 项目ID（可选）

    Returns:
        会话列表
    """
    try:
        result = await secure_session_manager.list_sessions(user_id=user_id, project_id=project_id)

        return JSONResponse(content={"success": True, "data": result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/session/status")
async def get_session_status(
    user_id: int = Query(..., description="用户ID"),
    project_id: int = Query(..., description="项目ID"),
    platform: str = Query(..., description="平台标识"),
    fast: bool = Query(False, description="是否快速检查（仅检查文件存在性）"),
):
    """
    获取单个平台的会话状态

    Args:
        user_id: 用户ID
        project_id: 项目ID
        platform: 平台标识
        fast: 是否快速检查

    Returns:
        会话状态详情
    """
    try:
        if fast:
            result = await secure_session_manager.get_session_status_fast(
                user_id=user_id, project_id=project_id, platform=platform
            )
        else:
            result = await secure_session_manager.get_session_status(
                user_id=user_id, project_id=project_id, platform=platform
            )

        return JSONResponse(content={"success": True, "data": result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.delete("/session")
async def delete_session(
    user_id: int = Query(..., description="用户ID"),
    project_id: int = Query(..., description="项目ID"),
    platform: str = Query(..., description="平台标识"),
):
    """
    删除会话

    Args:
        user_id: 用户ID
        project_id: 项目ID
        platform: 平台标识

    Returns:
        删除结果
    """
    try:
        result = await secure_session_manager.delete_session(user_id=user_id, project_id=project_id, platform=platform)

        if not result:
            raise HTTPException(status_code=400, detail="删除会话失败")

        return JSONResponse(content={"success": True, "message": "会话删除成功"})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


class SyncCookiesRequest(BaseModel):
    user_id: int = 1
    project_id: int = 1
    platform: str
    cookies: list = []
    local_storage: dict = {}
    fingerprint: dict = {}


@router.post("/sync-cookies")
async def sync_cookies_from_extension(request: SyncCookiesRequest):
    """
    接收浏览器扩展同步的 Cookie + LocalStorage + 指纹数据

    浏览器扩展通过 chrome.cookies API 获取所有 Cookie（含 HttpOnly），
    并通过此接口发送到后端加密存储。
    """
    try:
        result = await secure_session_manager.sync_cookies_from_extension(
            user_id=request.user_id,
            project_id=request.project_id,
            platform=request.platform,
            cookies=request.cookies,
            local_storage=request.local_storage,
            fingerprint=request.fingerprint,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "同步失败"),
                headers={"X-Error-Code": result.get("error_code", "SYNC_FAILED")},
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cookie同步异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


# 全局存储：扩展 ID（浏览器扩展启动时注册）
_extension_id: str = ""
# 同步请求：前端点"刷新状态"时设为 True，扩展轮询后设为 False
_sync_requested: bool = False
_sync_request_time: float = 0.0


@router.post("/register-extension")
async def register_extension_id(request: Request):
    """浏览器扩展启动时注册自己的 ID"""
    global _extension_id
    try:
        body = await request.json()
        _extension_id = body.get("extension_id", "")
        logger.info(f"扩展 ID 已注册: {_extension_id}")
        return JSONResponse(content={"success": True})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/extension-id")
async def get_extension_id():
    """前端查询已注册的扩展 ID"""
    return JSONResponse(content={"success": True, "extension_id": _extension_id})


@router.get("/request-sync")
async def request_sync():
    """前端点"刷新状态"时调用，设置同步请求标记"""
    global _sync_requested, _sync_request_time
    _sync_requested = True
    _sync_request_time = time.time()
    logger.info("收到前端同步请求")
    return JSONResponse(content={"success": True, "message": "同步请求已记录"})


@router.get("/sync-requests")
async def get_sync_requests(since: float = 0):
    """扩展轮询此接口，检查是否有待处理的同步请求"""
    global _sync_requested
    if _sync_requested and _sync_request_time > since:
        _sync_requested = False
        return JSONResponse(content={"sync_all": True, "time": _sync_request_time})
    return JSONResponse(content={"sync_all": False})


@router.post("/cleanup")
async def cleanup_auth_sessions():
    """
    清理过期的授权会话

    Returns:
        清理结果
    """
    try:
        await auth_service.cleanup_expired_sessions()

        return JSONResponse(content={"success": True, "message": "过期会话清理完成"})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
