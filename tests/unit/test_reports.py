# -*- coding: utf-8 -*-
"""
数据报表功能测试
测试所有数据报表API接口

测试范围：
- GET /api/reports/projects - 项目统计
- GET /api/reports/platforms - 平台统计
- GET /api/reports/trends - 趋势数据
- GET /api/reports/stats - 数据总览
- GET /api/reports/platform-comparison - 平台对比
- GET /api/reports/project-leaderboard - 项目排行
- GET /api/reports/overview - 数据总览
- POST /api/reports/run-check - 执行检测
"""

import pytest
import requests
from datetime import datetime, timedelta

BASE_URL = "http://127.0.0.1:8001"
API_PREFIX = "/api/reports"


class TestReportsAPI:
    """数据报表API测试类"""

    @pytest.fixture(scope="class")
    def base_url(self):
        """基础URL"""
        return f"{BASE_URL}{API_PREFIX}"

    def _make_request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None):
        """发送HTTP请求"""
        url = f"{BASE_URL}{API_PREFIX}{endpoint}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, json=json_data, timeout=30)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            return response
        except requests.exceptions.Timeout:
            pytest.fail(f"请求超时: {url}")
        except requests.exceptions.ConnectionError:
            pytest.fail(f"连接失败，请确认后端服务已启动: {url}")

    # ==================== /projects 接口测试 ====================

    def test_get_projects_success(self, base_url):
        """TC-RP-001: 获取项目统计 - 验证正常返回"""
        response = self._make_request("GET", "/projects")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 如果有数据，验证结构
        if len(data) > 0:
            item = data[0]
            required_fields = [
                "project_id", "project_name", "company_name",
                "total_keywords", "active_keywords", "total_questions",
                "total_checks", "keyword_hit_rate", "company_hit_rate"
            ]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

            # 验证数据类型
            assert isinstance(item["project_id"], int)
            assert isinstance(item["total_keywords"], int)
            assert isinstance(item["keyword_hit_rate"], (int, float))
            assert 0 <= item["keyword_hit_rate"] <= 100

    def test_get_projects_empty(self, base_url):
        """TC-RP-002: 获取项目统计 - 验证空数据返回"""
        response = self._make_request("GET", "/projects")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    # ==================== /platforms 接口测试 ====================

    def test_get_platforms_success(self, base_url):
        """TC-RP-003: 获取平台统计 - 验证正常返回"""
        response = self._make_request("GET", "/platforms")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 应该包含三个平台
        platform_names = [p["platform"] for p in data]
        assert "豆包" in platform_names
        assert "通义千问" in platform_names
        assert "DeepSeek" in platform_names

        # 验证数据结构
        for item in data:
            required_fields = ["platform", "total_checks", "keyword_found", "company_found", "keyword_hit_rate", "company_hit_rate"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

            assert isinstance(item["total_checks"], int)
            assert isinstance(item["keyword_hit_rate"], (int, float))
            assert 0 <= item["keyword_hit_rate"] <= 100

    # ==================== /trends 接口测试 ====================

    def test_get_trends_success(self, base_url):
        """TC-RP-004: 获取趋势数据 - 验证正常返回"""
        response = self._make_request("GET", "/trends", {"days": 7})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 验证数据结构
        for item in data:
            required_fields = ["date", "keyword_found_count", "company_found_count", "total_checks"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

            assert isinstance(item["date"], str)
            assert isinstance(item["total_checks"], int)

    def test_get_trends_with_days_filter(self, base_url):
        """TC-RP-005: 趋势数据 - 测试days参数"""
        # 测试7天
        response_7 = self._make_request("GET", "/trends", {"days": 7})
        assert response_7.status_code == 200
        data_7 = response_7.json()

        # 测试30天
        response_30 = self._make_request("GET", "/trends", {"days": 30})
        assert response_30.status_code == 200
        data_30 = response_30.json()

        assert isinstance(data_7, list)
        assert isinstance(data_30, list)

    def test_get_trends_with_platform_filter(self, base_url):
        """TC-RP-006: 趋势数据 - 测试platform参数"""
        response = self._make_request("GET", "/trends", {"days": 7, "platform": "doubao"})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_get_trends_invalid_days(self, base_url):
        """TC-RP-007: 趋势数据 - 测试无效days参数"""
        # days 应该在 1-90 之间
        response = self._make_request("GET", "/trends", {"days": 100})
        # 应该返回 422 错误
        assert response.status_code == 422

    # ==================== /stats 接口测试 ====================

    def test_get_stats_success(self, base_url):
        """TC-RP-008: 获取数据总览 - 验证正常返回"""
        response = self._make_request("GET", "/stats")
        assert response.status_code == 200

        data = response.json()
        required_fields = [
            "total_articles", "common_articles", "geo_articles",
            "publish_success_rate", "publish_success_count", "publish_total_count",
            "keyword_hit_rate", "keyword_hit_count", "keyword_check_count",
            "company_hit_rate", "company_hit_count", "company_check_count"
        ]

        for field in required_fields:
            assert field in data, f"响应缺少必需字段: {field}"

        # 验证数据类型
        assert isinstance(data["total_articles"], int)
        assert isinstance(data["publish_success_rate"], (int, float))
        assert 0 <= data["publish_success_rate"] <= 100
        assert isinstance(data["keyword_hit_rate"], (int, float))
        assert 0 <= data["keyword_hit_rate"] <= 100

    def test_get_stats_with_project_filter(self, base_url):
        """TC-RP-009: 数据总览 - 测试project_id参数"""
        response = self._make_request("GET", "/stats", {"project_id": 1, "days": 7})
        assert response.status_code == 200

        data = response.json()
        assert "total_articles" in data
        assert isinstance(data["total_articles"], int)

    def test_get_stats_with_days_filter(self, base_url):
        """TC-RP-010: 数据总览 - 测试days参数"""
        response_7 = self._make_request("GET", "/stats", {"days": 7})
        response_30 = self._make_request("GET", "/stats", {"days": 30})

        assert response_7.status_code == 200
        assert response_30.status_code == 200

        data_7 = response_7.json()
        data_30 = response_30.json()

        # 30天数据应该 >= 7天数据
        assert data_30["total_articles"] >= data_7["total_articles"]

    # ==================== /platform-comparison 接口测试 ====================

    def test_get_platform_comparison_success(self, base_url):
        """TC-RP-011: 平台对比分析 - 验证正常返回"""
        response = self._make_request("GET", "/platform-comparison")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 验证数据结构
        for item in data:
            required_fields = ["platform", "total_count", "hit_count", "hit_rate"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

            assert isinstance(item["platform"], str)
            assert isinstance(item["total_count"], int)
            assert isinstance(item["hit_rate"], (int, float))

    def test_get_platform_comparison_with_filters(self, base_url):
        """TC-RP-012: 平台对比 - 测试筛选参数"""
        response = self._make_request("GET", "/platform-comparison", {
            "project_id": 1,
            "days": 7,
            "platform": "doubao"
        })
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    # ==================== /project-leaderboard 接口测试 ====================

    def test_get_project_leaderboard_success(self, base_url):
        """TC-RP-013: 项目影响力排行榜 - 验证正常返回"""
        response = self._make_request("GET", "/project-leaderboard")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        # 验证数据结构
        for item in data:
            required_fields = [
                "rank", "project_name", "company_name",
                "content_volume", "ai_mention_rate", "brand_relevance"
            ]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"

            assert isinstance(item["rank"], int)
            assert isinstance(item["content_volume"], int)
            assert isinstance(item["ai_mention_rate"], (int, float))
            assert 0 <= item["ai_mention_rate"] <= 100

    def test_get_project_leaderboard_with_days_filter(self, base_url):
        """TC-RP-014: 项目排行榜 - 测试days参数"""
        response = self._make_request("GET", "/project-leaderboard", {"days": 7})
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

    def test_get_project_leaderboard_ranking(self, base_url):
        """TC-RP-015: 项目排行榜 - 验证排序正确"""
        response = self._make_request("GET", "/project-leaderboard", {"days": 7})
        assert response.status_code == 200

        data = response.json()

        # 验证排名是按 ai_mention_rate 降序排列的
        if len(data) > 1:
            for i in range(len(data) - 1):
                assert data[i]["ai_mention_rate"] >= data[i + 1]["ai_mention_rate"]
                assert data[i]["rank"] < data[i + 1]["rank"]

    # ==================== /overview 接口测试 ====================

    def test_get_overview_success(self, base_url):
        """TC-RP-016: 获取数据总览 - 验证正常返回"""
        response = self._make_request("GET", "/overview")
        assert response.status_code == 200

        data = response.json()
        required_fields = ["total_keywords", "keyword_found", "company_found", "overall_hit_rate"]

        for field in required_fields:
            assert field in data, f"响应缺少必需字段: {field}"

        # 验证数据类型
        assert isinstance(data["total_keywords"], int)
        assert isinstance(data["keyword_found"], int)
        assert isinstance(data["company_found"], int)
        assert isinstance(data["overall_hit_rate"], (int, float))
        assert 0 <= data["overall_hit_rate"] <= 100

    # ==================== /run-check 接口测试 ====================

    def test_run_check_invalid_project(self, base_url):
        """TC-RP-017: 执行收录检测 - 测试不存在的项目"""
        response = self._make_request("POST", "/run-check", json_data={
            "project_id": 99999,
            "platforms": ["doubao"]
        })
        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert "message" in data
        # 不存在的项目应该返回失败
        assert data["success"] is False

    def test_run_check_valid_project(self, base_url, db, test_project):
        """TC-RP-018: 执行收录检测 - 测试有效项目"""
        response = self._make_request("POST", "/run-check", json_data={
            "project_id": test_project.id,
            "platforms": ["doubao"]
        })
        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert "message" in data


# ==================== 集成测试 ====================

class TestReportsIntegration:
    """数据报表集成测试"""

    def test_full_reports_flow(self, db):
        """TC-RP-INT-01: 完整报表数据流程测试"""
        from backend.database.models import Project, Keyword, IndexCheckRecord, GeoArticle
        from datetime import datetime, timedelta

        # 创建测试项目
        project = Project(
            name="测试报表项目",
            company_name="测试公司",
            status=1
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # 创建测试关键词
        keyword = Keyword(
            project_id=project.id,
            keyword="测试关键词",
            status="active"
        )
        db.add(keyword)
        db.commit()
        db.refresh(keyword)

        # 创建检测记录
        now = datetime.now()
        record = IndexCheckRecord(
            keyword_id=keyword.id,
            platform="doubao",
            question="测试问题",
            answer="测试回答",
            keyword_found=True,
            company_found=True,
            check_time=now
        )
        db.add(record)

        # 创建GEO文章
        geo_article = GeoArticle(
            keyword_id=keyword.id,
            title="测试文章",
            content="测试内容",
            publish_status="published",
            created_at=now
        )
        db.add(geo_article)

        db.commit()

        # 测试各个API接口
        base_url = f"{BASE_URL}{API_PREFIX}"

        # 测试项目统计
        response = requests.get(f"{base_url}/projects")
        assert response.status_code == 200
        projects = response.json()
        assert any(p["project_id"] == project.id for p in projects)

        # 测试数据总览
        response = requests.get(f"{base_url}/stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_articles"] > 0

        # 测试平台统计
        response = requests.get(f"{base_url}/platforms")
        assert response.status_code == 200
        platforms = response.json()

        # 测试趋势数据
        response = requests.get(f"{base_url}/trends", params={"days": 7})
        assert response.status_code == 200
        trends = response.json()
        assert isinstance(trends, list)

        # 清理测试数据
        db.delete(geo_article)
        db.delete(record)
        db.delete(keyword)
        db.delete(project)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
