# -*- coding: utf-8 -*-
"""
GEO文章管理 API - 工业加固版
处理文章生成、质检、列表、收录检测触发等
"""

import asyncio
import json
import re
import zlib
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db, SessionLocal
from backend.services.geo_article_service import GeoArticleService
from backend.database.models import GeoArticle, Project, Keyword
from backend.schemas import ApiResponse
from loguru import logger

router = APIRouter(prefix="/api/geo", tags=["GEO文章"])


# ==================== 辅助函数 ====================


def _convert_article_to_dict(article: GeoArticle) -> dict:
    """
    将GeoArticle模型转换为字典，处理target_platforms和datetime类型转换
    修复Pydantic验证错误：target_platforms字符串需要转换为列表
    """
    # 处理target_platforms字段
    target_platforms = None
    if article.target_platforms is not None:
        if isinstance(article.target_platforms, str):
            try:
                target_platforms = json.loads(article.target_platforms)
            except:
                target_platforms = [article.target_platforms] if article.target_platforms else []
        elif isinstance(article.target_platforms, list):
            target_platforms = article.target_platforms
        else:
            target_platforms = []

    # 处理datetime字段
    def dt_to_str(dt):
        if dt is None:
            return None
        if isinstance(dt, datetime):
            return dt.isoformat()
        return str(dt)

    return {
        "id": article.id,
        "keyword_id": article.keyword_id,
        "title": article.title,
        "content": article.content,
        "quality_status": article.quality_status,
        "publish_status": article.publish_status,
        "index_status": article.index_status,
        "platform": article.platform,
        "account_id": article.account_id,
        "target_platforms": target_platforms,
        "publish_strategy": article.publish_strategy,
        "quality_score": article.quality_score,
        "ai_score": article.ai_score,
        "readability_score": article.readability_score,
        "retry_count": article.retry_count,
        "error_msg": article.error_msg,
        "publish_logs": article.publish_logs,
        "platform_url": article.platform_url,
        "index_details": article.index_details,
        "publish_time": dt_to_str(article.publish_time),
        "scheduled_at": dt_to_str(article.scheduled_at),
        "last_check_time": dt_to_str(article.last_check_time),
        "created_at": dt_to_str(article.created_at),
    }


def _stabilize_image_urls(content: str, article_id: int) -> str:
    """给 loremflickr 图片 URL 补稳定 lock，避免预览和发布拿到不同图片。"""
    if not content:
        return content

    counter = 0

    def replace_url(match):
        nonlocal counter
        url = match.group(1)
        if "loremflickr.com" not in url or "lock=" in url:
            return match.group(0)

        counter += 1
        seed_text = f"{article_id}:{counter}:{url}"
        lock = zlib.crc32(seed_text.encode("utf-8")) % 9999 + 1
        separator = "&" if "?" in url else "?"
        stable_url = f"{url}{separator}lock={lock}"
        return match.group(0).replace(url, stable_url)

    return re.sub(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", replace_url, content)


# ==================== 请求/响应模型 ====================


class GenerateArticleRequest(BaseModel):
    """文章生成请求模型"""

    keyword_id: int
    company_name: str
    # 发布策略相关（新增）
    target_platforms: Optional[List[str]] = Field(None, description="预设目标平台列表")
    publish_strategy: Optional[str] = Field(
        "draft", description="发布策略：draft=仅生成草稿 immediate=生成后立即发布 scheduled=定时发布"
    )
    scheduled_at: Optional[str] = Field(None, description="定时发布时间（ISO格式）")


class ArticleCallbackRequest(BaseModel):
    """
    n8n异步回调请求模型
    n8n生成完成后将结果通过此接口回调
    """

    article_id: int = Field(..., description="文章ID，用于关联更新对应记录")
    title: Optional[str] = Field(None, description="文章标题")
    content: Optional[str] = Field(None, description="文章内容")
    seo_score: Optional[int] = Field(None, description="SEO评分")
    quality_score: Optional[int] = Field(None, description="质量评分")
    error: Optional[str] = Field(None, description="错误信息，如果生成失败")
    status: Optional[str] = Field("success", description="生成状态")


class ArticleResponse(BaseModel):
    """
    🌟 核心模型：解决前端列表显示的所有字段需求
    """

    id: int
    keyword_id: int
    title: Optional[str] = None
    content: Optional[str] = None

    # 状态字段
    quality_status: Optional[str] = "pending"
    publish_status: Optional[str] = "draft"
    index_status: Optional[str] = "uncheck"
    platform: Optional[str] = None
    account_id: Optional[int] = None

    # 发布策略字段（新增）
    target_platforms: Optional[List[str]] = None
    publish_strategy: Optional[str] = "draft"

    # 评分字段
    quality_score: Optional[int] = None
    ai_score: Optional[int] = None
    readability_score: Optional[int] = None

    # 记录与日志
    retry_count: Optional[int] = 0
    error_msg: Optional[str] = None
    publish_logs: Optional[str] = None
    platform_url: Optional[str] = None  # 🌟 发布成功后的真实链接
    index_details: Optional[str] = None

    # 时间戳
    publish_time: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    last_check_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    # 兼容 SQLAlchemy 对象
    model_config = ConfigDict(from_attributes=True)


class ProjectResponse(BaseModel):
    id: int
    name: str
    company_name: str
    model_config = ConfigDict(from_attributes=True)


# ==================== 异步辅助逻辑 ====================


async def run_generate_task(
    keyword_id: int,
    company_name: str,
    target_platforms: Optional[List[str]] = None,
    publish_strategy: str = "draft",
    scheduled_at: Optional[str] = None,
):
    """后台执行生成任务的闭包"""
    db = SessionLocal()
    try:
        service = GeoArticleService(db)
        await service.generate(
            keyword_id,
            company_name,
            target_platforms=target_platforms,
            publish_strategy=publish_strategy,
            scheduled_at=scheduled_at,
        )
    except Exception as e:
        logger.error(f"❌ 后台生成任务失败: {str(e)}")
    finally:
        db.close()


# ==================== 接口实现 ====================


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)):
    """获取所有活跃项目列表"""
    return db.query(Project).filter(Project.status == 1).all()


