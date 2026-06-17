# -*- coding: utf-8 -*-
"""
自动发布任务管理 API
实现后台任务队列管理系统
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from loguru import logger

from backend.database import get_db
from backend.database.models import (
    AutoPublishTask,
    AutoPublishRecord,
    Account,
    GeoArticle,
)
from backend.schemas import (
    ApiResponse,
    AutoPublishTaskCreate,
    AutoPublishTaskUpdate,
    AutoPublishTaskResponse,
    AutoPublishTaskDetailResponse,
    AutoPublishRecordResponse,
)
from backend.config import PLATFORMS


router = APIRouter(prefix="/api/auto-publish", tags=["自动发布任务管理"])


# ==================== 全局任务执行管理器 ====================


class AutoPublishTaskExecutor:
    """
    自动发布任务执行器
    管理后台任务的执行、重试和状态更新
    """

    def __init__(self):
        self._running_tasks: dict = {}  # task_id -> task_info

    def start_task(self, task_id: int):
        """标记任务开始执行"""
        self._running_tasks[task_id] = {
            "status": "running",
            "started_at": datetime.now(),
        }

    def complete_task(self, task_id: int, success: bool = True, error_msg: str = None):
        """标记任务完成"""
        if task_id in self._running_tasks:
            self._running_tasks[task_id]["status"] = "completed" if success else "failed"
            self._running_tasks[task_id]["completed_at"] = datetime.now()
            if error_msg:
                self._running_tasks[task_id]["error_msg"] = error_msg

    def is_task_running(self, task_id: int) -> bool:
        """检查任务是否正在运行"""
        return self._running_tasks.get(task_id, {}).get("status") == "running"


# 全局执行器实例
task_executor = AutoPublishTaskExecutor()


def get_playwright_mgr():
    """延迟导入，避免循环依赖"""
    from backend.services.playwright_mgr import playwright_mgr

    return playwright_mgr


def get_ws_manager():
    """获取WebSocket管理器"""
    from backend.api.publish import get_ws_manager

    return get_ws_manager()


# ==================== API接口 ====================


@router.get("/tasks", response_model=ApiResponse)
async def get_auto_publish_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤"),
    platform: Optional[str] = Query(None, description="平台过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    """
    获取自动发布任务列表

    用于展示用户创建的所有后台发布任务
    支持按状态和平台筛选
    """
    query = db.query(AutoPublishTask).order_by(AutoPublishTask.created_at.desc())

    if status:
        query = query.filter(AutoPublishTask.status == status)

    # 如果指定了平台筛选，需要关联账号表
    if platform:
        # 子查询：获取指定平台的所有账号ID
        platform_account_ids = db.query(Account.id).filter(Account.platform == platform, Account.status == 1).all()
        platform_account_ids = [acc[0] for acc in platform_account_ids]

        # 筛选包含指定平台账号的任务
        if platform_account_ids:
            # 使用JSON_OVERLAPS或contains筛选account_ids
            query = query.filter(AutoPublishTask.account_ids.op("&&")(platform_account_ids))
        else:
            # 如果该平台没有账号，返回空结果
            return ApiResponse(data={"total": 0, "items": []})

    total = query.count()
    tasks = query.offset(offset).limit(limit).all()

    # 转换为响应格式
    task_list = []
    for task in tasks:
        task_list.append(
            {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "article_ids": task.article_ids or [],
                "account_ids": task.account_ids or [],
                "status": task.status,
                "exec_type": task.exec_type,
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "interval_minutes": task.interval_minutes,
                "total_count": task.total_count,
                "completed_count": task.completed_count,
                "failed_count": task.failed_count,
                "error_msg": task.error_msg,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        )

    return ApiResponse(
        data={
            "total": total,
            "items": task_list,
        }
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse)
async def get_auto_publish_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    获取自动发布任务详情（含子任务记录）

    用于查看任务的详细执行进度和结果
    """
    task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取子任务记录
    records = (
        db.query(AutoPublishRecord)
        .filter(AutoPublishRecord.task_id == task_id)
        .order_by(AutoPublishRecord.created_at.desc())
        .all()
    )

    # 转换记录为响应格式
    record_list = []
    for record in records:
        # 获取关联信息
        article = db.query(GeoArticle).filter(GeoArticle.id == record.article_id).first()
        account = db.query(Account).filter(Account.id == record.account_id).first()

        record_list.append(
            {
                "id": record.id,
                "task_id": record.task_id,
                "article_id": record.article_id,
                "account_id": record.account_id,
                "status": record.status,
                "platform_url": record.platform_url,
                "error_msg": record.error_msg,
                "retry_count": record.retry_count,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "started_at": record.started_at.isoformat() if record.started_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                # 关联信息
                "article_title": article.title if article else None,
                "account_name": account.account_name if account else None,
                "platform": account.platform if account else None,
            }
        )

    return ApiResponse(
        data={
            "task": {
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "article_ids": task.article_ids or [],
                "account_ids": task.account_ids or [],
                "status": task.status,
                "exec_type": task.exec_type,
                "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
                "interval_minutes": task.interval_minutes,
                "total_count": task.total_count,
                "completed_count": task.completed_count,
                "failed_count": task.failed_count,
                "error_msg": task.error_msg,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            },
            "records": record_list,
        }
    )


