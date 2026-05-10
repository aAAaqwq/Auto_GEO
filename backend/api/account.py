# -*- coding: utf-8 -*-
"""
账号管理API
写的API，简洁高效！
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models import Account
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
)
from backend.config import PLATFORMS
from backend.services.playwright_mgr import playwright_mgr
from backend.services.crypto import encrypt_cookies, encrypt_storage_state
from loguru import logger


router = APIRouter(prefix="/api/accounts", tags=["账号管理"])

# WebSocket 管理器引用（在 main.py 中设置）
ws_manager = None


def set_ws_manager(manager):
    """设置 WebSocket 管理器"""
    global ws_manager
    ws_manager = manager


# 设置 playwright_mgr 的数据库工厂
playwright_mgr.set_db_factory(get_db)


# 设置 playwright_mgr 的 WebSocket 回调
async def ws_notification(data: dict):
    """通过 WebSocket 发送通知"""
    if ws_manager:
        await ws_manager.broadcast(data)


playwright_mgr.set_ws_callback(ws_notification)


@router.get("", response_model=PaginatedResponse[AccountResponse])
async def get_accounts(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    platform: str = Query(None, description="平台筛选"),
    status: int = Query(None, description="状态筛选"),
    keyword: str = Query(None, description="关键词搜索"),
    db: Session = Depends(get_db),
):
    """
    获取账号列表（支持分页）
    """
    query = db.query(Account)

    if platform:
        query = query.filter(Account.platform == platform)
    if status is not None:
        query = query.filter(Account.status == status)
    if keyword:
        query = query.filter(
            (Account.account_name.contains(keyword)) |
            (Account.username.contains(keyword))
        )

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
        has_prev=page > 1
    )


@router.get("/{account_id}", response_model=AccountDetailResponse)
async def get_account(account_id: int, db: Session = Depends(get_db)):
    """获取账号详情"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 构建响应
    response = AccountDetailResponse(
        id=account.id,
        platform=account.platform,
        account_name=account.account_name,
        username=account.username,
        status=account.status,
        last_auth_time=account.last_auth_time,
        created_at=account.created_at,
        updated_at=account.updated_at,
        remark=account.remark,
        is_authorized=bool(account.cookies and account.storage_state),
        platform_info=PLATFORMS.get(account.platform),
    )

    return response


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account(account_data: AccountCreate, db: Session = Depends(get_db)):
    """
    创建账号

    注意：创建后需要授权才能使用！
    """
    # 检查平台是否支持
    if account_data.platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {account_data.platform}")

    # 创建账号记录
    account = Account(
        platform=account_data.platform,
        account_name=account_data.account_name,
        remark=account_data.remark,
        status=0,  # 初始状态为禁用，授权后激活
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    logger.info(f"账号已创建: {account.id} - {account.platform}:{account.account_name}")
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(account_id: int, account_data: AccountUpdate, db: Session = Depends(get_db)):
    """更新账号信息"""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 更新字段
    if account_data.account_name is not None:
        account.account_name = account_data.account_name
    if account_data.status is not None:
        account.status = account_data.status
    if account_data.remark is not None:
        account.remark = account_data.remark

    db.commit()
    db.refresh(account)

    logger.info(f"账号已更新: {account_id}")
    return account


@router.delete("/{account_id}", response_model=ApiResponse)
async def delete_account(account_id: int, db: Session = Depends(get_db)):
    """
    删除账号

    注意：删除会级联删除相关的发布记录！
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    db.delete(account)
    db.commit()

    logger.info(f"账号已删除: {account_id}")
    return ApiResponse(success=True, message="账号已删除")


# ==================== 授权相关 ====================


@router.post("/auth/start", response_model=AuthStartResponse)
async def start_auth(auth_data: AuthStartRequest, db: Session = Depends(get_db)):
    """
    开始账号授权

    注意：这个方法会打开浏览器窗口！授权成功后自动创建或更新账号！
    """
    platform = auth_data.platform

    # 验证平台
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    # 如果是更新授权，检查账号是否存在
    if auth_data.account_id:
        account = db.query(Account).filter(Account.id == auth_data.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        if account.platform != platform:
            raise HTTPException(status_code=400, detail="平台不匹配")

    # 创建授权任务
    try:
        task = await playwright_mgr.create_auth_task(platform, auth_data.account_id, auth_data.account_name)
        logger.info(f"授权任务已启动: {task.task_id}, 平台: {platform}")
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
async def save_auth(task_id: str, account_id: int, db: Session = Depends(get_db)):
    """
    手动保存授权结果（用于新账号）

    注意：新账号授权完成后需要调用这个接口！
    """
    task = playwright_mgr.get_auth_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="授权任务不存在")

    if task.status != "success":
        raise HTTPException(status_code=400, detail="授权尚未成功")

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 保存授权信息
    account.cookies = encrypt_cookies(task.cookies)
    account.storage_state = encrypt_storage_state(task.storage_state)
    account.status = 1  # 激活账号
    account.last_auth_time = task.created_at
    db.commit()

    # 清理任务
    await playwright_mgr.close_auth_task(task_id)

    logger.info(f"账号授权已保存: {account_id}")
    return ApiResponse(success=True, message="授权信息已保存")


@router.post("/auth/confirm/{task_id}", response_model=ApiResponse)
async def confirm_auth(task_id: str, db: Session = Depends(get_db)):
    """
    用户手动确认授权完成

    提取当前浏览器的 cookie 和 storage！
    用户点击浏览器里的"授权完成"按钮后会调用这个接口。
    """
    task = playwright_mgr.get_auth_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="授权任务不存在")

    if task.status == "success":
        # 已经完成，直接返回成功
        return ApiResponse(success=True, message="授权已完成")

    # 提取当前页面状态
    if not task.context or not task.page:
        return ApiResponse(success=False, message="授权任务已失效，请重新开始授权")

    cookies = await task.context.cookies()
    storage_state = (
        await task.page.evaluate("""
        () => {
            return {
                localStorage: {...localStorage},
                sessionStorage: {...sessionStorage}
            };
        }
    """)
        or {}
    )

    # 验证是否真的登录了（简单检查：是否有有效cookie）
    if not cookies or len(cookies) < 3:
        logger.warning(f"Cookie验证失败: cookie数量={len(cookies) if cookies else 0}")
        logger.info(f"当前Cookie列表: {[c['name'] for c in cookies] if cookies else []}")
        return ApiResponse(success=False, message="未检测到登录信息，请先在平台完成登录后再点击授权完成")

    # 保存到数据库
    try:
        from backend.database.models import Account

        if task.account_id:
            # 更新现有账号
            account = db.query(Account).filter(Account.id == task.account_id).first()
            if account:
                account.cookies = encrypt_cookies(cookies)
                account.storage_state = encrypt_storage_state(storage_state)
                account.status = 1
                account.last_auth_time = task.created_at
                db.commit()
                task.account_id = account.id
                logger.info(f"账号授权已更新: {account.id}")
        else:
            # 创建新账号
            account_name = task.account_name or f"{PLATFORMS[task.platform]['name']}账号"
            account = Account(
                platform=task.platform,
                account_name=account_name,
                cookies=encrypt_cookies(cookies),
                storage_state=encrypt_storage_state(storage_state),
                status=1,
                last_auth_time=task.created_at,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            task.created_account_id = account.id
            logger.info(f"新账号已创建: {account.id}, 名称: {account_name}")

        # 更新任务状态
        task.status = "success"
        task.cookies = cookies
        task.storage_state = storage_state

        logger.info(f"授权确认成功: {task_id}")

        # 通过 WebSocket 通知前端
        if ws_manager:
            await ws_manager.broadcast(
                {
                    "type": "auth_complete",
                    "task_id": task.task_id,
                    "platform": task.platform,
                    "account_id": task.account_id or task.created_account_id,
                    "success": True,
                }
            )

        return ApiResponse(
            success=True,
            message="授权成功！账号已保存",
            data={
                "account_id": task.account_id or task.created_account_id,
                "platform": task.platform,
                "task_id": task_id,
            },
        )

    except Exception as e:
        logger.error(f"授权确认失败: {e}")
        db.rollback()
        return ApiResponse(success=False, message=f"保存失败: {str(e)}")


@router.delete("/auth/task/{task_id}", response_model=ApiResponse)
async def cancel_auth(task_id: str):
    """取消授权任务"""
    await playwright_mgr.close_auth_task(task_id)
    return ApiResponse(success=True, message="授权任务已取消")


# ==================== 账号检测相关 ====================


@router.post("/check/all", response_model=AccountCheckSummary)
async def check_all_accounts(db: Session = Depends(get_db)):
    """
    批量检测所有账号的授权状态
    通过WebSocket实时推送检测进度
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

    summary = await account_validator.check_all_accounts(db_session=db, progress_callback=progress_callback)

    if ws_manager:
        await ws_manager.broadcast({"type": "account_check_complete", "summary": summary})

    return summary
