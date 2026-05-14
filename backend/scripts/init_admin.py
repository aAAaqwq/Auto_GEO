# -*- coding: utf-8 -*-
"""
系统初始化脚本
创建默认管理员用户和系统配置

使用方法:
    python -m backend.scripts.init_admin
    或
    python backend/scripts/init_admin.py

环境变量:
    ADMIN_USERNAME: 管理员用户名 (默认: admin)
    ADMIN_PASSWORD: 管理员密码 (默认: 随机生成)
    ADMIN_EMAIL: 管理员邮箱 (默认: admin@example.com)
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import bcrypt
from backend.database import SessionLocal, init_db
from backend.database.models import User, SystemConfig
from loguru import logger

# 默认系统配置
DEFAULT_SYSTEM_CONFIGS = [
    # 通用配置
    {
        "config_key": "site_name",
        "config_value": "Auto GEO 内容发布平台",
        "category": "general",
        "description": "站点名称",
        "value_type": "string",
        "is_editable": True,
        "sort_order": 1,
    },
    {
        "config_key": "site_description",
        "config_value": "基于GEO（生成式引擎优化）的智能内容发布平台",
        "category": "general",
        "description": "站点描述",
        "value_type": "string",
        "is_editable": True,
        "sort_order": 2,
    },
    # 认证配置
    {
        "config_key": "login_max_attempts",
        "config_value": "5",
        "category": "auth",
        "description": "最大登录失败次数（超过则锁定账户）",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 1,
    },
    {
        "config_key": "login_lock_duration",
        "config_value": "30",
        "category": "auth",
        "description": "账户锁定持续时间（分钟）",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 2,
    },
    {
        "config_key": "session_expire_hours",
        "config_value": "24",
        "category": "auth",
        "description": "会话过期时间（小时）",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 3,
    },
    {
        "config_key": "password_min_length",
        "config_value": "8",
        "category": "auth",
        "description": "密码最小长度",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 4,
    },
    # 安全配置
    {
        "config_key": "enable_register",
        "config_value": "true",
        "category": "security",
        "description": "是否开放用户注册",
        "value_type": "bool",
        "is_editable": True,
        "sort_order": 1,
    },
    {
        "config_key": "require_email_verify",
        "config_value": "false",
        "category": "security",
        "description": "是否需要邮箱验证",
        "value_type": "bool",
        "is_editable": True,
        "sort_order": 2,
    },
    # 发布配置
    {
        "config_key": "publish_retry_max",
        "config_value": "3",
        "category": "publish",
        "description": "发布失败最大重试次数",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 1,
    },
    {
        "config_key": "publish_interval_seconds",
        "config_value": "60",
        "category": "publish",
        "description": "发布间隔（秒）",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 2,
    },
    # AI配置
    {
        "config_key": "ai_content_default_platform",
        "config_value": "openai",
        "category": "ai",
        "description": "默认AI内容生成平台",
        "value_type": "string",
        "is_editable": True,
        "sort_order": 1,
    },
    {
        "config_key": "ai_content_max_tokens",
        "config_value": "2000",
        "category": "ai",
        "description": "AI生成内容最大token数",
        "value_type": "int",
        "is_editable": True,
        "sort_order": 2,
    },
]


def generate_random_password(length: int = 12) -> str:
    """生成随机密码"""
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    """加密密码（使用bcrypt）"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_admin_user(db) -> tuple[User, str]:
    """创建默认管理员用户"""

    # 从环境变量读取配置
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "")
    email = os.getenv("ADMIN_EMAIL", "admin@example.com")

    # 如果没有提供密码，生成随机密码
    if not password:
        password = generate_random_password()
        logger.warning(f"⚠️  未设置 ADMIN_PASSWORD 环境变量，已生成随机密码")

    # 检查是否已存在管理员用户
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        logger.info(f"✅ 管理员用户已存在: {existing_admin.username}")
        return existing_admin, ""

    # 检查用户名是否已被使用
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        logger.error(f"❌ 用户名 '{username}' 已被使用，请设置 ADMIN_USERNAME 环境变量")
        raise ValueError(f"用户名 '{username}' 已被使用")

    # 创建管理员用户
    admin_user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="admin",
        is_active=True,
        login_count=0,
        failed_login_attempts=0,
    )

    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    logger.success(f"✅ 管理员用户创建成功: {username}")
    return admin_user, password


def create_system_configs(db, admin_user: User = None):
    """创建默认系统配置"""

    created_count = 0
    updated_count = 0

    for config_data in DEFAULT_SYSTEM_CONFIGS:
        config_key = config_data["config_key"]

        # 检查是否已存在
        existing = db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()

        if existing:
            # 更新描述和分类（保留用户修改的值）
            existing.category = config_data["category"]
            existing.description = config_data["description"]
            existing.value_type = config_data["value_type"]
            existing.sort_order = config_data["sort_order"]
            if admin_user:
                existing.updated_by = admin_user.id
            updated_count += 1
        else:
            # 创建新配置
            config = SystemConfig(
                config_key=config_key,
                config_value=config_data["config_value"],
                category=config_data["category"],
                description=config_data["description"],
                value_type=config_data["value_type"],
                is_editable=config_data["is_editable"],
                is_sensitive=False,
                is_active=True,
                sort_order=config_data["sort_order"],
                updated_by=admin_user.id if admin_user else None,
            )
            db.add(config)
            created_count += 1

    db.commit()

    logger.success(f"✅ 系统配置初始化完成: 新建 {created_count} 项, 更新 {updated_count} 项")

    return created_count, updated_count


def print_admin_info(username: str, password: str, email: str):
    """打印管理员信息"""
    print("\n" + "=" * 60)
    print("🔐 管理员账户信息")
    print("=" * 60)
    print(f"用户名: {username}")
    print(f"密码: {password}")
    print(f"邮箱: {email}")
    print(f"角色: admin")
    print("=" * 60)
    print("⚠️  请妥善保存以上信息，特别是密码！")
    print("=" * 60 + "\n")


def main():
    """主函数"""
    print("\n🚀 系统初始化脚本启动...\n")

    # 初始化数据库表
    try:
        init_db()
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        sys.exit(1)

    db = SessionLocal()

    try:
        # 创建管理员用户
        admin_user, password = create_admin_user(db)

        # 如果生成了新密码，打印信息
        if password:
            username = os.getenv("ADMIN_USERNAME", "admin")
            email = os.getenv("ADMIN_EMAIL", "admin@example.com")
            print_admin_info(username, password, email)

            # 提示保存密码
            print("💡 建议操作:")
            print("1. 将密码保存到安全的地方")
            print("2. 设置环境变量以避免下次生成随机密码:")
            print(f"   export ADMIN_PASSWORD='{password}'")
            print("3. 登录后修改密码\n")

        # 创建系统配置
        create_system_configs(db, admin_user)

        logger.success("✅ 系统初始化完成！")

    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
