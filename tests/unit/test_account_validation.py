# -*- coding: utf-8 -*-
"""
详细测试账号授权验证逻辑
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到路径（从 tests/ 往上一级）
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal, init_db
from backend.database.models import Account
from backend.services.account_validator import AccountValidator
from backend.config import PLATFORMS

# 初始化数据库
init_db()


async def test_single_account(account_id: int):
    """测试单个账号的验证"""
    from backend.database import SessionLocal
    from backend.services.account_validator import AccountValidator

    db = SessionLocal()
    validator = AccountValidator()

    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            print(f"账号 {account_id} 不存在")
            return

        print(f"\n{'='*80}")
        print(f"开始验证账号: {account.account_name} ({account.platform})")
        print(f"{'='*80}")

        # 基础信息
        print(f"\n[基础信息]")
        print(f"  账号ID: {account.id}")
        print(f"  平台: {account.platform}")
        print(f"  账号名: {account.account_name}")
        print(f"  用户名: {account.username}")
        print(f"  当前状态: {account.status}")
        print(f"  最后授权时间: {account.last_auth_time}")

        # 检查数据完整性
        print(f"\n[数据完整性]")
        print(f"  Cookies存在: {bool(account.cookies)}")
        print(f"  Storage_state存在: {bool(account.storage_state)}")

        if not account.cookies or not account.storage_state:
            print("  ❌ 数据不完整，跳过验证")
            return

        # 平台配置
        platform_config = PLATFORMS.get(account.platform)
        if platform_config:
            test_url = platform_config.get("publish_url") or platform_config.get("home_url")
            print(f"\n[平台配置]")
            print(f"  测试URL: {test_url}")
        else:
            print(f"  ❌ 不支持的平台: {account.platform}")
            return

        # 启动验证
        print(f"\n[开始验证...]")
        result = await validator._check_account_auth(account, db)

        print(f"\n[验证结果]")
        print(f"  是否有效: {result.get('is_valid')}")
        print(f"  消息: {result.get('message')}")
        print(f"  检查时间: {result.get('check_time')}")
        print(f"  验证后状态: {account.status}")

        if not result.get('is_valid'):
            print(f"\n  ⚠️  授权验证失败！")
        else:
            print(f"\n  ✅ 授权验证成功！")

    finally:
        db.close()
        await validator._stop_browser()


async def main():
    """主函数"""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        accounts = db.query(Account).all()
        print(f"共找到 {len(accounts)} 个账号")

        if not accounts:
            print("没有账号可测试")
            return

        # 测试第一个账号
        account = accounts[0]
        await test_single_account(account.id)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
