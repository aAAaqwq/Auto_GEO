# -*- coding: utf-8 -*-
"""
数据模型定义 - 工业级完整版
包含基础发布、GEO、监控、知识库及AI招聘所有表结构
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func, ForeignKey, JSON
from sqlalchemy.orm import relationship, backref
from backend.database import Base
from datetime import datetime

# 表参数：允许扩展现有表
TABLE_ARGS = {"extend_existing": True}


class Account(Base):
    """账号表"""

    __tablename__ = "accounts"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    account_name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=True)  # 平台内的用户名
    cookies = Column(Text, nullable=True)
    storage_state = Column(Text, nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(Integer, default=1)
    last_auth_time = Column(DateTime, nullable=True)
    remark = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # 关联关系
    publish_records = relationship("PublishRecord", back_populates="account", cascade="all, delete-orphan")


class ScheduledTask(Base):
    """
    定时任务配置表
    """

    __tablename__ = "scheduled_tasks"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="任务名称")
    task_key = Column(String(50), unique=True, nullable=False, comment="任务标识符(代码中对应key)")
    cron_expression = Column(String(50), nullable=False, comment="Cron表达式")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(Text, nullable=True, comment="任务描述")

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Task {self.name} : {self.cron_expression}>"


# ==================== 客户管理相关表 ====================


class Client(Base):
    """
    客户表
    存储客户/公司信息，一个客户可以有多个项目
    """

    __tablename__ = "clients"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name = Column(String(200), nullable=False, comment="客户名称")
    company_name = Column(String(200), nullable=True, comment="公司名称")
    contact_person = Column(String(100), nullable=True, comment="联系人")
    phone = Column(String(50), nullable=True, comment="联系电话")
    email = Column(String(200), nullable=True, comment="邮箱")
    industry = Column(String(100), nullable=True, comment="行业")
    address = Column(String(500), nullable=True, comment="地址")

    # 备注和状态
    description = Column(Text, nullable=True, comment="客户描述/备注")
    status = Column(Integer, default=1, comment="状态：1=活跃 0=停用")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Client {self.name}>"


# ==================== 已废弃的 Article 类 ====================
# 旧的 Article 模型已被 GeoArticle 替代，保留此注释以防历史引用问题
# class Article(Base):
#     """
#     文章表
#     存储文章内容和基本信息
#     """
#     __tablename__ = "articles"
#     __table_args__ = TABLE_ARGS
#
#     id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
#     title = Column(String(200), nullable=False, comment="文章标题")
#     content = Column(Text, nullable=False, comment="文章正文内容（Markdown/HTML）")
#     ... (其余字段已移除)
# =========================================================


class PublishRecord(Base):
    """
    发布记录表
    记录文章到各平台的发布状态
    """

    __tablename__ = "publish_records"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 外键
    article_id = Column(
        Integer, ForeignKey("geo_articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文章ID"
    )
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True, comment="账号ID"
    )

    # 发布状态
    publish_status = Column(Integer, default=0, comment="发布状态：0=待发布 1=发布中 2=成功 3=失败")

    # 结果
    platform_url = Column(String(500), nullable=True, comment="发布后的文章链接")
    error_msg = Column(Text, nullable=True, comment="错误信息")

    # 重试
    retry_count = Column(Integer, default=0, comment="重试次数")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    published_at = Column(DateTime, nullable=True, comment="实际发布时间")

    # 关联关系
    article = relationship("GeoArticle", back_populates="publish_records")
    account = relationship("Account", back_populates="publish_records")

    def __repr__(self):
        return f"<PublishRecord article_id={self.article_id} account_id={self.account_id} status={self.publish_status}>"


# ==================== GEO相关表 ====================


