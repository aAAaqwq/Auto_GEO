# -*- coding: utf-8 -*-
"""
Pydantic schemas 用于API请求和响应
用这个做数据校验，别传垃圾数据给我！
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import IntEnum

# 导入平台配置（忘记导出了！）
# 注意：这里不能用相对导入，因为schemas会被作为独立模块导入
PLATFORMS = None  # 将在运行时从config模块获取


# ==================== 枚举定义 ====================
class AccountStatus(IntEnum):
    """账号状态"""

    DISABLED = 0  # 禁用
    ACTIVE = 1  # 正常
    EXPIRED = -1  # 授权过期


class PublishStatus(IntEnum):
    """发布状态"""

    PENDING = 0  # 待发布
    PUBLISHING = 1  # 发布中
    SUCCESS = 2  # 成功
    FAILED = 3  # 失败


class ArticleStatus(IntEnum):
    """文章状态"""

    DRAFT = 0  # 草稿
    PUBLISHED = 1  # 已发布


# ==================== 通用响应 ====================
class ApiResponse(BaseModel):
    """统一API响应格式"""

    success: bool = True
    message: str = "操作成功"
    data: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ErrorResponse(BaseModel):
    """错误响应"""

    success: bool = False
    error: Optional[str] = None
    message: str = "操作失败"
    timestamp: datetime = Field(default_factory=datetime.now)


# ==================== 账号相关 ====================
class AccountBase(BaseModel):
    """账号基础信息"""

    platform: str = Field(
        ...,
        description="平台ID",
        pattern="^(zhihu|baijiahao|sohu|toutiao|wenku|penguin|weixin|wangyi|zijie|xiaohongshu|bilibili|36kr|huxiu|woshipm|douyin|kuaishou|video_account|sohu_video|weibo|haokan|xigua|jianshu|iqiyi|dayu|acfun|tencent_video|yidian|pipixia|meipai|douban|kuai_chuan|dafeng|xueqiu|yiche|chejia|duoduo|weishi|mango|ximalaya|meituan|alipay|douyin_company|douyin_company_lead|custom)$",
    )
    account_name: str = Field(..., min_length=1, max_length=100, description="账号备注名称")
    remark: Optional[str] = Field(None, description="备注信息")


class AccountCreate(AccountBase):
    """创建账号请求"""

    pass


class AccountUpdate(BaseModel):
    """更新账号请求"""

    account_name: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[int] = Field(None, ge=-1, le=1)
    remark: Optional[str] = None


class AccountResponse(AccountBase):
    """账号响应"""

    id: int
    username: Optional[str] = None
    status: int
    last_auth_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountDetailResponse(AccountResponse):
    """账号详情（含授权状态）"""

    is_authorized: bool = False
    platform_info: Optional[dict] = None


# ==================== 授权相关 ====================
class AuthStartRequest(BaseModel):
    """开始授权请求"""

    platform: str = Field(..., description="平台ID")
    account_id: Optional[int] = Field(None, description="账号ID，更新授权时使用")
    account_name: Optional[str] = Field(None, description="账号名称，新账号时使用")


class AuthStartResponse(BaseModel):
    """开始授权响应"""

    task_id: str
    message: str = "浏览器已打开，请完成登录"


class AuthStatusResponse(BaseModel):
    """授权状态响应"""

    task_id: str
    status: str  # pending, running, success, failed, timeout
    is_logged_in: bool = False
    message: Optional[str] = None
    account_id: Optional[int] = None  # 授权成功后返回账号ID


# ==================== 文章相关 ====================
class ArticleBase(BaseModel):
    """文章基础信息"""

    title: str = Field(..., min_length=1, max_length=200, description="文章标题")
    content: str = Field(..., min_length=1, description="文章内容")
    tags: Optional[str] = Field(None, description="标签，逗号分隔")
    category: Optional[str] = Field(None, max_length=100, description="文章分类")
    cover_image: Optional[str] = Field(None, max_length=500, description="封面图片URL")


class ArticleCreate(ArticleBase):
    """创建文章请求"""

    pass


class ArticleUpdate(BaseModel):
    """更新文章请求"""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    tags: Optional[str] = None
    category: Optional[str] = None
    cover_image: Optional[str] = None
    status: Optional[int] = Field(None, ge=0, le=1)


class ArticleResponse(ArticleBase):
    """文章响应"""

    id: int
    status: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ArticleListResponse(BaseModel):
    """文章列表响应"""

    total: int
    items: List[ArticleResponse]


# ==================== 发布相关 ====================
class PublishTaskCreate(BaseModel):
    """创建发布任务请求"""

    article_ids: List[int] = Field(..., description="文章ID列表")
    account_ids: List[int] = Field(..., description="账号ID列表")


class PublishTaskResponse(BaseModel):
    """发布任务响应"""

    task_id: str
    total_tasks: int
    message: str = "发布任务已创建"


class PublishProgressItem(BaseModel):
    """单条发布进度"""

    id: int
    article_id: int
    article_title: str
    account_id: int
    account_name: str
    platform: str
    platform_name: str
    status: int
    platform_url: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: datetime
    published_at: Optional[datetime] = None


class PublishProgressResponse(BaseModel):
    """发布进度响应"""

    task_id: str
    total: int
    completed: int
    failed: int
    items: List[PublishProgressItem]


class PublishRecordResponse(BaseModel):
    """发布记录响应"""

    id: int
    article_id: int
    article_title: str
    account_id: int
    account_name: str
    platform: str
    platform_name: str
    status: int
    platform_url: Optional[str] = None
    error_msg: Optional[str] = None
    retry_count: int
    created_at: datetime
    published_at: Optional[datetime] = None


# ==================== 账号验证相关 ====================
class AccountCheckResult(BaseModel):
    """单个账号检测结果"""

    account_id: int
    platform: str
    account_name: str
    status_before: int
    is_valid: bool
    message: str
    check_time: str


class AccountCheckSummary(BaseModel):
    """批量检测汇总结果"""

    total: int
    success: int
    failed: int
    results: List[AccountCheckResult]
    check_time: str


# ==================== 分页相关 ====================
from typing import TypeVar, Generic

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """统一分页响应格式"""
    total: int = Field(..., description="总记录数")
    items: List[T] = Field(..., description="当前页数据")
    page: int = Field(..., description="当前页码")
    limit: int = Field(..., description="每页数量")
    pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")
class AutoPublishTaskCreate(BaseModel):
    """创建自动发布任务请求"""

    name: str = Field(..., min_length=1, max_length=200, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    article_ids: List[int] = Field(..., description="文章ID列表")
    account_ids: List[int] = Field(..., description="账号ID列表")
    exec_type: str = Field(
        default="immediate", description="执行类型：immediate=立即执行 scheduled=定时执行 interval=间隔执行"
    )
    scheduled_at: Optional[str] = Field(None, description="定时执行时间（ISO格式）")
    interval_minutes: Optional[int] = Field(None, ge=1, description="间隔执行分钟数")
    declare_ai_content: bool = Field(True, description="是否勾选AI创作内容声明")


class AutoPublishTaskUpdate(BaseModel):
    """更新自动发布任务请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, description="任务状态：pending/running/completed/failed/cancelled")
    scheduled_at: Optional[str] = None
    interval_minutes: Optional[int] = None


class AutoPublishTaskResponse(BaseModel):
    """自动发布任务响应"""

    id: int
    name: str
    description: Optional[str] = None
    article_ids: List[int]
    account_ids: List[int]
    status: str
    exec_type: str
    scheduled_at: Optional[datetime] = None
    interval_minutes: Optional[int] = None
    declare_ai_content: bool = True
    total_count: int
    completed_count: int
    failed_count: int
    error_msg: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutoPublishRecordResponse(BaseModel):
    """自动发布子任务记录响应"""

    id: int
    task_id: int
    article_id: int
    account_id: int
    status: str
    platform_url: Optional[str] = None
    error_msg: Optional[str] = None
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 关联信息（通过join获取）
    article_title: Optional[str] = None
    account_name: Optional[str] = None
    platform: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== 自动发布任务相关 ====================
class AutoPublishTaskDetailResponse(AutoPublishTaskResponse):
    """自动发布任务详情响应（含子任务记录）"""

    records: List[AutoPublishRecordResponse] = []