@router.post("/generate", response_model=ApiResponse)
async def generate_article(request: GenerateArticleRequest, background_tasks: BackgroundTasks):
    """
    提交文章生成任务
    使用 BackgroundTasks 实现非阻塞响应

    支持发布策略：
    - draft: 仅生成草稿
    - immediate: 生成后立即发布
    - scheduled: 定时发布
    """
    background_tasks.add_task(
        run_generate_task,
        request.keyword_id,
        request.company_name,
        request.target_platforms,
        request.publish_strategy,
        request.scheduled_at,
    )
    return ApiResponse(success=True, message="生成任务已提交，请在列表查看进度")


@router.get("/articles")
async def list_articles(
    project_id: Optional[int] = Query(None, description="项目ID筛选"),
    limit: int = Query(100),
    publish_status: Optional[str] = Query(
        None, description="发布状态过滤: generating/completed/scheduled/publishing/published/failed"
    ),
    db: Session = Depends(get_db),
):
    """
    获取文章列表（按创建时间倒序）

    支持按 publish_status 和 project_id 过滤。

    状态说明：
    - generating: AI 生成中
    - completed: 已生成/待分发（生成完成，等待用户配置发布）
    - scheduled: 已配置定时发布
    - publishing: 发布中
    - published: 已发布
    - failed: 失败

    批量发布页面应使用 publish_status=completed 获取待配置发布的文章。
    """
    query = db.query(GeoArticle).order_by(desc(GeoArticle.created_at))

    # 如果指定了项目，进行过滤
    if project_id:
        query = query.join(Keyword).filter(Keyword.project_id == project_id)

    # 如果指定了状态，进行过滤
    if publish_status:
        # 🌟 支持数组过滤：如果 publish_status 是列表，使用 in_ 方法
        if isinstance(publish_status, list):
            query = query.filter(GeoArticle.publish_status.in_(publish_status))
        else:
            query = query.filter(GeoArticle.publish_status == publish_status)

    # 应用分页限制
    if limit:
        query = query.limit(limit)

    articles = query.all()
    # 手动转换数据类型，修复Pydantic验证错误
    return [_convert_article_to_dict(article) for article in articles]


@router.post("/articles/{article_id}/check-quality", response_model=ApiResponse)
async def check_quality(article_id: int, db: Session = Depends(get_db)):
    """
    🌟 [修复] 手动触发文章质检评分
    """
    service = GeoArticleService(db)
    try:
        result = await service.check_quality(article_id)
        if result.get("success"):
            return ApiResponse(success=True, message="质检完成", data=result)
        return ApiResponse(success=False, message=result.get("message", "质检失败"))
    except Exception as e:
        logger.error(f"质检异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/articles/{article_id}/check-index", response_model=ApiResponse)