class Project(Base):
    """
    项目表
    存储项目信息，一个客户可以有多个项目
    """

    __tablename__ = "projects"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联客户
    client_id = Column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True, comment="客户ID"
    )

    # 项目信息
    name = Column(String(200), nullable=False, comment="项目名称")
    company_name = Column(String(200), nullable=True, comment="公司名称")
    domain_keyword = Column(String(200), nullable=True, comment="领域关键词，用于关键词蒸馏")
    description = Column(Text, nullable=True, comment="项目描述")
    industry = Column(String(100), nullable=True, comment="行业")

    # 状态
    status = Column(Integer, default=1, comment="状态：1=活跃 0=停用")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    client = relationship("Client", back_populates="projects")
    keywords = relationship("Keyword", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"


class Keyword(Base):
    """
    关键词表
    存储AI分析出的高价值关键词
    """

    __tablename__ = "keywords"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID"
    )
    keyword = Column(String(200), nullable=False, comment="关键词")
    difficulty_score = Column(Integer, nullable=True, comment="难度评分（0-100）")

    # 状态
    status = Column(String(20), default="active", comment="状态：active=活跃 inactive=停用")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 关联关系
    project = relationship("Project", back_populates="keywords")
    articles = relationship("GeoArticle", back_populates="keyword", cascade="all, delete-orphan")
    question_variants = relationship("QuestionVariant", back_populates="keyword", cascade="all, delete-orphan")
    index_records = relationship("IndexCheckRecord", back_populates="keyword", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Keyword {self.keyword}>"


class QuestionVariant(Base):
    """
    问题变体表
    存储基于关键词生成的不同问法
    """

    __tablename__ = "question_variants"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    keyword_id = Column(
        Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False, index=True, comment="关键词ID"
    )
    question = Column(Text, nullable=False, comment="问题变体")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    # 关联关系
    keyword = relationship("Keyword", back_populates="question_variants")

    def __repr__(self):
        return f"<QuestionVariant {self.question[:30]}...>"


class IndexCheckRecord(Base):
    """
    收录检测记录表
    存储AI平台收录检测结果
    """

    __tablename__ = "index_check_records"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    keyword_id = Column(
        Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False, index=True, comment="关键词ID"
    )
    platform = Column(String(50), nullable=False, comment="检测平台：doubao/qianwen/deepseek")
    question = Column(Text, nullable=False, comment="检测时使用的问题")
    answer = Column(Text, nullable=True, comment="AI回答内容")

    # 检测结果
    keyword_found = Column(Boolean, nullable=True, comment="是否包含关键词")
    company_found = Column(Boolean, nullable=True, comment="是否包含公司名")

    # 时间戳
    check_time = Column(DateTime, default=func.now(), comment="检测时间")

    # 关联关系
    keyword = relationship("Keyword", back_populates="index_records")

    def __repr__(self):
        return f"<IndexCheckRecord keyword_id={self.keyword_id} platform={self.platform}>"


class GeoArticle(Base):
    """
    GEO文章表
    存储AI生成的文章及质检信息
    """

    __tablename__ = "geo_articles"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    keyword_id = Column(
        Integer, ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False, index=True, comment="关键词ID"
    )
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True, comment="项目ID"
    )
    title = Column(Text, nullable=True, comment="文章标题")
    content = Column(Text, nullable=False, comment="文章正文内容")

    # 质检相关
    quality_score = Column(Integer, nullable=True, comment="质量评分（0-100）")
    ai_score = Column(Integer, nullable=True, comment="AI味检测分数（0-100，越高越像AI）")
    readability_score = Column(Integer, nullable=True, comment="可读性评分（0-100）")
    quality_status = Column(String(20), default="pending", comment="质检状态：pending=待检查 passed=通过 failed=未通过")

    # 发布相关
    platform = Column(String(50), nullable=True, comment="目标发布平台：仅在配置发布时填写，生成阶段为空")
    account_id = Column(Integer, nullable=True, comment="目标账号ID：仅在配置发布时填写，生成阶段为空")
    publish_status = Column(
        String(20),
        default="draft",
        comment="发布状态：draft=草稿 generating=生成中 completed=已生成待分发 scheduled=已配置定时发布 publishing=发布中 published=已发布 failed=发布失败",
    )
    publish_time = Column(DateTime, nullable=True, comment="发布时间")
    scheduled_at = Column(DateTime, nullable=True, comment="定时发布时间：仅在定时发布时设置")

    # 发布策略字段（新增）
    target_platforms = Column(
        JSON, nullable=True, comment="预设目标平台列表（JSON数组）：如 ['zhihu', 'sohu', 'baijiahao']，用于多平台发布"
    )
    publish_strategy = Column(
        String(20), default="draft", comment="发布策略：draft=仅生成草稿 immediate=生成后立即发布 scheduled=定时发布"
    )

    # 强壮性与重试 (Added back from v1)
    retry_count = Column(Integer, default=0)
    error_msg = Column(Text, nullable=True)
    publish_logs = Column(Text, nullable=True)
    platform_url = Column(String(500), nullable=True)

    # 效果监测 (Added back from v1)
    index_status = Column(String(20), default="uncheck")
    last_check_time = Column(DateTime, nullable=True)
    index_details = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    keyword = relationship("Keyword", back_populates="articles")
    publish_records = relationship("PublishRecord", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<GeoArticle id={self.id} keyword_id={self.keyword_id}>"


# ==================== 知识库相关表 ====================


class KnowledgeCategory(Base):
    """
    知识库分类表（企业分类）
    存储企业/客户的知识库分类信息
    RAGFlow为主存储，SQLite为缓存
    """

    __tablename__ = "knowledge_categories"
    __table_args__ = TABLE_ARGS

    # 主键（本地ID）
    id = Column(Integer, primary_key=True, autoincrement=True, comment="本地主键ID")

    # RAGFlow唯一标识（主数据源）
    ragflow_dataset_id = Column(
        String(100), unique=True, nullable=True, index=True, comment="RAGFlow知识库ID（唯一标识，主数据源）"
    )

    # 元数据字段（从RAGFlow同步的缓存）
    name = Column(String(200), nullable=False, comment="企业/分类名称")
    industry = Column(String(100), nullable=True, comment="所属行业")
    description = Column(Text, nullable=True, comment="分类描述")
    tags = Column(String(500), nullable=True, comment="标签，逗号分隔")
    color = Column(String(20), default="#6366f1", comment="主题颜色")

    # 状态
    status = Column(Integer, default=1, comment="状态：1=活跃 0=停用")

    # 同步状态管理
    sync_status = Column(
        String(20), default="pending", comment="同步状态：pending=待同步 synced=已同步 syncing=同步中 error=同步失败"
    )
    ragflow_synced = Column(Boolean, default=False, comment="是否已同步到RAGFlow（已废弃，使用sync_status）")
    ragflow_synced_at = Column(DateTime, nullable=True, comment="同步时间")
    last_sync_at = Column(DateTime, nullable=True, comment="最后同步时间")

    # 统计字段（从RAGFlow同步）
    knowledge_count = Column(Integer, default=0, comment="知识数量（缓存）")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系
    items = relationship("Knowledge", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<KnowledgeCategory {self.name} (RAGFlow: {self.ragflow_dataset_id})>"


class Knowledge(Base):
    """
    知识库条目表
    存储企业相关的知识内容
    RAGFlow为主存储，SQLite为缓存
    """

    __tablename__ = "knowledge_items"
    __table_args__ = TABLE_ARGS

    # 主键（本地ID）
    id = Column(Integer, primary_key=True, autoincrement=True, comment="本地主键ID")

    # RAGFlow唯一标识（主数据源）
    ragflow_document_id = Column(
        String(100), unique=True, nullable=True, index=True, comment="RAGFlow文档ID（唯一标识，主数据源）"
    )

    # 关联到RAGFlow知识库
    ragflow_dataset_id = Column(String(100), nullable=False, index=True, comment="所属RAGFlow知识库ID")

    # 向后兼容的外键关系（用于SQLAlchemy关系映射，实际主要使用ragflow_dataset_id）
    category_id = Column(
        Integer,
        ForeignKey("knowledge_categories.id", ondelete="CASCADE"),
        nullable=False,  # 与数据库表结构保持一致
        index=True,
        comment="分类ID（向后兼容，实际主要使用ragflow_dataset_id）",
    )

    # 元数据字段（从RAGFlow同步的缓存）
    title = Column(String(200), nullable=False, comment="知识标题")
    content = Column(Text, nullable=False, comment="知识内容（本地缓存摘要，完整内容在RAGFlow中）")
    type = Column(
        String(50),
        default="other",
        comment="知识类型：company_intro=企业介绍 product=产品服务 industry=行业知识 faq=常见问题 other=其他",
    )

    # 状态
    status = Column(Integer, default=1, comment="状态：1=启用 0=停用")

    # 同步状态管理
    sync_status = Column(
        String(20), default="pending", comment="同步状态：pending=待同步 synced=已同步 syncing=同步中 error=同步失败"
    )
    ragflow_synced = Column(Boolean, default=False, comment="是否已同步到RAGFlow（已废弃，使用sync_status）")
    ragflow_synced_at = Column(DateTime, nullable=True, comment="同步时间")
    ragflow_parsed = Column(Boolean, default=False, comment="文档是否已解析")
    last_sync_at = Column(DateTime, nullable=True, comment="最后同步时间")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系（保留向后兼容）
    category = relationship("KnowledgeCategory", back_populates="items")

    def __repr__(self):
        return f"<Knowledge {self.title} (RAGFlow: {self.ragflow_document_id})>"


# ==================== 用户相关表 ====================


class User(Base):
    """
    用户表
    存储系统用户信息，支持用户认证和角色管理
    """

    __tablename__ = "users"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    username = Column(String(100), nullable=False, unique=True, index=True, comment="用户名")
    email = Column(String(200), nullable=True, unique=True, index=True, comment="邮箱")
    password_hash = Column(String(255), nullable=False, comment="密码哈希（bcrypt）")

    # 角色管理
    role = Column(
        String(20),
        default="user",
        nullable=False,
        index=True,
        comment="角色：admin=管理员 user=普通用户"
    )

    # 状态管理
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="是否激活：True=激活 False=禁用"
    )
    status = Column(Integer, default=1, comment="状态：1=活跃 0=禁用（保留字段，优先使用is_active）")

    # 登录追踪
    last_login = Column(DateTime, nullable=True, comment="最后登录时间")
    login_count = Column(Integer, default=0, comment="登录次数")

    # 安全相关
    failed_login_attempts = Column(Integer, default=0, comment="连续登录失败次数")
    locked_until = Column(DateTime, nullable=True, comment="账户锁定截止时间")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<User {self.username} role={self.role} active={self.is_active}>"

    @property
    def is_admin(self) -> bool:
        """检查是否为管理员"""
        return self.role == "admin"

    @property
    def is_locked(self) -> bool:
        """检查账户是否被锁定"""
        if self.locked_until is None:
            return False
        from datetime import datetime
        return datetime.now() < self.locked_until


# ==================== 系统配置表 ====================


class SystemConfig(Base):
    """
    系统配置表
    存储系统级别的配置项，支持key-value存储和配置分类
    """

    __tablename__ = "system_configs"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 配置键值
    config_key = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="配置键（唯一标识符）"
    )
    config_value = Column(Text, nullable=True, comment="配置值（JSON字符串或纯文本）")

    # 配置分类
    category = Column(
        String(50),
        default="general",
        nullable=False,
        index=True,
        comment="配置分类：general=通用 auth=认证 security=安全 email=邮件 storage=存储"
    )

    # 配置描述
    description = Column(Text, nullable=True, comment="配置项描述/说明")

    # 数据类型（用于类型转换提示）
    value_type = Column(
        String(20),
        default="string",
        nullable=False,
        comment="值类型：string=字符串 int=整数 float=浮点数 bool=布尔 json=JSON对象"
    )

    # 是否可编辑
    is_editable = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否可通过界面编辑：True=可编辑 False=只读"
    )

    # 是否敏感配置（如API密钥）
    is_sensitive = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为敏感配置（如密码、密钥）：True=敏感 False=普通"
    )

    # 状态
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="是否启用：True=启用 False=禁用"
    )

    # 排序权重
    sort_order = Column(Integer, default=0, comment="排序权重（越小越靠前）")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="最后更新用户ID")

    def __repr__(self):
        return f"<SystemConfig {self.config_key}={self.config_value[:30] if self.config_value else None}>"

    def get_value(self):
        """
        根据value_type自动转换并返回配置值
        """
        import json
        from datetime import datetime

        if self.config_value is None:
            return None

        try:
            if self.value_type == "string":
                return self.config_value
            elif self.value_type == "int":
                return int(self.config_value)
            elif self.value_type == "float":
                return float(self.config_value)
            elif self.value_type == "bool":
                return self.config_value.lower() in ("true", "1", "yes", "on")
            elif self.value_type == "json":
                return json.loads(self.config_value)
            else:
                return self.config_value
        except (ValueError, json.JSONDecodeError) as e:
            return self.config_value

    def set_value(self, value):
        """
        根据value_type自动转换并设置配置值
        """
        import json

        if value is None:
            self.config_value = None
            return

        try:
            if self.value_type == "string":
                self.config_value = str(value)
            elif self.value_type == "int":
                self.config_value = str(int(value))
            elif self.value_type == "float":
                self.config_value = str(float(value))
            elif self.value_type == "bool":
                self.config_value = "true" if bool(value) else "false"
            elif self.value_type == "json":
                self.config_value = json.dumps(value, ensure_ascii=False)
            else:
                self.config_value = str(value)
        except (ValueError, TypeError) as e:
            self.config_value = str(value)


