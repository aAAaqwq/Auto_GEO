# -*- coding: utf-8 -*-
"""
检查账号数据是否正常
"""
import sys
from pathlib import Path

# 添加项目根目录到路径（从 tests/ 往上一级）
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal, init_db
from backend.database.models import Account
from backend.services.crypto import decrypt_cookies, decrypt_storage_state
import json

# 初始化数据库
init_db()

# 创建会话
db = SessionLocal()

try:
    # 获取所有账号
    accounts = db.query(Account).all()
    print(f"共有 {len(accounts)} 个账号\n")
    print("=" * 80)

    for account in accounts:
        print(f"\n账号ID: {account.id}")
        print(f"平台: {account.platform}")
        print(f"账号名称: {account.account_name}")
        print(f"用户名: {account.username}")
        print(f"状态: {account.status}")
        print(f"最后授权时间: {account.last_auth_time}")
        print(f"创建时间: {account.created_at}")

        # 检查 cookies
        has_cookies = bool(account.cookies)
        print(f"\nCookies 字段存在: {has_cookies}")
        if has_cookies:
            print(f"Cookies 长度: {len(account.cookies)} 字符")
            try:
                decrypted_cookies = decrypt_cookies(account.cookies)
                print(f"Cookies 解密成功: {len(decrypted_cookies)} 个")
                if decrypted_cookies:
                    print(f"Cookies 名称: {[c['name'] for c in decrypted_cookies[:5]]}...")
            except Exception as e:
                print(f"Cookies 解密失败: {e}")
        else:
            print("Cookies 字段为空！")

        # 检查 storage_state
        has_storage = bool(account.storage_state)
        print(f"\nStorage_state 字段存在: {has_storage}")
        if has_storage:
            print(f"Storage_state 长度: {len(account.storage_state)} 字符")
            try:
                decrypted_storage = decrypt_storage_state(account.storage_state)
                print(f"Storage_state 解密成功: {type(decrypted_storage)}")
                if isinstance(decrypted_storage, dict):
                    print(f"Storage keys: {list(decrypted_storage.keys())}")
                    if 'localStorage' in decrypted_storage:
                        print(f"localStorage 条目数: {len(decrypted_storage['localStorage'])}")
                        if decrypted_storage['localStorage']:
                            print(f"localStorage 前3个键: {list(decrypted_storage['localStorage'].keys())[:3]}")
            except Exception as e:
                print(f"Storage_state 解密失败: {e}")
        else:
            print("Storage_state 字段为空！")

        print("\n" + "-" * 80)

finally:
    db.close()