@router.post("/tasks", response_model=ApiResponse)
async def create_auto_publish_task(
    request: AutoPublishTaskCreate,
    db: Session = Depends(get_db),
):
    """
    创建自动发布任务

    用户选择文章和账号后，创建一个后台发布任务
    """
    # 1. 验证文章和账号是否存在
    articles = db.query(GeoArticle).filter(GeoArticle.id.in_(request.article_ids)).all()
    if len(articles) != len(request.article_ids):
        found_ids = [a.id for a in articles]
        missing = set(request.article_ids) - set(found_ids)
        raise HTTPException(status_code=404, detail=f"文章不存在: {missing}")

    accounts = db.query(Account).filter(Account.id.in_(request.account_ids)).all()
    if len(accounts) != len(request.account_ids):
        found_ids = [a.id for a in accounts]
        missing = set(request.account_ids) - set(found_ids)
        raise HTTPException(status_code=404, detail=f"账号不存在: {missing}")

    # 2. 检查账号状态
    disabled_accounts = [a.account_name for a in accounts if a.status != 1]
    if disabled_accounts:
        raise HTTPException(status_code=400, detail=f"以下账号未授权或已禁用: {', '.join(disabled_accounts)}")

    # 3. 检查文章状态（移除限制，允许重复发布）
    # 之前的逻辑：只能发布状态为 completed/scheduled/failed 的文章
    # 新逻辑：允许任何文章重新发布（支持重复发布到不同平台）
    # 只要文章内容存在即可发布
    invalid_articles = [a.title for a in articles if not a.content]
    if invalid_articles:
        raise HTTPException(
            status_code=400,
            detail=f"以下文章内容为空，无法发布: {', '.join(invalid_articles[:3])}{'...' if len(invalid_articles) > 3 else ''}",
        )

    # 4. 验证执行类型和配置
    if request.exec_type == "scheduled" and not request.scheduled_at:
        raise HTTPException(status_code=400, detail="定时执行必须指定执行时间")

    if request.exec_type == "interval" and not request.interval_minutes:
        raise HTTPException(status_code=400, detail="间隔执行必须指定间隔分钟数")

    # 5. 解析定时时间
    scheduled_at = None
    if request.scheduled_at:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))
            if scheduled_at <= datetime.now():
                raise HTTPException(status_code=400, detail="定时执行时间必须晚于当前时间")
        except ValueError:
            raise HTTPException(status_code=400, detail="时间格式错误")

    # 6. 创建自动发布任务
    total_count = len(articles) * len(accounts)
    task = AutoPublishTask(
        name=request.name,
        description=request.description,
        article_ids=request.article_ids,
        account_ids=request.account_ids,
        exec_type=request.exec_type,
        scheduled_at=scheduled_at,
        interval_minutes=request.interval_minutes,
        declare_ai_content=request.declare_ai_content,
        total_count=total_count,
        completed_count=0,
        failed_count=0,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 7. 创建子任务记录
    for article_id in request.article_ids:
        for account_id in request.account_ids:
            record = AutoPublishRecord(
                task_id=task.id,
                article_id=article_id,
                account_id=account_id,
                status="pending",
            )
            db.add(record)
    db.commit()

    # 8. 根据执行类型启动任务
    if request.exec_type == "immediate":
        # 立即执行：启动后台任务
        asyncio.create_task(execute_auto_publish_task(task.id))
    elif request.exec_type == "scheduled":
        # 定时执行：调度器会处理
        pass
    elif request.exec_type == "interval":
        # 间隔执行：调度器会处理
        pass

    logger.info(f"自动发布任务已创建: {task.id}, 文章数: {len(articles)}, 账号数: {len(accounts)}")

    return ApiResponse(
        data={
            "task_id": task.id,
            "total_count": total_count,
            "message": "自动发布任务已创建",
        }
    )


@router.put("/tasks/{task_id}", response_model=ApiResponse)
async def update_auto_publish_task(
    task_id: int,
    request: AutoPublishTaskUpdate,
    db: Session = Depends(get_db),
):
    """
    更新自动发布任务

    支持修改任务配置或取消任务
    """
    task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 如果任务正在运行，不允许修改
    if task.status == "running":
        raise HTTPException(status_code=400, detail="任务正在执行中，无法修改")

    # 更新字段
    if request.name is not None:
        task.name = request.name
    if request.description is not None:
        task.description = request.description
    if request.status is not None:
        # 状态转换验证
        valid_transitions = {
            "pending": ["running", "cancelled"],
            "running": ["completed", "failed", "cancelled"],
            "failed": ["pending"],  # 失败任务可以重置为待执行
        }
        current_status = task.status
        if request.status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=400,
                detail=f"不允许从状态 {current_status} 转换到 {request.status}",
            )
        task.status = request.status

        # 如果取消任务，更新完成时间
        if request.status == "cancelled":
            task.completed_at = datetime.now()

    if request.scheduled_at is not None:
        try:
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace("Z", "+00:00"))
            if scheduled_at <= datetime.now():
                raise HTTPException(status_code=400, detail="定时执行时间必须晚于当前时间")
            task.scheduled_at = scheduled_at
        except ValueError:
            raise HTTPException(status_code=400, detail="时间格式错误")

    if request.interval_minutes is not None:
        task.interval_minutes = request.interval_minutes

    db.commit()

    return ApiResponse(data={"task_id": task.id, "message": "任务已更新"})


