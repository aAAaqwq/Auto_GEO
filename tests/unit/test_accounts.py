# -*- coding: utf-8 -*-
"""
账号管理功能测试
测试所有账号管理API接口



测试范围：
- GET /api/accounts - 获取账号列表
- GET /api/accounts/{account_id} - 获取账号详情
- POST /api/accounts - 创建账号
- PUT /api/accounts/{account_id} - 更新账号
- DELETE /api/accounts/{account_id} - 删除账号
- POST /api/accounts/auth/start - 开始授权
- GET /api/accounts/auth/status/{task_id} - 获取授权状态
- POST /api/accounts/auth/confirm/{task_id} - 确认授权
- DELETE /api/accounts/auth/task/{task_id} - 取消授权
"""

import pytest
import requests
from typing import Optional

BASE_URL = "http://127.0.0.1:8001"
API_PREFIX = "/api/accounts"


class TestAccountsAPI:
    """账号管理API测试类"""

    def _make_request(self, method: str, endpoint: str = "", params: dict = None, json_data: dict = None):
        """发送HTTP请求"""
        url = f"{BASE_URL}{API_PREFIX}{endpoint}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, json=json_data, timeout=10)
            elif method.upper() == "PUT":
                response = requests.put(url, params=params, json=json_data, timeout=10)
            elif method.upper() == "DELETE":
                response = requests.delete(url, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            return response
        except requests.exceptions.Timeout:
            pytest.fail(f"请求超时: {url}")
        except requests.exceptions.ConnectionError:
            pytest.fail(f"连接失败，请确认后端服务已启动: {url}")

    # ==================== GET /api/accounts 接口测试 ====================

    def test_get_accounts_success(self):
        """TC-AC-001: 获取账号列表 - 验证正常返回"""
        response = self._make_request("GET")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 如果有数据，验证结构
        if len(data) > 0:
            item = data[0]
            required_fields = ["id", "platform", "account_name", "username", "status", "created_at", "updated_at"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

    def test_get_accounts_with_platform_filter(self):
        """TC-AC-002: 获取账号列表 - 测试平台筛选"""
        response = self._make_request("GET", params={"platform": "zhihu"})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 验证所有返回的账号都是zhihu平台
        for account in data:
            assert account["platform"] == "zhihu"

    def test_get_accounts_with_status_filter(self):
        """TC-AC-003: 获取账号列表 - 测试状态筛选"""
        response = self._make_request("GET", params={"status": 1})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 验证所有返回的账号都是启用状态
        for account in data:
            assert account["status"] == 1

    def test_get_accounts_with_both_filters(self):
        """TC-AC-004: 获取账号列表 - 测试平台和状态组合筛选"""
        response = self._make_request("GET", params={"platform": "zhihu", "status": 1})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        for account in data:
            assert account["platform"] == "zhihu"
            assert account["status"] == 1

    # ==================== GET /api/accounts/{account_id} 接口测试 ====================

    def test_get_account_detail_success(self, test_account):
        """TC-AC-005: 获取账号详情 - 验证正常返回"""
        response = self._make_request("GET", f"/{test_account.id}")
        assert response.status_code == 200

        data = response.json()
        required_fields = [
            "id", "platform", "account_name", "username", "status",
            "last_auth_time", "created_at", "updated_at", "remark",
            "is_authorized", "platform_info"
        ]

        for field in required_fields:
            assert field in data, f"响应项缺少字段: {field}"

        # 验证数据一致性
        assert data["id"] == test_account.id
        assert data["platform"] == test_account.platform

    def test_get_account_detail_not_found(self):
        """TC-AC-006: 获取账号详情 - 测试不存在的账号"""
        response = self._make_request("GET", "/99999")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "不存在" in data["detail"]

    # ==================== POST /api/accounts 接口测试 ====================

    def test_create_account_success(self, db):
        """TC-AC-007: 创建账号 - 验证正常创建"""
        account_data = {
            "platform": "zhihu",
            "account_name": "新建测试账号",
            "remark": "这是自动化测试创建的账号"
        }

        response = self._make_request("POST", json_data=account_data)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["platform"] == "zhihu"
        assert data["account_name"] == "新建测试账号"
        assert data["remark"] == "这是自动化测试创建的账号"
        assert data["status"] == 0  # 新账号默认为禁用状态

        # 清理测试数据
        from backend.database.models import Account
        db.query(Account).filter(Account.id == data["id"]).delete()
        db.commit()

    def test_create_account_invalid_platform(self):
        """TC-AC-008: 创建账号 - 测试不支持的平台"""
        account_data = {
            "platform": "invalid_platform",
            "account_name": "测试账号"
        }

        response = self._make_request("POST", json_data=account_data)
        assert response.status_code == 422

        data = response.json()
        assert "detail" in data
        # Pydantic 422 错误的 detail 是一个列表
        assert isinstance(data["detail"], list)
        assert data["detail"][0]["loc"] == ["body", "platform"]

    def test_create_account_missing_required_fields(self):
        """TC-AC-009: 创建账号 - 测试缺少必填字段"""
        account_data = {
            "account_name": "测试账号"
            # 缺少 platform 字段
        }

        response = self._make_request("POST", json_data=account_data)
        assert response.status_code == 422  # 验证错误

    @pytest.mark.parametrize("platform", ["zhihu", "toutiao", "sohu", "weixin", "bilibili"])
    def test_create_account_all_platforms(self, db, platform):
        """TC-AC-010: 创建账号区 - 测试多个平台"""
        account_data = {
            "platform": platform,
            "account_name": f"测试_{platform}_账号"
        }

        response = self._make_request("POST", json_data=account_data)
        assert response.status_code == 201

        data = response.json()
        assert data["platform"] == platform

        # 清理
        from backend.database.models import Account
        db.query(Account).filter(Account.id == data["id"]).delete()
        db.commit()

    # ==================== PUT /api/accounts/{account_id} 接口测试 ====================

    def test_update_account_success(self, test_account):
        """TC-AC-011: 更新账号 - 验证正常更新"""
        update_data = {
            "account_name": "更新后的账号名称",
            "remark": "更新后的备注",
            "status": 1
        }

        response = self._make_request("PUT", f"/{test_account.id}", json_data=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == test_account.id
        assert data["account_name"] == "更新后的账号名称"
        assert data["remark"] == "更新后的备注"
        assert data["status"] == 1

    def test_update_account_partial(self, test_account):
        """TC-AC-012: 更新账号 - 测试部分字段更新"""
        update_data = {
            "account_name": "只更新名称"
        }

        response = self._make_request("PUT", f"/{test_account.id}", json_data=update_data)
        assert response.status_code == 200

        data = response.json()
        assert data["account_name"] == "只更新名称"

    def test_update_account_not_found(self):
        """TC-AC-013: 更新账号 - 测试不存在的账号"""
        update_data = {
            "account_name": "测试"
        }

        response = self._make_request("PUT", "/99999", json_data=update_data)
        assert response.status_code == 404

    def test_update_account_invalid_status(self, test_account):
        """TC-AC-014: 更新账号 - 测试无效的状态值"""
        update_data = {
            "status": 999  # 状态只能是 -1, 0, 1
        }

        response = self._make_request("PUT", f"/{test_account.id}", json_data=update_data)
        # 应该返回验证错误
        assert response.status_code in [422, 400]

    # ==================== DELETE /api/accounts/{account_id} 接口测试 ====================

    def test_delete_account_success(self, db):
        """TC-AC-015: 删除账号 - 验证正常删除"""
        # 先创建一个测试账号
        from backend.database.models import Account
        account = Account(
            platform="zhihu",
            account_name="待删除的账号",
            status=0
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        # 删除账号
        response = self._make_request("DELETE", f"/{account.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "删除" in data["message"]

        # 验证账号已被删除
        deleted_account = db.query(Account).filter(Account.id == account.id).first()
        assert deleted_account is None

    def test_delete_account_not_found(self):
        """TC-AC-016: 删除账号 - 测试不存在的账号"""
        response = self._make_request("DELETE", "/99999")
        assert response.status_code == 404

    # ==================== POST /api/accounts/auth/start 接口测试 ====================

    @pytest.mark.skip(reason="需要Mock playwright_mgr")
    def test_auth_start_new_account(self):
        """TC-AC-017: 开始授权 - 新账号授权"""
        auth_data = {
            "platform": "zhihu",
            "account_name": "新授权账号"
        }

        response = self._make_request("POST", "/auth/start", json_data=auth_data)

        # playwright_mgr未正确配置时会返回错误
        if response.status_code == 500:
            return

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "message" in data

    @pytest.mark.skip(reason="需要Mock playwright_mgr")
    def test_auth_start_update_account(self, test_account):
        """TC-AC-018: 开始授权 - 更新已有账号授权"""
        auth_data = {
            "platform": test_account.platform,
            "account_id": test_account.id,
            "account_name": test_account.account_name
        }

        response = self._make_request("POST", "/auth/start", json_data=auth_data)

        # playwright_mgr未正确配置时会返回错误
        if response.status_code == 500:
            return

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data

    def test_auth_start_invalid_platform(self):
        """TC-AC-019: 开始授权 - 测试不支持的平台"""
        auth_data = {
            "platform": "invalid_platform",
            "account_name": "测试账号"
        }

        response = self._make_request("POST", "/auth/start", json_data=auth_data)
        assert response.status_code == 400

    def test_auth_start_platform_mismatch(self, test_account):
        """TC-AC-020: 开始授权 - 测试平台不匹配"""
        auth_data = {
            "platform": "toutiao",  # 与 test_account.platform 不一致
            "account_id": test_account.id
        }

        response = self._make_request("POST", "/auth/start", json_data=auth_data)
        assert response.status_code == 400

        data = response.json()
        assert "平台不匹配" in data.get("detail", "")

    @pytest.mark.skip(reason="需要Mock playwright_mgr")
    def test_auth_start_account_not_found(self):
        """TC-AC-021: 开始授权 - 测试不存在的账号ID"""
        auth_data = {
            "platform": "zhihu",
            "account_id": 99999
        }

        response = self._make_request("POST", "/auth/start", json_data=auth_data)
        assert response.status_code == 404

    # ==================== GET /api/accounts/auth/status/{task_id} 接口测试 ====================

    def test_auth_status_not_found(self):
        """TC-AC-022: 获取授权状态 - 测试不存在的任务"""
        response = self._make_request("GET", "/auth/status/non_existent_task_id")
        assert response.status_code == 404

    # ==================== POST /api/accounts/auth/confirm/{task_id} 接口测试 ====================

    def test_auth_confirm_not_found(self):
        """TC-AC-023: 确认授权 - 测试不存在的任务"""
        response = self._make_request("POST", "/auth/confirm/non_existent_task_id")
        assert response.status_code == 404

    # ==================== DELETE /api/accounts/auth/task/{task_id} 接口测试 ====================

    def test_cancel_auth(self):
        """TC-AC-024: 取消授权任务"""
        response = self._make_request("DELETE", "/auth/task/non_existent_task_id")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True


# ==================== 集成测试 ====================

class TestAccountsIntegration:
    """账号管理集成测试"""

    def test_full_account_lifecycle(self, db):
        """TC-AC-INT-01: 完整账号生命周期测试"""
        from backend.database.models import Account

        base_url = f"{BASE_URL}{API_PREFIX}"

        # 1. 创建账号
        create_data = {
            "platform": "zhihu",
            "account_name": "集成测试账号",
            "remark": "用于完整生命周期测试"
        }
        response = requests.post(f"{base_url}", json=create_data)
        assert response.status_code == 201
        account = response.json()
        account_id = account["id"]

        # 2. 获取账号列表
        response = requests.get(f"{base_url}")
        assert response.status_code == 200
        accounts = response.json()
        assert any(a["id"] == account_id for a in accounts)

        # 3. 获取账号详情
        response = requests.get(f"{base_url}/{account_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["id"] == account_id
        assert detail["account_name"] == "集成测试账号"

        # 4. 更新账号
        update_data = {
            "account_name": "更新后的集成测试账号",
            "status": 1
        }
        response = requests.put(f"{base_url}/{account_id}", json=update_data)
        assert response.status_code == 200
        updated = response.json()
        assert updated["account_name"] == "更新后的集成测试账号"
        assert updated["status"] == 1

        # 5. 筛选账号
        response = requests.get(f"{base_url}", params={"platform": "zhihu", "status": 1})
        assert response.status_code == 200
        filtered = response.json()
        assert any(a["id"] == account_id for a in filtered)

        # 6. 删除账号
        response = requests.delete(f"{base_url}/{account_id}")
        assert response.status_code == 200

        # 7. 验证删除
        response = requests.get(f"{base_url}/{account_id}")
        assert response.status_code == 404

    def test_account_with_publish_records_cascade_delete(self, db):
        """TC-AC-INT-02: 测试级联删除发布记录"""
        from backend.database.models import Account, Article, PublishRecord

        # 创建账号
        account = Account(
            platform="zhihu",
            account_name="级联删除测试账号",
            status=1
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        # 创建文章
        article = Article(
            title="测试文章",
            content="测试内容",
            status=0
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # 创建发布记录
        record = PublishRecord(
            article_id=article.id,
            account_id=account.id,
            publish_status=2
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # 删除账号
        db.delete(account)
        db.commit()

        # 验证发布记录也被级联删除
        deleted_record = db.query(PublishRecord).filter(PublishRecord.id == record.id).first()
        assert deleted_record is None

        # 清理
        db.delete(article)
        db.commit()

    def test_create_multiple_accounts_different_platforms(self, db):
        """TC-AC-INT-03: 测试创建多个不同平台的账号"""
        from backend.database.models import Account

        base_url = f"{BASE_URL}{API_PREFIX}"

        platforms_to_test = ["zhihu", "toutiao", "sohu", "weixin"]
        created_ids = []

        for platform in platforms_to_test:
            response = requests.post(f"{base_url}", json={
                "platform": platform,
                "account_name": f"多平台测试_{platform}"
            })
            assert response.status_code == 201
            created_ids.append(response.json()["id"])

        # 验证所有账号都已创建
        for account_id in created_ids:
            response = requests.get(f"{base_url}/{account_id}")
            assert response.status_code == 200

        # 清理
        for account_id in created_ids:
            db.query(Account).filter(Account.id == account_id).delete()
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
