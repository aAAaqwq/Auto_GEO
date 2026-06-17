# -*- coding: utf-8 -*-
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Integer, case
from backend.database import get_db
from backend.database.models import Project, Keyword, IndexCheckRecord, GeoArticle, QuestionVariant
from backend.schemas import ApiResponse
from loguru import logger

router = APIRouter(prefix="/api/reports", tags=["数据报表"])


class SummaryStats(BaseModel):
    total_articles: int
    common_articles: int
    geo_articles: int
    publish_success_rate: float
    publish_success_count: int
    publish_total_count: int
    keyword_hit_rate: float
    keyword_hit_count: int
    keyword_check_count: int
    company_hit_rate: float
    company_hit_count: int
    company_check_count: int


class PlatformStat(BaseModel):
    platform: str
    hit_count: int
    total_count: int
    hit_rate: float


class ProjectRank(BaseModel):
    rank: int
    project_name: str
    company_name: str
    content_volume: int
    ai_mention_rate: float
    brand_relevance: float


class TrendDataPoint(BaseModel):
    """趋势数据点"""

    date: str
    keyword_found_count: int
    company_found_count: int
    total_checks: int


class ProjectStatsResponse(BaseModel):
    project_id: int
    project_name: str
    company_name: str
    total_keywords: int
    active_keywords: int
    total_questions: int
    total_checks: int
    keyword_hit_rate: float
    company_hit_rate: float


class PlatformStatsResponse(BaseModel):
    platform: str
    total_checks: int
    keyword_found: int
    company_found: int
    keyword_hit_rate: float
    company_hit_rate: float


class ArticleStatsResponse(BaseModel):
    """GeoArticle 文章统计响应"""

    total: int
    generating: int
    completed: int
    published: int
    failed: int


# ==================== 报表API ====================


@router.get("/article-stats", response_model=ArticleStatsResponse)
async def get_article_stats(
    project_id: Optional[int] = Query(None, description="项目ID筛选"), db: Session = Depends(get_db)
):
    """
    获取 GeoArticle 文章统计信息

    统计不同状态的文章数量：
    - total: 总数
    - generating: 生成中
    - completed: 已生成/待分发 (completed)
    - published: 已发布
    - failed: 生成失败
    """
    # 构建基础查询
    query = db.query(GeoArticle)

    # 如果指定了项目，则通过关键词关联筛选
    if project_id:
        query = query.join(Keyword).filter(Keyword.project_id == project_id)

    # 统计各状态数量（使用聚合查询提高性能）
    stats = (
        db.query(GeoArticle.publish_status, func.count(GeoArticle.id).label("count"))
        .filter(GeoArticle.publish_status.in_(["generating", "completed", "scheduled", "published", "failed"]))
        .group_by(GeoArticle.publish_status)
        .all()
    )

    # 将查询结果转换为字典
    stats_dict = {row.publish_status: row.count for row in stats}

    # 统计总数（包含其他状态如 draft）
    total = query.count()

    return ArticleStatsResponse(
        total=total,
        generating=stats_dict.get("generating", 0),
        completed=stats_dict.get("completed", 0),
        published=stats_dict.get("published", 0),
        failed=stats_dict.get("failed", 0),
    )


@router.get("/projects", response_model=List[ProjectStatsResponse])
async def get_project_stats(db: Session = Depends(get_db)):
    """
    获取所有项目的统计数据

    注意：返回每个项目的关键词数量、命中率等！
    """
    projects = db.query(Project).filter(Project.status == 1).all()

    results = []
    for project in projects:
        # 统计关键词数量
        total_keywords = db.query(Keyword).filter(Keyword.project_id == project.id).count()
        active_keywords = db.query(Keyword).filter(Keyword.project_id == project.id, Keyword.status == "active").count()

        # 统计问题变体数量
        keyword_ids = db.query(Keyword.id).filter(Keyword.project_id == project.id).subquery()
        total_questions = db.query(QuestionVariant).filter(QuestionVariant.keyword_id.in_(keyword_ids)).count()

        # 统计检测记录
        keyword_ids_active = (
            db.query(Keyword.id).filter(Keyword.project_id == project.id, Keyword.status == "active").subquery()
        )

        total_checks = db.query(IndexCheckRecord).filter(IndexCheckRecord.keyword_id.in_(keyword_ids_active)).count()

        # 计算命中率
        stats = (
            db.query(
                func.sum(case((IndexCheckRecord.keyword_found == True, 1), else_=0)).label("keyword_found"),
                func.sum(case((IndexCheckRecord.company_found == True, 1), else_=0)).label("company_found"),
            )
            .filter(IndexCheckRecord.keyword_id.in_(keyword_ids_active))
            .first()
        )

        keyword_found = stats.keyword_found or 0
        company_found = stats.company_found or 0

        keyword_hit_rate = round(keyword_found / total_checks * 100, 2) if total_checks > 0 else 0
        company_hit_rate = round(company_found / total_checks * 100, 2) if total_checks > 0 else 0

        results.append(
            ProjectStatsResponse(
                project_id=project.id,
                project_name=project.name,
                company_name=project.company_name,
                total_keywords=total_keywords,
                active_keywords=active_keywords,
                total_questions=total_questions,
                total_checks=total_checks,
                keyword_hit_rate=keyword_hit_rate,
                company_hit_rate=company_hit_rate,
            )
        )

    return results