@router.delete("/tasks/{task_id}", response_model=ApiResponse)
async def delete_auto_publish_task(task_id: int):
    """
    删除自动发布任务

    只能删除已完成或已取消的任务
    """
    # 艹！完全不使用FastAPI的get_db，自己创建engine和connection
    from sqlalchemy import create_engine
    from backend.config import DATABASE_URL

    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # 开启外键约束
        conn.execute(text("PRAGMA foreign_keys=ON"))
        # 检查任务状态
        result = conn.execute(
            text("SELECT status FROM auto_publish_tasks WHERE id = :task_id"), {"task_id": task_id}
        ).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="任务不存在")

        task_status = result[0]
        if task_status == "running":
            raise HTTPException(status_code=400, detail="无法删除正在执行的任务")

        # 先删除关联的发布记录
        conn.execute(text("DELETE FROM auto_publish_records WHERE task_id = :task_id"), {"task_id": task_id})
        # 删除任务
        conn.execute(text("DELETE FROM auto_publish_tasks WHERE id = :task_id"), {"task_id": task_id})
        conn.commit()

    logger.info(f"自动发布任务已删除: {task_id}")

    return ApiResponse(data={"message": "任务已删除"})


@router.post("/tasks/{task_id}/start", response_model=ApiResponse)
async def start_auto_publish_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    手动启动自动发布任务

    用于立即执行待执行或失败的任务
    """
    task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查任务状态
    if task.status == "running":
        raise HTTPException(status_code=400, detail="任务正在执行中")

    if task.status not in ["pending", "failed"]:
        raise HTTPException(status_code=400, detail=f"当前任务状态为 {task.status}，无法启动")

    # 启动后台执行任务
    asyncio.create_task(execute_auto_publish_task(task_id))

    logger.info(f"自动发布任务已手动启动: {task_id}")

    return ApiResponse(data={"task_id": task_id, "message": "任务已启动"})


@router.post("/tasks/{task_id}/cancel", response_model=ApiResponse)
async def cancel_auto_publish_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    取消正在执行的自动发布任务

    用于停止正在运行的任务
    """
    task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "running":
        raise HTTPException(status_code=400, detail="只能取消正在执行的任务")

    # 更新任务状态
    task.status = "cancelled"
    task.completed_at = datetime.now()
    db.commit()

    # 从执行器中移除
    task_executor.complete_task(task_id, success=False, error_msg="任务已取消")

    logger.info(f"自动发布任务已取消: {task_id}")

    return ApiResponse(data={"task_id": task_id, "message": "任务已取消"})


@router.post("/tasks/{task_id}/retry", response_model=ApiResponse)
async def retry_auto_publish_task(
    task_id: int,
    db: Session = Depends(get_db),
):
    """
    重试失败的自动发布任务

    重新执行任务中失败的子任务
    """
    task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "failed":
        raise HTTPException(status_code=400, detail="只能重试失败的任务")

    # 重置任务状态
    task.status = "pending"
    task.error_msg = None
    task.failed_count = 0
    task.completed_count = 0
    db.commit()

    # 重置失败的子任务记录
    failed_records = (
        db.query(AutoPublishRecord)
        .filter(AutoPublishRecord.task_id == task_id, AutoPublishRecord.status == "failed")
        .all()
    )
    for record in failed_records:
        record.status = "pending"
        record.error_msg = None
        record.retry_count = 0
    db.commit()

    # 启动后台执行任务
    asyncio.create_task(execute_auto_publish_task(task_id))

    logger.info(f"自动发布任务已重试: {task_id}")

    return ApiResponse(data={"task_id": task_id, "message": "任务已重试"})


