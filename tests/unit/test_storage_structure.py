# -*- coding: utf-8 -*-
"""
检查 storage_state 结构
"""
import sys
import json
from pathlib import Path

# 添加项目根目录到路径（从 tests/ 往上一级）
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import SessionLocal, init_db
from backend.database.models import Account
from backend.services.crypto import decrypt_cookies, decrypt_storage_state

init_db()
db = SessionLocal()

try:
    accounts = db.query(Account).all()

    for account in accounts:
        print(f"\n{'='*60}")
        print(f"账号: {account.account_name} ({account.platform})")
        print(f"{'='*60}")

        # 解密 storage_state
        if account.storage_state:
            try:
                storage = decrypt_storage_state(account.storage_state)
                print(f"\nstorage_state 类型: {type(storage)}")
                if isinstance(storage, dict):
                    print(f"storage_state keys: {list(storage.keys())}")

                    # 检查 localStorage
                    if 'localStorage' in storage:
                        ls = storage['localStorage']
                        print(f"localStorage 类型: {type(ls)}")
                        if isinstance(ls, dict):
                            print(f"localStorage 条目数: {len(ls)}")
                            print(f"localStorage 前5个键: {list(ls.keys())[:5]}")
                        else:
                            print(f"localStorage 内容: {ls}")

                    # 检查 sessionStorage
                    if 'sessionStorage' in storage:
                        ss = storage['sessionStorage']
                        print(f"sessionStorage 类型: {type(ss)}")
                        if isinstance(ss, dict):
                            print(f"sessionStorage 条目数: {len(ss)}")

                    # 检查 cookies
                    if 'cookies' in storage:
                        cookies = storage['cookies']
                        print(f"cookies 类型: {type(cookies)}")
                        if isinstance(co(cookies), list):
                            print(f"cookies 数量: {len(cookies)}")
                    else:
                        # 没有 cookies 字段，说明结构可能有问题
                        print("\n⚠️  storage_state 中没有 'cookies' 字段！")
                        print("这就是问题所在！")
                        print("\n正确的 storage_state 应该包含 'cookies', 'origins' 等字段")

            except Exception as e:
                print(f"解密失败: {e}")

        # 解密 cookies
        if account.cookies:
            try:
                cookies = decrypt_cookies(account.cookies)
                print(f"\n独立 cookies 数量: {len(cookies)}")
                print(f"cookies 名称: {[c['name'] for c in cookies[:5]]}...")
            except Exception as e:
                print(f"解密 cookies 失败: {e}")

finally:
    db.close()
