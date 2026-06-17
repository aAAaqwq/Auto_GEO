# -*- coding: utf-8 -*-
"""
修复数据库表结构脚本
"""

import sqlite3
from pathlib import Path
from loguru import logger


def check_and_fix_database():
    """
    检查并修复数据库表结构
    """
    # 数据库路径
    # 假设此脚本位于 backend/scripts/ 目录下
    # 向上两级是项目根目录，然后进入 backend/database/
    # 注意：根据原逻辑 BASE_DIR 是 parent.parent，即 backend/
    # 数据库路径是 BASE_DIR / "database" / "auto_geo_v3.db"
    # 即 backend/database/auto_geo_v3.db

    current_file = Path(__file__).resolve()
    # 如果作为模块导入，路径计算方式不变
    BASE_DIR = current_file.parent.parent
    db_path = BASE_DIR / "database" / "auto_geo_v3.db"

    logger.info(f"正在检查数据库结构: {db_path}")

    if not db_path.exists():
        logger.warning(f"数据库文件不存在: {db_path}，跳过结构修复（等待 init_db 创建）")
        return

    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 检查geo_articles表结构
        cursor.execute("PRAGMA table_info(geo_articles)")
        columns = cursor.fetchall()

        # 获取现有列名列表
        existing_columns = [col[1] for col in columns]

        # 定义需要检查的列及其定义
        columns_to_check = [
            ("publish_time", "DATETIME"),
            ("last_check_time", "DATETIME"),
            ("index_details", "TEXT"),
            ("quality_status", "TEXT DEFAULT 'pending'"),
            ("quality_score", "INTEGER"),
            ("ai_score", "INTEGER"),
            ("readability_score", "INTEGER"),
            ("retry_count", "INTEGER DEFAULT 0"),
            ("error_msg", "TEXT"),
            ("publish_logs", "TEXT"),
            ("platform_url", "TEXT"),
            ("index_status", "TEXT DEFAULT 'uncheck'"),
            ("fact_risk_score", "INTEGER"),
            ("duplication_score", "INTEGER"),
            ("platform_risk_score", "INTEGER"),
        ]

        for col_name, col_def in columns_to_check:
            if col_name not in existing_columns:
                logger.info(f"添加缺失的列: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE geo_articles ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    logger.success(f"✓ {col_name} 列添加成功")
                except Exception as e:
                    logger.error(f"✗ 添加 {col_name} 列失败: {e}")
                    conn.rollback()
            else:
                # logger.debug(f"{col_name} 列已存在")
                pass

        # 检查knowledge_categories表结构（RAGFlow同步字段）
        cursor.execute("PRAGMA table_info(knowledge_categories)")
        cat_columns = cursor.fetchall()
        cat_existing = [col[1] for col in cat_columns]

        cat_columns_to_check = [
            ("ragflow_dataset_id", "VARCHAR(100)"),
            ("ragflow_synced", "BOOLEAN DEFAULT 0"),
            ("ragflow_synced_at", "DATETIME"),
        ]

        for col_name, col_def in cat_columns_to_check:
            if col_name not in cat_existing:
                logger.info(f"添加knowledge_categories缺失的列: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE knowledge_categories ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    logger.success(f"✓ knowledge_categories.{col_name} 列添加成功")
                except Exception as e:
                    logger.error(f"✗ 添加 knowledge_categories.{col_name} 列失败: {e}")
                    conn.rollback()

        # 检查knowledge_items表结构（RAGFlow同步字段）
        cursor.execute("PRAGMA table_info(knowledge_items)")
        know_columns = cursor.fetchall()
        know_existing = [col[1] for col in know_columns]

        know_columns_to_check = [
            ("ragflow_document_id", "VARCHAR(100)"),
            ("ragflow_synced", "BOOLEAN DEFAULT 0"),
            ("ragflow_synced_at", "DATETIME"),
            ("ragflow_parsed", "BOOLEAN DEFAULT 0"),
        ]

        for col_name, col_def in know_columns_to_check:
            if col_name not in know_existing:
                logger.info(f"添加knowledge_items缺失的列: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE knowledge_items ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    logger.success(f"✓ knowledge_items.{col_name} 列添加成功")
                except Exception as e:
                    logger.error(f"✗ 添加 knowledge_items.{col_name} 列失败: {e}")
                    conn.rollback()

        # 检查users表结构（用户认证字段）
        cursor.execute("PRAGMA table_info(users)")
        user_columns = cursor.fetchall()
        user_existing = [col[1] for col in user_columns]

        user_columns_to_check = [
            ("role", "VARCHAR(20) DEFAULT 'user'"),
            ("is_active", "BOOLEAN DEFAULT 1"),
            ("last_login", "DATETIME"),
            ("login_count", "INTEGER DEFAULT 0"),
            ("failed_login_attempts", "INTEGER DEFAULT 0"),
            ("locked_until", "DATETIME"),
        ]

        for col_name, col_def in user_columns_to_check:
            if col_name not in user_existing:
                logger.info(f"添加users缺失的列: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    logger.success(f"✓ users.{col_name} 列添加成功")
                except Exception as e:
                    logger.error(f"✗ 添加 users.{col_name} 列失败: {e}")
                    conn.rollback()

        # 如果role列不存在，需要确保第一个用户成为管理员
        if "role" not in user_existing:
            logger.info("设置第一个用户为管理员...")
            try:
                cursor.execute("UPDATE users SET role = 'admin' WHERE id = 1")
                conn.commit()
                logger.success("✓ 第一个用户已设为管理员")
            except Exception as e:
                logger.error(f"✗ 设置管理员失败: {e}")
                conn.rollback()

        # 检查accounts表结构（用户隔离、分组、标签、健康度字段）
        cursor.execute("PRAGMA table_info(accounts)")
        account_columns = cursor.fetchall()
        account_existing = [col[1] for col in account_columns]

        account_columns_to_check = [
            ("user_id", "INTEGER"),
            ("deleted_at", "DATETIME"),
            ("group_id", "INTEGER"),
            ("tags", "TEXT"),
            ("health_score", "INTEGER DEFAULT 100"),
            ("last_check_time", "DATETIME"),
            ("auth_expires_at", "DATETIME"),
            ("browser_type", "VARCHAR(20) DEFAULT 'playwright'"),
            ("adspower_profile_id", "VARCHAR(100)"),
        ]

        added_account_columns = set()
        for col_name, col_def in account_columns_to_check:
            if col_name not in account_existing:
                logger.info(f"添加accounts缺失的列: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE accounts ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    added_account_columns.add(col_name)
                    logger.success(f"✓ accounts.{col_name} 列添加成功")
                except Exception as e:
                    logger.error(f"✗ 添加 accounts.{col_name} 列失败: {e}")
                    conn.rollback()

        # SQLite不能安全地用ALTER TABLE后补外键；索引可以后补，避免列表查询变慢。
        account_available_columns = set(account_existing) | added_account_columns
        account_indexes_to_check = [
            ("ix_accounts_user_id", "user_id"),
            ("ix_accounts_deleted_at", "deleted_at"),
            ("ix_accounts_group_id", "group_id"),
        ]
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes = {row[0] for row in cursor.fetchall()}
        for index_name, col_name in account_indexes_to_check:
            if col_name in account_available_columns and index_name not in existing_indexes:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON accounts ({col_name})")
                    conn.commit()
                except Exception as e:
                    logger.warning(f"accounts.{col_name} 索引创建失败: {e}")
                    conn.rollback()

        # Keep legacy SQLite databases compatible with the current AutoPublishTask model.
        cursor.execute("PRAGMA table_info(auto_publish_tasks)")
        task_columns = cursor.fetchall()
        task_existing = [col[1] for col in task_columns]

        task_columns_to_check = [
            ("triggered_by_user_id", "INTEGER"),
            ("feishu_event_id", "VARCHAR(200)"),
        ]

        added_task_columns = set()
        for col_name, col_def in task_columns_to_check:
            if col_name not in task_existing:
                logger.info(f"Adding missing auto_publish_tasks column: {col_name}...")
                try:
                    cursor.execute(f"ALTER TABLE auto_publish_tasks ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    added_task_columns.add(col_name)
                    logger.success(f"auto_publish_tasks.{col_name} added")
                except Exception as e:
                    logger.error(f"Failed to add auto_publish_tasks.{col_name}: {e}")
                    conn.rollback()

        task_available_columns = set(task_existing) | added_task_columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes = {row[0] for row in cursor.fetchall()}
        if "triggered_by_user_id" in task_available_columns and "ix_apt_triggered_by_user_id" not in existing_indexes:
            try:
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS ix_apt_triggered_by_user_id "
                    "ON auto_publish_tasks (triggered_by_user_id)"
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"Failed to create auto_publish_tasks.triggered_by_user_id index: {e}")
                conn.rollback()

        logger.success("数据库表结构检查和修复完成")

    except Exception as e:
        logger.error(f"数据库修复过程出错: {e}")
    finally:
        # 关闭连接
        conn.close()


if __name__ == "__main__":
    # 配置 logger 输出到控制台
    import sys

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    check_and_fix_database()