# ==================== 任务执行核心逻辑 ====================


async def execute_auto_publish_task(task_id: int):
    """
    执行自动发布任务（后台异步任务）

    这是核心执行逻辑，负责：
    1. 更新任务状态为 running
    2. 逐个执行子任务（发布文章到账号）
    3. 更新进度和结果
    4. 处理错误和重试

    注意：不再接收 db 参数，函数内部自行管理 Session 生命周期。
    """
    # 获取新的session（避免在异步线程中使用过期的session）
    from backend.database import SessionLocal

    db = SessionLocal()

    try:
        # 1. 获取任务
        task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        # 2. 更新任务状态
        task.status = "running"
        task.started_at = datetime.now()
        db.commit()

        task_executor.start_task(task_id)

        # 3. 获取子任务记录
        records = (
            db.query(AutoPublishRecord)
            .filter(AutoPublishRecord.task_id == task_id, AutoPublishRecord.status == "pending")
            .all()
        )

        logger.info(f"开始执行自动发布任务: {task_id}, 子任务数: {len(records)}")

        # 4. 获取发布管理器
        publish_mgr = get_playwright_mgr()
        await publish_mgr.start()

        # 5. 逐个执行子任务
        for record in records:
            try:
                # 检查任务是否被取消
                task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
                if task.status == "cancelled":
                    logger.info(f"任务已取消，停止执行: {task_id}")
                    return

                # 更新子任务状态
                record.status = "publishing"
                record.started_at = datetime.now()
                db.commit()

                # 获取文章和账号
                article = db.query(GeoArticle).filter(GeoArticle.id == record.article_id).first()
                account = db.query(Account).filter(Account.id == record.account_id).first()

                if not article or not account:
                    raise Exception("文章或账号不存在")

                # 执行发布 (传递AI声明选项)
                declare_ai = getattr(task, "declare_ai_content", True)
                result = await publish_mgr.execute_publish(article, account, declare_ai_content=declare_ai)

                if result.get("success"):
                    # 发布成功
                    record.status = "success"
                    record.platform_url = result.get("platform_url")
                    record.completed_at = datetime.now()

                    # 更新任务计数
                    task.completed_count += 1
                else:
                    # 发布失败
                    record.status = "failed"
                    record.error_msg = result.get("error_msg", "未知错误")
                    record.completed_at = datetime.now()
                    record.retry_count += 1

                    # 更新任务计数
                    task.failed_count += 1

                db.commit()

                # WebSocket 推送进度
                ws_mgr = get_ws_manager()
                if ws_mgr:
                    platform_config = PLATFORMS.get(account.platform, {})
                    await ws_mgr.broadcast(
                        {
                            "type": "auto_publish_progress",
                            "task_id": task_id,
                            "data": {
                                "record_id": record.id,
                                "article_id": article.id,
                                "article_title": article.title,
                                "account_id": account.id,
                                "account_name": account.account_name,
                                "platform": account.platform,
                                "platform_name": platform_config.get("name", account.platform),
                                "status": record.status,
                                "platform_url": record.platform_url,
                                "error_msg": record.error_msg,
                                "completed_count": task.completed_count,
                                "failed_count": task.failed_count,
                                "total_count": task.total_count,
                            },
                        }
                    )

            except Exception as e:
                logger.error(f"发布子任务失败: {record.id}, {e}")
                record.status = "failed"
                record.error_msg = str(e)
                record.completed_at = datetime.now()
                record.retry_count += 1
                task.failed_count += 1
                db.commit()

        # 6. 更新任务完成状态
        task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now()

            # 如果有失败的子任务，整体状态设为failed
            if task.failed_count > 0:
                task.status = "failed"
                task.error_msg = f"部分发布失败: {task.failed_count}/{task.total_count}"

            db.commit()

        task_executor.complete_task(task_id, success=(task.status == "completed"), error_msg=task.error_msg)

        logger.info(f"自动发布任务执行完成: {task_id}, 状态: {task.status}")

    except Exception as e:
        logger.error(f"自动发布任务执行失败: {task_id}, {e}")

        # 更新任务状态为失败
        task = db.query(AutoPublishTask).filter(AutoPublishTask.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_msg = str(e)
            task.completed_at = datetime.now()
            db.commit()

        task_executor.complete_task(task_id, success=False, error_msg=str(e))

    finally:
        db.close()
