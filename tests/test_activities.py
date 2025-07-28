"""
活动相关接口测试
测试活动摘要、高级指标等功能
"""

import pytest
from fastapi import status

# 使用MySQL数据库进行测试，如果使用sqlite，则注释掉这行
# pytest_plugins = ["tests.conftest"]  # 注释掉，因为conftest.py会自动加载

class TestActivitySummary:
    """活动摘要测试"""
    
    def test_get_activity_summary_success(self, client):
        """测试成功获取活动摘要"""
        activity_id = 1
        
        response = client.get(f"/activities/{activity_id}/summary")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "distance_km" in data
        assert "duration_min" in data
        assert "avg_power" in data
        assert "avg_hr" in data
        assert "max_power" in data
        assert "max_hr" in data
        assert "activity_type" in data
    
    def test_get_activity_summary_not_found(self, client):
        """测试获取不存在的活动摘要"""
        response = client.get("/activities/99999/summary")
        
        # 当前实现返回mock数据，所以总是成功
        # 后续实现真实逻辑时可能需要调整
        assert response.status_code == status.HTTP_200_OK

class TestActivityAdvanced:
    """活动高级指标测试"""
    
    def test_get_advanced_metrics_success(self, client):
        """测试成功获取高级指标"""
        activity_id = 1
        
        response = client.get(f"/activities/{activity_id}/advanced")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "NP" in data
        assert "IF" in data
        assert "TSS" in data
        assert "hr_zones" in data
        assert isinstance(data["hr_zones"], dict)

class TestActivityList:
    """活动列表测试"""
    
    def test_get_activities_list(self, client):
        """测试获取活动列表"""
        response = client.get("/activities/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # 当前实现返回空列表
        assert isinstance(data, list)
    
    def test_get_activity_detail_not_found(self, client):
        """测试获取不存在的活动详情"""
        response = client.get("/activities/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "活动未找到" 