# ==================== 参考文章表（爆火文章收集）====================


class ReferenceArticle(Base):
    """
    参考文章表
    存储从各平台采集的爆火/热门文章，用于内容创作参考
    """

    __tablename__ = "reference_articles"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 基本信息
    title = Column(String(500), nullable=False, comment="文章标题")
    url = Column(String(1000), nullable=False, unique=True, comment="原文链接")
    content = Column(Text, nullable=False, comment="文章正文（已清洗）")
    summary = Column(Text, nullable=True, comment="文章摘要")

    # 来源信息
    platform = Column(String(50), nullable=False, index=True, comment="来源平台：zhihu/toutiao等")
    author = Column(String(200), nullable=True, comment="作者名称")
    publish_time = Column(String(50), nullable=True, comment="原文发布时间")

    # 热度指标
    likes = Column(Integer, default=0, comment="点赞数")
    reads = Column(Integer, default=0, comment="阅读量")
    comments = Column(Integer, default=0, comment="评论数")

    # 采集信息
    keyword = Column(String(200), nullable=True, index=True, comment="采集时使用的关键词")
    collected_at = Column(DateTime, default=func.now(), comment="采集时间")

    # RAGFlow 同步状态
    ragflow_synced = Column(Boolean, default=False, comment="是否已同步到RAGFlow")
    ragflow_doc_id = Column(String(100), nullable=True, comment="RAGFlow文档ID")
    ragflow_sync_time = Column(DateTime, nullable=True, comment="RAGFlow同步时间")

    # 状态
    status = Column(Integer, default=1, comment="状态：1=正常 0=已删除")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<ReferenceArticle {self.title[:30]}... ({self.platform})>"


