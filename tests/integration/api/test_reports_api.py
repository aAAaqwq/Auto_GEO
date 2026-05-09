# -*- coding: utf-8 -*-
"""
数据报表功能 - 后端API自动化测试
使用 pytest + requests 进行接口测试

测试范围：
- /api/reports/stats
- /api/reports/platform-comparison
- /api/reports/project-leaderboard
- /api/reports/content-analysis

运行方式：
    cd backend
    pip install pytest requests
    pytest tests/test_reports_api.py -v

作者：测试工程师
日期：2026-02-03
"""

import pytest
import requests
from typing import Dict, Any
from datetime import datetime

# 配置
BASE_URL = "http://127.0.0.1:8001"
API_PREFIX = "/api/reports"


class TestReportsAPI:
    """数据报表API测试类"""
    
    @pytest.fixture(scope="class")
    def base_url(self):
        """基础URL"""
        return f"{BASE_URL}{API_PREFIX}"
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """发送HTTP请求并返回JSON响应"""
        url = f"{BASE_URL}{API_PREFIX}{endpoint}"
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=10)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            pytest.fail(f"请求超时: {url}")
        except requests.exceptions.ConnectionError:
            pytest.fail(f"连接失败，请确认后端服务已启动: {url}")
        except requests.exceptions.HTTPError as e:
            pytest.fail(f"HTTP错误 {response.status_code}: {response.text}")
    
    # ==================== TC-001: /stats 接口测试 ====================
    
    def test_get_stats_success(self, base_url):
        """TC-001: 正常请求 - 验证 /stats 接口返回正确数据结构"""
        response = self._make_request("GET", "/stats")
        
        # 验证响应包含所有必需字段
        required_fields = [
            "total_articles", "common_articles", "geo_articles",
            "publish_success_rate", "publish_success_count", "publish_total_count",
            "keyword_hit_rate", "keyword_hit_count", "keyword_check_count",
            "company_hit_rate", "company_hit_count", "company_check_count"
        ]
        
        for field in required_fields:
            assert field in response, f"响应缺少必需字段: {field}"
        
        # 验证数据类型
        assert isinstance(response["total_articles"], int)
        assert isinstance(response["publish_success_rate"], float)
        assert response["publish_success_rate"] >= 0 and response["publish_success_rate"] <= 100
    
    def test_get_stats_with_project_filter(self, base_url):
        """TC-002: 按项目筛选 - 验证 project_id 参数正常工作"""
        # 测试不存在的项目ID
        response = self._make_request("GET", "/stats", {"project_id": 99999, "days": 7})
        assert "total_articles" in response
        # 不存在的项目应该返回0数据
        assert response["total_articles"] == 0
    
    def test_get_stats_with_days_filter(self, base_url):
        """TC-003: 时间范围筛选 - 验证 days 参数正常工作"""
        # 测试7天
        response_7 = self._make_request("GET", "/stats", {"days": 7})
        # 测试30天
        response_30 = self._make_request("GET", "/stats", {"days": 30})
        
        # 30天的数据量应该 >= 7天的数据量
        assert response_30["total_articles"] >= response_7["total_articles"]
    
    def test_get_stats_empty_data(self, base_url):
        """TC-004: 空数据情况 - 验证无数据时返回正确"""
        # 查询一个不存在的项目，应该返回空数据而不是错误
        response = self._make_request("GET", "/stats", {"project_id": 0})
        
        assert response["total_articles"] == 0
        assert response["publish_success_rate"] == 0.0
        assert response["keyword_hit_rate"] == 0.0
        assert response["company_hit_rate"] == 0.0
    
    # ==================== TC-005: 平台对比接口测试 ====================
    
    def test_get_platform_comparison_success(self, base_url):
        """TC-005: 平台对比分析 - 验证正常返回数据结构"""
        response = self._make_request("GET", "/platform-comparison")
        
        # 返回应该是数组
        assert isinstance(response, list)
        
        # 如果数据库有数据，验证每个元素的结构
        if len(response) > 0:
            item = response[0]
            required_fields = ["platform", "hit_count", "total_count", "hit_rate"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"
            
            # 验证数据类型
            assert isinstance(item["platform"], str)
            assert isinstance(item["hit_count"], int)
            assert isinstance(item["total_count"], int)
            assert isinstance(item["hit_rate"], (int, float))
    
    def test_get_platform_comparison_with_filters(self, base_url):
        """验证平台对比接口支持筛选参数"""
        # 测试带参数的请求
        response = self._make_request("GET", "/platform-comparison", {
            "project_id": 1,
            "days": 7
        })
        
        # 应该返回数组（可能是空的，取决于数据）
        assert isinstance(response, list)
    
    # ==================== TC-006: 项目排行接口测试 ====================
    
    def test_get_project_leaderboard_success(self, base_url):
        """TC-006: 项目影响力排行榜 - 验证正常返回"""
        response = self._make_request("GET", "/project-leaderboard")
        
        # 返回应该是数组
        assert isinstance(response, list)
        
        # 验证每个元素的结构（如果有数据）
        if len(response) > 0:
            item = response[0]
            required_fields = [
                "rank", "project_name", "company_name",
                "content_volume", "ai_mention_rate", "brand_relevance"
            ]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"
            
            # 验证 rank 是递增的
            assert item["rank"] == 1
    
    def test_get_project_leaderboard_with_days_filter(self, base_url):
        """验证排行榜支持 days 参数"""
        response = self._make_request("GET", "/project-leaderboard", {"days": 7})
        assert isinstance(response, list)
    
    # ==================== TC-007: 内容分析接口测试 ====================
    
    def test_get_content_analysis_success(self, base_url):
        """TC-007: 高贡献内容分析 - 验证正常返回"""
        response = self._make_request("GET", "/content-analysis")
        
        # 返回应该是数组
        assert isinstance(response, list)
        
        # 验证每个元素的结构（如果有数据）
        if len(response) > 0:
            item = response[0]
            required_fields = ["rank", "title", "platform", "ai_contribution", "publish_time"]
            for field in required_fields:
                assert field in item, f"响应项缺少字段: {field}"
    
    def test_get_content_analysis_with_filters(self, base_url):
        """验证内容分析支持筛选参数"""
        response = self._make_request("GET", "/content-analysis", {
            "project_id": 1,
            "days": 7
        })
        assert isinstance(response, list)


# 如果直接运行此文件
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