@router.get("/platforms", response_model=List[PlatformStatsResponse])
async def get_platform_stats(db: Session = Depends(get_db)):
    """
    获取各平台的统计数据

    注意：比较不同平台的收录效果！
    """
    platforms = ["doubao", "qianwen", "deepseek"]

    results = []
    for platform in platforms:
        # 统计该平台的检测记录
        records = db.query(IndexCheckRecord).filter(IndexCheckRecord.platform == platform).all()

        total_checks = len(records)
        keyword_found = sum(1 for r in records if r.keyword_found)
        company_found = sum(1 for r in records if r.company_found)

        keyword_hit_rate = round(keyword_found / total_checks * 100, 2) if total_checks > 0 else 0
        company_hit_rate = round(company_found / total_checks * 100, 2) if total_checks > 0 else 0

        # 平台名称映射
        platform_names = {"doubao": "豆包", "qianwen": "通义千问", "deepseek": "DeepSeek"}

        results.append(
            PlatformStatsResponse(
                platform=platform_names.get(platform, platform),
                total_checks=total_checks,
                keyword_found=keyword_found,
                company_found=company_found,
                keyword_hit_rate=keyword_hit_rate,
                company_hit_rate=company_hit_rate,
            )
        )

    return results


@router.get("/trends", response_model=List[TrendDataPoint])
async def get_trends(
    days: int = Query(30, ge=1, le=90, description="统计天数"),
    platform: Optional[str] = Query(None, description="平台筛选"),
    db: Session = Depends(get_db),
):
    """
    获取收录趋势数据

    注意：用于绘制趋势图表！
    """
    start_date = datetime.now() - timedelta(days=days)

    # 构建查询
    query = db.query(
        func.date(IndexCheckRecord.check_time).label("date"),
        func.sum(case((IndexCheckRecord.keyword_found == True, 1), else_=0)).label("keyword_found"),
        func.sum(case((IndexCheckRecord.company_found == True, 1), else_=0)).label("company_found"),
        func.count().label("total_checks"),
    ).filter(IndexCheckRecord.check_time >= start_date)

    # 增加平台筛选
    if platform:
        query = query.filter(IndexCheckRecord.platform == platform)

    # 按日期分组统计
    trends = (
        query.group_by(func.date(IndexCheckRecord.check_time)).order_by(func.date(IndexCheckRecord.check_time)).all()
    )

    # 转换为响应模型
    result = []
    for trend in trends:
        result.append(
            TrendDataPoint(
                date=str(trend.date),
                keyword_found_count=trend.keyword_found or 0,
                company_found_count=trend.company_found or 0,
                total_checks=trend.total_checks,
            )
        )

    return result


@router.get("/stats", response_model=SummaryStats)
async def get_summary_stats(
    project_id: Optional[int] = Query(None), days: int = Query(7), db: Session = Depends(get_db)
):
    """获取数据总览卡片数据"""
    start_date = datetime.now() - timedelta(days=days)

    # 1. 文章生成数（仅统计 GeoArticle）
    geo_query = db.query(GeoArticle).filter(GeoArticle.created_at >= start_date)

    if project_id:
        # GeoArticle 有关联 Keyword -> Project
        geo_query = geo_query.join(Keyword).filter(Keyword.project_id == project_id)

    total_articles = geo_query.count()

    # 2. 发布成功率（仅统计 GeoArticle）
    # 统计 GeoArticle 的发布状态
    geo_pub_published = geo_query.filter(GeoArticle.publish_status == "published").count()
    geo_pub_total = geo_query.filter(GeoArticle.publish_status.in_(["published", "failed"])).count()
    pub_rate = round((geo_pub_published / geo_pub_total * 100), 2) if geo_pub_total > 0 else 0

    # 3. 关键词/公司名命中率
    idx_query = db.query(IndexCheckRecord).filter(IndexCheckRecord.check_time >= start_date)
    if project_id:
        idx_query = idx_query.join(Keyword).filter(Keyword.project_id == project_id)

    idx_total = idx_query.count()
    kw_hit_count = idx_query.filter(IndexCheckRecord.keyword_found == True).count()
    co_hit_count = idx_query.filter(IndexCheckRecord.company_found == True).count()

    kw_rate = round((kw_hit_count / idx_total * 100), 2) if idx_total > 0 else 0
    co_rate = round((co_hit_count / idx_total * 100), 2) if idx_total > 0 else 0

    return SummaryStats(
        total_articles=total_articles,
        common_articles=0,  # 仪表盘只统计GeoArticle
        geo_articles=total_articles,  # 所有文章都是GeoArticle
        publish_success_rate=pub_rate,
        publish_success_count=geo_pub_published,
        publish_total_count=geo_pub_total,
        keyword_hit_rate=kw_rate,
        keyword_hit_count=kw_hit_count,
        keyword_check_count=idx_total,
        company_hit_rate=co_rate,
        company_hit_count=co_hit_count,
        company_check_count=idx_total,
    )