# ==================== AEO网站信息收集表 ====================
class SiteProject(Base):
    __tablename__ = "site_projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, comment="项目名称，如：极速物流官网")
    site_id = Column(String, unique=True, index=True, comment="唯一标识，用于生成路径")

    # 核心配置：存储前端传来的那个大 JSON
    config_data = Column(JSON, comment="网站的全量配置数据")

    # 状态管理
    deploy_path = Column(String, nullable=True, comment="生成的本地 index.html 路径")
    preview_url = Column(String, nullable=True, comment="本地预览 URL")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ==================== 自动发布任务系统 ====================


class AutoPublishTask(Base):
    """
    自动发布任务表
    用于管理用户创建的后台发布任务队列
    """

    __tablename__ = "auto_publish_tasks"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 任务基本信息
    name = Column(String(200), nullable=False, comment="任务名称")
    description = Column(Text, nullable=True, comment="任务描述")

    # 发布配置（JSON格式存储文章和账号ID列表）
    article_ids = Column(JSON, nullable=False, comment="文章ID列表 [1,2,3]")
    account_ids = Column(JSON, nullable=False, comment="账号ID列表 [1,2,3]")

    # 发布选项
    declare_ai_content = Column(Boolean, default=True, comment="是否勾选AI创作内容声明")

    # 任务状态
    status = Column(
        String(20),
        default="pending",
        comment="任务状态：pending=待执行 running=执行中 completed=已完成 failed=失败 cancelled=已取消",
    )

    # 执行类型
    exec_type = Column(
        String(20), default="immediate", comment="执行类型：immediate=立即执行 scheduled=定时执行 interval=间隔执行"
    )

    # 定时配置
    scheduled_at = Column(DateTime, nullable=True, comment="计划执行时间")
    interval_minutes = Column(Integer, nullable=True, comment="间隔执行分钟数")

    # 执行结果
    total_count = Column(Integer, default=0, comment="总发布任务数（文章数×账号数）")
    completed_count = Column(Integer, default=0, comment="已完成数量")
    failed_count = Column(Integer, default=0, comment="失败数量")

    # 错误信息
    error_msg = Column(Text, nullable=True, comment="错误信息")
    last_error_at = Column(DateTime, nullable=True, comment="最后错误时间")

    # 执行时间
    started_at = Column(DateTime, nullable=True, comment="实际开始时间")
    completed_at = Column(DateTime, nullable=True, comment="实际完成时间")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关联关系：一对多，级联删除子记录
    records = relationship(
        "AutoPublishRecord", back_populates="task", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self):
        return f"<AutoPublishTask {self.name} status={self.status}>"


