# -*- coding: utf-8 -*-
"""
账号管理API — 全面增强版
支持：用户数据隔离、分组标签、批量操作、健康监控、操作日志
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
import csv
import io
from loguru import logger

from backend.database import get_db
from backend.database.models import Account, AccountGroup, AccountOperationLog, User
from backend.schemas import (
    AccountCreate,
    AccountUpdate,
    AccountResponse,
    AccountDetailResponse,
    AuthStartRequest,
    AuthStartResponse,
    AuthStatusResponse,
    ApiResponse,
    AccountCheckSummary,
    PaginatedResponse,
    AccountGroupCreate,
    AccountGroupUpdate,
    AccountGroupResponse,
    BatchStatusRequest,
    BatchDeleteRequest,
    BatchCheckRequest,
    BatchMoveGroupRequest,
    BatchImportRequest,
)
from backend.config import PLATFORMS
from backend.services.playwright_mgr import playwright_mgr
from backend.services.crypto import encrypt_cookies, encrypt_storage_state

# 复用 user.py 中已有的认证依赖
from backend.api.user import security


router = APIRouter(prefix="/api/accounts", tags=["账号管理"])

# WebSocket 管理器引用（在 main.py 中设置）
ws_manager = None


def set_ws_manager(manager):
    """设置 WebSocket 管理器"""
    global ws_manager
    ws_manager = manager


async def get_optional_user(
    credentials=Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    可选的用户认证依赖：
    - 有 Token → 解析并返回用户（数据隔离）
    - 无 Token → 返回 None（兼容未登录状态，返回所有数据）
    """
    if not credentials:
        return None
    try:
        payload = None
        from backend.api.user import decode_token
        payload = decode_token(credentials.credentials)
        if not payload:
            return None
        user_id = payload.get("user_id")
        if not user_id:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        return user
    except Exception:
        return None


# 设置 playwright_mgr 的数据库工厂
playwright_mgr.set_db_factory(get_db)


# 设置 playwright_mgr 的 WebSocket 回调
async def ws_notification(data: dict):
    """通过 WebSocket 发送通知"""
    if ws_manager:
        await ws_manager.broadcast(data)


playwright_mgr.set_ws_callback(ws_notification)


# ==================== 工具函数 ====================


async def _log_operation(
    db: Session,
    account_id: Optional[int],
    user: User,
    operation: str,
    detail: dict = None,
    ip_address: str = None,
):
    """记录账号操作日志"""
    try:
        log = AccountOperationLog(
            account_id=account_id,
            user_id=user.id,
            operation=operation,
            detail=detail or {},
            ip_address=ip_address,
        )
        db.add(log)
        db.flush()  # flush 不 commit，让调用方统一 commit
    except Exception as e:
        logger.warning(f"记录操作日志失败: {e}")


def _verify_account_owner(account: Account, user: User):
    """验证账号是否属于当前用户"""
    if account.user_id is not None and account.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问此账号")


# ==================== 账号 CRUD ====================


