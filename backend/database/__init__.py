# -*- coding: utf-8 -*-
"""
数据库连接管理 - 工业级加固版
支持 SQLite 和 PostgreSQL 双模式
自动检测数据库类型并应用相应优化
"""

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool, QueuePool
from typing import Generator
from loguru import logger
import os

from backend.config import (
    DATABASE_URL,
    DATABASE_DIR,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT,
    DB_POOL_RECYCLE,
    get_database_type,
)

# 检测数据库类型
DB_TYPE = get_database_type()
logger.info(f"🗄️  数据库类型: {DB_TYPE.upper()}")

# 确保数据库目录存在（SQLite需要）
if DB_TYPE == "sqlite":
    DATABASE_DIR.mkdir(exist_ok=True, parents=True)


def create_database_engine():
    """
    创建数据库引擎
    根据数据库类型自动配置连接池和参数
    """
    if DB_TYPE == "postgresql":
        # PostgreSQL 配置
        engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_recycle=DB_POOL_RECYCLE,
            pool_pre_ping=True,  # 连接健康检查
            echo=False,
        )
        logger.info(
            f"✅ PostgreSQL连接池已配置: "
            f"size={DB_POOL_SIZE}, overflow={DB_MAX_OVERFLOW}"
        )
    else:
        # SQLite 配置
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,  # SQLite使用NullPool避免连接池问题
            echo=False,
        )
        logger.info("✅ SQLite引擎已创建 (WAL模式)")

    return engine


# 创建引擎
engine = create_database_engine()


# ==================== SQLite 特定配置 ====================
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    SQLite 连接时设置优化参数
    包括 WAL 模式、外键约束等
    """
    if DB_TYPE == "sqlite":
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=30000000")  # 30MB内存映射
            cursor.close()
            logger.debug("SQLite WAL模式已启用")
        except Exception as e:
            logger.error(f"设置 SQLite Pragma 失败: {e}")


# ==================== PostgreSQL 特定配置 ====================
@event.listens_for(engine, "connect")
def set_postgresql_settings(dbapi_connection, connection_record):
    """
    PostgreSQL 连接时设置优化参数
    """
    if DB_TYPE == "postgresql":
        try:
            cursor = dbapi_connection.cursor()
            # 设置时区
            cursor.execute("SET timezone='Asia/Shanghai'")
            # 设置客户端编码
            cursor.execute("SET client_encoding='UTF8'")
            cursor.close()
            logger.debug("PostgreSQL连接参数已设置")
        except Exception as e:
            logger.error(f"设置 PostgreSQL 参数失败: {e}")


# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 基类
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依赖注入：获取数据库会话
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    初始化数据库表
    逻辑：导入所有模型 -> 检查已存在的表 -> 创建新表
    """
    # 必须在这里导入模型，否则 Base.metadata 不知道有哪些表
    from backend.database.models import (
        Account,
        PublishRecord,
        Project,
        Keyword,
        QuestionVariant,
        IndexCheckRecord,
        GeoArticle,
        ScheduledTask,
        KnowledgeCategory,
        Knowledge,
        Client,
        User,
        ReferenceArticle,
        AutoPublishTask,
        AutoPublishRecord,
        SiteProject,
        SystemConfig,
    )

    # 获取已存在的表名用于对比
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    try:
        # checkfirst=True 会自动处理"表已存在"的情况
        Base.metadata.create_all(bind=engine, checkfirst=True)

        # 再次获取所有表名，对比输出日志
        all_tables = inspect(engine).get_table_names()

        for table in all_tables:
            if table not in existing_tables:
                logger.info(f"✨ 新表创建成功: {table}")

        if DB_TYPE == "sqlite":
            logger.success("✅ 数据库初始化完成 (SQLite + WAL模式)")
        else:
            logger.success("✅ 数据库初始化完成 (PostgreSQL)")

    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {str(e)}")
        raise e


def get_engine_info() -> dict:
    """
    获取数据库引擎信息
    用于健康检查和监控
    """
    info = {
        "type": DB_TYPE,
        "url": DATABASE_URL.replace(
            "://", "://***@").replace("//", "//***@") if "@" in DATABASE_URL else DATABASE_URL,
    }

    if DB_TYPE == "postgresql":
        try:
            with engine.connect() as conn:
                result = conn.execute("SELECT version()").scalar()
                info["version"] = result
                info["pool_size"] = DB_POOL_SIZE
                info["max_overflow"] = DB_MAX_OVERFLOW
        except Exception as e:
            info["error"] = str(e)
    else:
        info["wal_mode"] = True

    return info