class AutoPublishRecord(Base):
    """
    自动发布子任务记录表
    记录每个自动发布任务中的单次发布结果
    """

    __tablename__ = "auto_publish_records"
    __table_args__ = TABLE_ARGS

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    # 关联自动发布任务
    task_id = Column(
        Integer,
        ForeignKey("auto_publish_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属自动发布任务ID",
    )

    # 发布目标和内容
    article_id = Column(
        Integer, ForeignKey("geo_articles.id", ondelete="CASCADE"), nullable=False, index=True, comment="文章ID"
    )
    account_id = Column(
        Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True, comment="账号ID"
    )

    # 发布状态
    status = Column(
        String(20),
        default="pending",
        comment="状态：pending=待发布 publishing=发布中 success=成功 failed=失败 skipped=跳过",
    )

    # 发布结果
    platform_url = Column(String(500), nullable=True, comment="发布后的文章链接")
    error_msg = Column(Text, nullable=True, comment="错误信息")

    # 重试信息
    retry_count = Column(Integer, default=0, comment="重试次数")
    max_retries = Column(Integer, default=3, comment="最大重试次数")

    # 时间戳
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 关联关系
    # 艹！级联删除配置：删除任务时自动删除关联的发布记录
    task = relationship("AutoPublishTask", back_populates="records")
    article = relationship("GeoArticle")
    account = relationship("Account")

    def __repr__(self):
        return f"<AutoPublishRecord task_id={self.task_id} article_id={self.article_id} status={self.status}>"