async def manual_check_index(article_id: int, db: Session = Depends(get_db)):
    """手动触发单篇文章的收录监测"""
    service = GeoArticleService(db)
    try:
        result = await service.check_article_index(article_id)
        if result.get("status") == "error":
            return ApiResponse(success=False, message=result.get("message"))
        return ApiResponse(success=True, message=f"检测完成，当前状态：{result.get('index_status')}")
    except Exception as e:
        logger.error(f"收录检测异常: {str(e)}")
        return ApiResponse(success=False, message="检测服务暂时不可用")


@router.delete("/articles/{article_id}", response_model=ApiResponse)
async def delete_article(article_id: int, db: Session = Depends(get_db)):
    """删除文章记录"""
    article = db.query(GeoArticle).filter(GeoArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    try:
        db.delete(article)
        db.commit()
        return ApiResponse(success=True, message="文章已成功删除")
    except Exception as e:
        db.rollback()
        return ApiResponse(success=False, message=f"删除失败: {str(e)}")


@router.post("/callback", response_model=ApiResponse)
async def handle_n8n_callback(request: ArticleCallbackRequest, db: Session = Depends(get_db)):
    """
    接收 n8n 异步回调接口
    n8n生成完成后调用此接口更新文章内容
    """
    logger.info(f"📨 收到 n8n 回调: article_id={request.article_id}, status={request.status}")

    # 1. 查找文章记录
    article = db.query(GeoArticle).filter(GeoArticle.id == request.article_id).first()
    if not article:
        logger.warning(f"⚠️ 回调文章不存在: article_id={request.article_id}")
        raise HTTPException(status_code=404, detail=f"文章 ID {request.article_id} 不存在")

    # 2. 根据回调状态更新文章
    if request.status == "success" or request.error is None:
        # 生成成功：更新内容和状态
        if request.title:
            article.title = request.title
            logger.info(f"✅ 更新标题: {request.title}")

        if request.content:
            article.content = _stabilize_image_urls(request.content, article.id)
            logger.info(f"✅ 更新内容 (长度: {len(request.content)})")

        # 更新评分（如果有）
        if request.quality_score:
            article.quality_score = request.quality_score
            article.quality_status = "passed"
            logger.info(f"✅ 更新质量评分: {request.quality_score}")

        if request.seo_score:
            article.ai_score = request.seo_score
            logger.info(f"✅ 更新SEO评分: {request.seo_score}")

        # 🌟 根据发布策略执行不同逻辑
        strategy = article.publish_strategy or "draft"
        logger.info(f"📋 文章生成完成，发布策略: {strategy}")

        if strategy == "immediate":
            # 立即发布：设为 publishing 并立即调用发布逻辑
            article.publish_status = "publishing"
            article.error_msg = None
            # 从 target_platforms 获取第一个平台
            if article.target_platforms and len(article.target_platforms) > 0:
                article.platform = article.target_platforms[0]

            db.commit()
            logger.success(f"✅ 文章 {article.id} 生成完成，策略为立即发布，开始执行发布")

            # 异步调用发布逻辑
            from backend.services.geo_article_service import GeoArticleService

            service = GeoArticleService(db)
            asyncio.create_task(service.execute_publish(article.id))

        elif strategy == "scheduled":
            # 定时发布：设为 scheduled，保留 scheduled_at 时间
            article.publish_status = "scheduled"
            article.error_msg = None
            # 从 target_platforms 获取第一个平台
            if article.target_platforms and len(article.target_platforms) > 0:
                article.platform = article.target_platforms[0]

            db.commit()
            logger.success(f"✅ 文章 {article.id} 生成完成，策略为定时发布，将在 {article.scheduled_at} 执行")

        else:
            # draft：仅生成草稿，设为 completed
            article.publish_status = "completed"
            article.error_msg = None
            # 清除发布相关字段
            article.platform = None
            article.scheduled_at = None
            article.publish_time = None

            db.commit()
            logger.success(f"✅ 文章 {article.id} 生成完成，策略为仅生成草稿，等待用户配置发布")

    else:
        # 生成失败：记录错误信息
        article.publish_status = "failed"
        article.error_msg = request.error or "n8n生成失败"
        db.commit()
        logger.error(f"❌ 文章 {article.id} 生成失败: {request.error}")

    return ApiResponse(success=True, message="回调处理完成")