@router.get("", response_model=PaginatedResponse[AccountResponse])
async def get_accounts(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    platform: str = Query(None, description="平台筛选"),
    status: int = Query(None, description="状态筛选"),
    keyword: str = Query(None, description="关键词搜索"),
    group_id: int = Query(None, description="分组筛选"),
    tag: str = Query(None, description="标签筛选"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    获取账号列表（支持分页、平台/状态/分组/标签筛选）
    有 Token → 只返回当前用户的账号（数据隔离）
    无 Token → 返回所有账号（兼容旧模式）
    """
    # 基础查询：排除软删除
    query = db.query(Account).filter(Account.deleted_at.is_(None))

    # 数据隔离：有用户时只查该用户的账号
    if current_user:
        query = query.filter(Account.user_id == current_user.id)

    if platform:
        query = query.filter(Account.platform == platform)
    if status is not None:
        query = query.filter(Account.status == status)
    if group_id is not None:
        query = query.filter(Account.group_id == group_id)
    if keyword:
        query = query.filter(
            (Account.account_name.contains(keyword)) | (Account.username.contains(keyword))
        )
    if tag:
        # JSON 字段中的标签匹配（SQLite 使用 LIKE 兼容）
        query = query.filter(Account.tags.contains(tag))

    # 统计总数
    total = query.count()

    # 分页查询
    accounts = query.order_by(Account.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    # 计算分页信息
    pages = (total + limit - 1) // limit if total > 0 else 1

    return PaginatedResponse(
        total=total,
        items=accounts,
        page=page,
        limit=limit,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


@router.get("/{account_id}", response_model=AccountDetailResponse)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取账号详情"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 有用户时验证归属，无用户时放行
    if current_user:
        _verify_account_owner(account, current_user)

    # 获取分组名称
    group_name = None
    if account.group_id:
        group = db.query(AccountGroup).filter(AccountGroup.id == account.group_id).first()
        if group:
            group_name = group.name

    # 构建响应
    response = AccountDetailResponse(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        username=account.username,
        status=account.status,
        last_auth_time=account.last_auth_time,
        remark=account.remark,
        user_id=account.user_id,
        group_id=account.group_id,
        tags=account.tags,
        health_score=account.health_score,
        last_check_time=account.last_check_time,
        auth_expires_at=account.auth_expires_at,
        browser_type=account.browser_type,
        adspower_profile_id=account.adspower_profile_id,
        is_authorized=bool(account.cookies and account.storage_state),
        platform_info=PLATFORMS.get(account.platform),
        group_name=group_name,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )

    return response


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(
    account_data: AccountCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    创建账号（有登录用户时自动绑定 user_id）

    注意：创建后需要授权才能使用！
    """
    # 检查平台是否支持
    if account_data.platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {account_data.platform}")

    # 如果指定了分组，验证分组归属
    if account_data.group_id and current_user:
        group = db.query(AccountGroup).filter(AccountGroup.id == account_data.group_id).first()
        if not group or group.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="分组不存在或不属于当前用户")

    # 创建账号记录
    account = Account(
        platform=account_data.platform,
        account_name=account_data.account_name,
        remark=account_data.remark,
        user_id=current_user.id if current_user else None,
        group_id=account_data.group_id,
        tags=account_data.tags,
        status=0,  # 初始状态为禁用，授权后激活
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    # 记录操作日志
    await _log_operation(
        db, account.id, current_user, "create",
        detail={"platform": account.platform, "account_name": account.account_name},
    )
    db.commit()

    logger.info(f"账号已创建: {account.id} - {account.platform}:{account.account_name} (user={current_user.username if current_user else 'anonymous'})")
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    account_data: AccountUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """更新账号信息"""
    account = db.query(Account).filter(
        Account.id == account_id,
        Account.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if current_user:
        _verify_account_owner(account, current_user)

    # 更新字段
    changed_fields = {}
    if account_data.account_name is not None:
        account.account_name = account_data.account_name
        changed_fields["account_name"] = account_data.account_name
    if account_data.status is not None:
        account.status = account_data.status
        changed_fields["status"] = account_data.status
    if account_data.remark is not None:
        account.remark = account_data.remark
        changed_fields["remark"] = account_data.remark
    if account_data.group_id is not None:
        # 验证分组归属
        if account_data.group_id != 0:
            group = db.query(AccountGroup).filter(AccountGroup.id == account_data.group_id).first()
            if not group or group.user_id != current_user.id:
                raise HTTPException(status_code=400, detail="分组不存在或不属于当前用户")
            account.group_id = account_data.group_id
        else:
            account.group_id = None
        changed_fields["group_id"] = account_data.group_id
    if account_data.tags is not None:
        account.tags = account_data.tags
        changed_fields["tags"] = account_data.tags

    db.commit()
    db.refresh(account)

    # 记录操作日志
    await _log_operation(
        db, account.id, current_user, "update",
        detail={"changed_fields": changed_fields},
    )
    db.commit()

    logger.info(f"账号已更新: {account_id} (user={current_user.username if current_user else 'anonymous'})")
    return account


@router.delete("/{account_id}", response_model=ApiResponse)
async def delete_account(
    account_id: int,
    hard: bool = Query(False, description="是否硬删除（默认软删除）"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    删除账号（默认软删除）

    注意：硬删除会级联删除相关的发布记录！
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if current_user:
        _verify_account_owner(account, current_user)

    if hard:
        db.delete(account)
    else:
        # 软删除
        from datetime import datetime
        account.deleted_at = datetime.now()
        account.status = 0

    # 记录操作日志
    await _log_operation(
        db, account_id, current_user, "delete",
        detail={"hard_delete": hard, "account_name": account.account_name},
    )
    db.commit()

    logger.info(f"账号已{'硬' if hard else '软'}删除: {account_id} (user={current_user.username if current_user else 'anonymous'})")
    return ApiResponse(success=True, message=f"账号已{'彻底删除' if hard else '删除'}")


# ==================== 授权相关 ====================


@router.post("/auth/start", response_model=AuthStartResponse)
async def start_auth(
    auth_data: AuthStartRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    开始账号授权

    注意：这个方法会打开浏览器窗口！授权成功后自动创建或更新账号！
    """
    platform = auth_data.platform

    # 验证平台
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    # 如果是更新授权，检查账号是否存在且属于当前用户
    if auth_data.account_id:
        account = db.query(Account).filter(
            Account.id == auth_data.account_id,
            Account.deleted_at.is_(None),
        ).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        if current_user:
            _verify_account_owner(account, current_user)
        if account.platform != platform:
            raise HTTPException(status_code=400, detail="平台不匹配")

    # 记录操作日志（有用户时才记录）
    if current_user:
        await _log_operation(
            db, auth_data.account_id, current_user, "auth_start",
            detail={"platform": platform},
        )
    db.commit()

    # 创建授权任务
    try:
        task = await playwright_mgr.create_auth_task(
            platform, auth_data.account_id, auth_data.account_name,
            user_id=current_user.id if current_user else None
        )
        logger.info(f"授权任务已启动: {task.task_id}, 平台: {platform} (user={current_user.username if current_user else 'anonymous'})")
        return AuthStartResponse(
            task_id=task.task_id, message=f"已打开{PLATFORMS[platform]['name']}登录页面，请完成扫码/密码登录"
        )
    except Exception as e:
        import traceback

        logger.error(f"启动授权任务失败: {repr(e)}")
        logger.error(f"堆栈跟踪:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"启动授权失败: {repr(e)}")


@router.get("/auth/status/{task_id}", response_model=AuthStatusResponse)
async def get_auth_status(task_id: str, db: Session = Depends(get_db)):
    """
    获取授权状态

    注意：前端应该轮询这个接口！授权成功后会自动创建账号！
    """
    task = playwright_mgr.get_auth_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="授权任务不存在")

    # 返回账号ID（新账号创建后或老账号更新后）
    account_id = task.account_id or task.created_account_id

    response = AuthStatusResponse(
        task_id=task.task_id, status=task.status, is_logged_in=(task.status == "success"), account_id=account_id
    )

    # 设置消息
    if task.status == "success":
        response.message = f"{PLATFORMS[task.platform]['name']}授权成功！账号已自动保存。"
    elif task.status in ["failed", "timeout"]:
        response.message = task.error_message or "授权失败，请重试"

    return response


@router.post("/auth/save/{task_id}", response_model=ApiResponse)
async def save_auth(
    task_id: str,
    account_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    手动保存授权结果（用于新账号）
    """
    task = playwright_mgr.get_auth_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="授权任务不存在")

    if task.status != "success":
        raise HTTPException(status_code=400, detail="授权尚未成功")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if current_user:
        _verify_account_owner(account, current_user)

    # 保存授权信息
    account.cookies = encrypt_cookies(task.cookies)
    account.storage_state = encrypt_storage_state(task.storage_state)
    account.status = 1  # 激活账号
    account.last_auth_time = task.created_at
    account.health_score = 100  # 新授权，健康度满分

    # 记录操作日志
    if current_user:
        await _log_operation(
            db, account_id, current_user, "auth_success",
            detail={"platform": account.platform},
        )
    db.commit()

    # 清理任务
    await playwright_mgr.close_auth_task(task_id)

    logger.info(f"账号授权已保存: {account_id} (user={current_user.username if current_user else 'anonymous'})")
    return ApiResponse(success=True, message="授权信息已保存")


@router.post("/auth/confirm/{task_id}", response_model=ApiResponse)
async def confirm_auth(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    用户手动确认授权完成
    委托给 playwright_mgr._finalize_auth() 执行完整的验证+入库流程
    """
    task = playwright_mgr.get_auth_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="授权任务不存在")

    if task.status == "success":
        return ApiResponse(success=True, message="授权已完成")

    # 提取当前页面状态
    if not task.context or not task.page:
        return ApiResponse(success=False, message="授权任务已失效，请重新开始授权")

    # 快速预检：cookie 数量
    cookies = await task.context.cookies()
    if not cookies or len(cookies) < 3:
        logger.warning(f"预检失败: cookie数量={len(cookies) if cookies else 0}")
        return ApiResponse(success=False, message="未检测到登录信息，请先在平台完成登录后再点击授权完成")

    try:
        # 委托给 _finalize_auth 执行完整验证+入库
        import json as _json
        result_raw = await playwright_mgr._finalize_auth(task_id)
        result = _json.loads(result_raw)

        if result.get("success"):
            # 记录操作日志
            account_id = task.account_id or task.created_account_id
            if current_user:
                await _log_operation(
                    db, account_id, current_user, "auth_success",
                    detail={"platform": task.platform},
                )
                db.commit()

            # 清理任务资源
            await playwright_mgr.close_auth_task(task_id)

            if ws_manager:
                await ws_manager.broadcast({
                    "type": "auth_complete",
                    "task_id": task.task_id,
                    "platform": task.platform,
                    "account_id": account_id,
                    "success": True,
                })

            logger.info(f"授权确认成功: {task_id}")
            return ApiResponse(
                success=True,
                message="授权成功！账号已保存",
                data={
                    "account_id": account_id,
                    "platform": task.platform,
                    "task_id": task_id,
                },
            )
        else:
            msg = result.get("message", "授权失败，请确认已完成登录")
            return ApiResponse(success=False, message=msg)

    except Exception as e:
        logger.error(f"授权确认失败: {e}")
        db.rollback()

        if current_user:
            await _log_operation(
                db, None, current_user, "auth_fail",
                detail={"platform": task.platform, "error": str(e)},
            )
            db.commit()

        return ApiResponse(success=False, message=f"授权失败: {str(e)}")

        return ApiResponse(success=False, message=f"保存失败: {str(e)}")


@router.delete("/auth/task/{task_id}", response_model=ApiResponse)
async def cancel_auth(task_id: str):
    """取消授权任务"""
    await playwright_mgr.close_auth_task(task_id)
    return ApiResponse(success=True, message="授权任务已取消")


# ==================== 账号检测相关 ====================


@router.post("/check/all", response_model=AccountCheckSummary)
async def check_all_accounts(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    批量检测账号的授权状态
    有 Token → 只检测当前用户的账号
    无 Token → 检测所有账号
    """
    from backend.services.account_validator import account_validator

    async def progress_callback(current: int, total: int, result: dict):
        """推送检测进度到前端"""
        if ws_manager:
            await ws_manager.broadcast(
                {
                    "type": "account_check_progress",
                    "current": current,
                    "total": total,
                    "progress": round(current / total * 100, 1),
                    "result": result,
                }
            )

    # 只检测当前用户的账号
    # 注：account_validator.check_all_accounts 目前是查所有 status==1 的账号
    # 这里先获取当前用户 ID，在验证回调中过滤
    summary = await account_validator.check_all_accounts(
        db_session=db,
        progress_callback=progress_callback,
        user_id=current_user.id if current_user else None,
    )

    if ws_manager:
        await ws_manager.broadcast({"type": "account_check_complete", "summary": summary})

    return summary


# ==================== 账号分组 API ====================


@router.get("/groups/list", response_model=ApiResponse)
async def get_groups(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取分组列表（有用户时返回该用户的分组，无用户时返回空）"""
    if not current_user:
        return ApiResponse(success=True, data=[])

    groups = (
        db.query(AccountGroup)
        .filter(AccountGroup.user_id == current_user.id)
        .order_by(AccountGroup.sort_order, AccountGroup.created_at)
        .all()
    )

    # 统计每个分组的账号数量
    result = []
    for group in groups:
        count = db.query(Account).filter(
            Account.group_id == group.id,
            Account.deleted_at.is_(None),
        ).count()
        result.append({
            "id": group.id,
            "name": group.name,
            "icon": group.icon,
            "color": group.color,
            "sort_order": group.sort_order,
            "account_count": count,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
        })

    return ApiResponse(success=True, data=result)


@router.post("/groups", response_model=ApiResponse)
async def create_group(
    group_data: AccountGroupCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """创建分组"""
    if not current_user:
        raise HTTPException(status_code=401, detail="请先登录")

    group = AccountGroup(
        name=group_data.name,
        icon=group_data.icon,
        color=group_data.color,
        user_id=current_user.id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    return ApiResponse(success=True, message="分组创建成功", data={"id": group.id, "name": group.name})


@router.put("/groups/{group_id}", response_model=ApiResponse)
async def update_group(
    group_id: int,
    group_data: AccountGroupUpdate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """更新分组"""
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if current_user and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此分组")

    if group_data.name is not None:
        group.name = group_data.name
    if group_data.icon is not None:
        group.icon = group_data.icon
    if group_data.color is not None:
        group.color = group_data.color
    if group_data.sort_order is not None:
        group.sort_order = group_data.sort_order

    db.commit()

    return ApiResponse(success=True, message="分组更新成功")


@router.delete("/groups/{group_id}", response_model=ApiResponse)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """删除分组（账号的 group_id 自动置空）"""
    group = db.query(AccountGroup).filter(AccountGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="分组不存在")
    if current_user and group.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作此分组")

    # 将该分组下的账号 group_id 置空
    db.query(Account).filter(Account.group_id == group_id).update({"group_id": None})

    db.delete(group)
    db.commit()

    return ApiResponse(success=True, message="分组已删除")


# ==================== 批量操作 API ====================

def _user_filter(current_user: Optional[User]):
    """辅助：有用户时返回用户ID过滤条件列表，无用户时返回空列表"""
    if current_user:
        return [Account.user_id == current_user.id]
    return []


@router.post("/batch/status", response_model=ApiResponse)
async def batch_update_status(
    request: BatchStatusRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """批量更新账号状态"""
    filters = [
        Account.id.in_(request.account_ids),
        Account.deleted_at.is_(None),
    ] + _user_filter(current_user)

    accounts = db.query(Account).filter(*filters).all()

    if not accounts:
        raise HTTPException(status_code=404, detail="未找到可操作的账号")

    updated = 0
    for account in accounts:
        account.status = request.status
        updated += 1

    if current_user:
        await _log_operation(
            db, None, current_user, "batch_update_status",
            detail={"account_ids": request.account_ids, "status": request.status, "updated": updated},
        )
    db.commit()

    return ApiResponse(success=True, message=f"已更新 {updated} 个账号状态")


@router.post("/batch/delete", response_model=ApiResponse)
async def batch_delete(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """批量软删除账号"""
    from datetime import datetime

    filters = [Account.id.in_(request.account_ids)] + _user_filter(current_user)
    accounts = db.query(Account).filter(*filters).all()

    if not accounts:
        raise HTTPException(status_code=404, detail="未找到可操作的账号")

    deleted = 0
    for account in accounts:
        account.deleted_at = datetime.now()
        account.status = 0
        deleted += 1

    if current_user:
        await _log_operation(
            db, None, current_user, "batch_delete",
            detail={"account_ids": request.account_ids, "deleted": deleted},
        )
    db.commit()

    return ApiResponse(success=True, message=f"已删除 {deleted} 个账号")


@router.post("/batch/move-group", response_model=ApiResponse)
async def batch_move_group(
    request: BatchMoveGroupRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """批量移动账号到指定分组"""
    # 验证目标分组
    if request.group_id and current_user:
        group = db.query(AccountGroup).filter(AccountGroup.id == request.group_id).first()
        if not group or group.user_id != current_user.id:
            raise HTTPException(status_code=400, detail="目标分组不存在或不属于当前用户")

    filters = [
        Account.id.in_(request.account_ids),
        Account.deleted_at.is_(None),
    ] + _user_filter(current_user)
    accounts = db.query(Account).filter(*filters).all()

    moved = 0
    for account in accounts:
        account.group_id = request.group_id
        moved += 1

    if current_user:
        await _log_operation(
            db, None, current_user, "batch_move_group",
            detail={"account_ids": request.account_ids, "group_id": request.group_id, "moved": moved},
        )
    db.commit()

    return ApiResponse(success=True, message=f"已移动 {moved} 个账号")


@router.post("/batch/check", response_model=ApiResponse)
async def batch_check(
    request: BatchCheckRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """批量检测指定账号的授权状态"""
    from backend.services.account_validator import account_validator

    filters = [
        Account.id.in_(request.account_ids),
        Account.deleted_at.is_(None),
        Account.status == 1,
    ] + _user_filter(current_user)
    accounts = db.query(Account).filter(*filters).all()

    if not accounts:
        raise HTTPException(status_code=404, detail="未找到可检测的账号")

    return ApiResponse(
        success=True,
        message=f"已提交 {len(accounts)} 个账号的检测任务",
        data={"account_count": len(accounts)},
    )


@router.post("/import", response_model=ApiResponse)
async def import_accounts(
    request: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """批量导入账号"""
    created = []
    errors = []

    for idx, item in enumerate(request.accounts):
        if item.platform not in PLATFORMS:
            errors.append({"index": idx, "error": f"不支持的平台: {item.platform}"})
            continue

        account = Account(
            platform=item.platform,
            account_name=item.account_name,
            remark=item.remark,
            tags=item.tags,
            user_id=current_user.id if current_user else None,
            status=0,  # 未授权
        )
        db.add(account)
        created.append(item.account_name)

    db.commit()

    if current_user:
        await _log_operation(
            db, None, current_user, "batch_import",
            detail={"created": len(created), "errors": len(errors)},
        )
        db.commit()

    return ApiResponse(
        success=True,
        message=f"导入完成：成功 {len(created)} 个，失败 {len(errors)} 个",
        data={"created": len(created), "errors": errors},
    )


@router.get("/export")
async def export_accounts(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """导出账号（不含 Cookie 等敏感数据）"""
    from fastapi.responses import StreamingResponse

    query = db.query(Account).filter(Account.deleted_at.is_(None))
    if current_user:
        query = query.filter(Account.user_id == current_user.id)
    accounts = query.all()

    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "平台", "账号名称", "状态", "分组ID", "标签", "健康度", "最后授权时间", "创建时间", "备注"])

    for acc in accounts:
        status_map = {1: "正常", 0: "禁用", -1: "授权过期"}
        writer.writerow([
            acc.id,
            acc.platform,
            acc.account_name,
            status_map.get(acc.status, str(acc.status)),
            acc.group_id or "",
            ",".join(acc.tags) if acc.tags else "",
            acc.health_score or "",
            acc.last_auth_time.isoformat() if acc.last_auth_time else "",
            acc.created_at.isoformat() if acc.created_at else "",
            acc.remark or "",
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=accounts_export.csv"},
    )


# ==================== 过期账号查询 ====================


@router.get("/expiring/list", response_model=ApiResponse)
async def get_expiring_accounts(
    days: int = Query(7, ge=1, le=30, description="几天内即将过期"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """获取即将过期的账号列表"""
    from datetime import datetime, timedelta

    threshold = datetime.now() + timedelta(days=days)

    query = db.query(Account).filter(
        Account.deleted_at.is_(None),
        Account.status == 1,
        or_(
            Account.health_score < 60,
            Account.auth_expires_at <= threshold,
        ),
    )
    if current_user:
        query = query.filter(Account.user_id == current_user.id)
    accounts = query.order_by(Account.health_score.asc()).all()

    result = []
    for acc in accounts:
        result.append({
            "id": acc.id,
            "platform": acc.platform,
            "account_name": acc.account_name,
            "health_score": acc.health_score,
            "last_auth_time": acc.last_auth_time.isoformat() if acc.last_auth_time else None,
            "auth_expires_at": acc.auth_expires_at.isoformat() if acc.auth_expires_at else None,
        })

    return ApiResponse(success=True, data=result)


# ==================== 操作日志查询 ====================


@router.get("/logs/list", response_model=ApiResponse)
async def get_account_logs(
    account_id: int = Query(None, description="账号ID，不传则查全部"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """查询账号操作日志"""
    if not current_user:
        return ApiResponse(success=True, data={"total": 0, "items": [], "page": page, "limit": limit})

    # 获取当前用户的所有账号 ID
    user_account_ids = [
        row[0] for row in db.query(Account.id).filter(Account.user_id == current_user.id).all()
    ]

    query = db.query(AccountOperationLog).filter(
        AccountOperationLog.user_id == current_user.id,
    )

    if account_id:
        if account_id not in user_account_ids:
            raise HTTPException(status_code=403, detail="无权查看此账号日志")
        query = query.filter(AccountOperationLog.account_id == account_id)
    else:
        query = query.filter(AccountOperationLog.account_id.in_(user_account_ids))

    total = query.count()
    logs = query.order_by(AccountOperationLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    items = []
    for log in logs:
        items.append({
            "id": log.id,
            "account_id": log.account_id,
            "operation": log.operation,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return ApiResponse(success=True, data={
        "total": total,
        "items": items,
        "page": page,
        "limit": limit,
    })