@router.get("/platform-comparison", response_model=List[PlatformStat])
async def get_platform_comparison(
    project_id: Optional[int] = Query(None),
    days: int = Query(7),
    platform: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """AI平台对比分析"""
    start_date = datetime.now() - timedelta(days=days)
    query = db.query(
        IndexCheckRecord.platform,
        func.count(IndexCheckRecord.id).label("total"),
        func.sum(cast(IndexCheckRecord.keyword_found, Integer)).label("kw_hits"),
    ).filter(IndexCheckRecord.check_time >= start_date)

    if project_id:
        query = query.join(Keyword).filter(Keyword.project_id == project_id)

    if platform:
        query = query.filter(IndexCheckRecord.platform == platform)

    stats = query.group_by(IndexCheckRecord.platform).all()

    return [
        PlatformStat(
            platform=s.platform,
            total_count=s.total,
            hit_count=int(s.kw_hits or 0),
            hit_rate=round((int(s.kw_hits or 0) / s.total * 100), 2) if s.total > 0 else 0,
        )
        for s in stats
    ]


@router.get("/project-leaderboard", response_model=List[ProjectRank])
async def get_project_leaderboard(days: int = Query(7), db: Session = Depends(get_db)):
    """项目影响力排行榜"""
    start_date = datetime.now() - timedelta(days=days)
    projects = db.query(Project).filter(Project.status == 1).all()

    result = []
    for i, p in enumerate(projects):
        # 统计该项目的文章数
        content_volume = (
            db.query(GeoArticle)
            .join(Keyword)
            .filter(Keyword.project_id == p.id, GeoArticle.created_at >= start_date)
            .count()
        )

        # 统计收录率作为提及率参考
        idx_query = (
            db.query(IndexCheckRecord)
            .join(Keyword)
            .filter(Keyword.project_id == p.id, IndexCheckRecord.check_time >= start_date)
        )
        total_checks = idx_query.count()
        hits = idx_query.filter(IndexCheckRecord.keyword_found == True).count()
        mention_rate = round((hits / total_checks * 100), 2) if total_checks > 0 else 0

        result.append(
            ProjectRank(
                rank=i + 1,
                project_name=p.name,
                company_name=p.company_name,
                content_volume=content_volume,
                ai_mention_rate=mention_rate,
                brand_relevance=mention_rate,  # 暂时使用相同逻辑
            )
        )

    # 按提及率排序
    result.sort(key=lambda x: x.ai_mention_rate, reverse=True)
    for i, item in enumerate(result):
        item.rank = i + 1

    return result[:10]


@router.get("/overview")
async def get_overview(db: Session = Depends(get_db)):
    """获取数据总览"""
    # 统计关键词数量
    total_keywords = db.query(Keyword).count()

    # 统计检测记录
    total_records = db.query(IndexCheckRecord).count()
    keyword_found = db.query(IndexCheckRecord).filter(IndexCheckRecord.keyword_found == True).count()
    company_found = db.query(IndexCheckRecord).filter(IndexCheckRecord.company_found == True).count()

    # 计算总体命中率
    overall_hit_rate = 0
    if total_records > 0:
        overall_hit_rate = round(((keyword_found + company_found) / (total_records * 2)) * 100, 2)

    return {
        "total_keywords": total_keywords,
        "keyword_found": keyword_found,
        "company_found": company_found,
        "overall_hit_rate": overall_hit_rate,
    }


# ==================== 收录检测相关API ====================


class BatchCheckRequest(BaseModel):
    """批量收录检测请求"""

    project_id: int
    platforms: Optional[List[str]] = None


@router.post("/run-check", response_model=ApiResponse)
async def run_check(request: BatchCheckRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    在数据报表页面执行项目收录收录检测
    复用 IndexCheckService.check_project_keywords() 方法
    """
    from backend.services.index_check_service import IndexCheckService

    # 验证项目存在
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        return ApiResponse(success=False, message="项目不存在")

    service = IndexCheckService(db)

    # 执行批量检测（复用收录查询的服务逻辑）
    try:
        results = await service.check_project_keywords(project_id=request.project_id, platforms=request.platforms)

        return ApiResponse(success=True, message=f"收录检测完成，共生成 {len(results)} 条检测记录")
    except Exception as e:
        logger.error(f"收录检测失败: {e}")
        return ApiResponse(success=False, message=f"检测失败: {str(e)}")
