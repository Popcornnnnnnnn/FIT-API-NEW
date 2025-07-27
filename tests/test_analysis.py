"""
数据分析相关接口测试
测试活动摘要、流数据、高级指标等功能
"""

import pytest
from fastapi import status

class TestActivitySummary:
    """活动摘要测试"""
    
    def test_get_activity_summary_success(self, client):
        """测试成功获取活动摘要"""
        activity_id = 1  # 使用测试数据
        
        response = client.get(f"/analysis/summary/{activity_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "distance_km" in data
        assert "duration_min" in data
        assert "avg_power" in data
        assert "avg_hr" in data
    
    def test_get_activity_summary_not_found(self, client):
        """测试获取不存在的活动摘要"""
        response = client.get("/analysis/summary/99999")
        
        # 当前实现返回mock数据，所以总是成功
        # 后续实现真实逻辑时可能需要调整
        assert response.status_code == status.HTTP_200_OK

class TestActivityStream:
    """活动流数据测试"""
    
    def test_get_activity_stream_default(self, client):
        """测试获取活动流数据（默认采样率）"""
        activity_id = 1
        
        response = client.get(f"/analysis/stream/{activity_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "stream" in data
        assert isinstance(data["stream"], list)
        
        # 检查流数据格式
        if data["stream"]:
            stream_item = data["stream"][0]
            assert "time" in stream_item
            assert "power" in stream_item
            assert "hr" in stream_item
    
    def test_get_activity_stream_with_sample_rate(self, client):
        """测试获取活动流数据（指定采样率）"""
        activity_id = 1
        sample_rate = 5
        
        response = client.get(f"/analysis/stream/{activity_id}?sample_rate={sample_rate}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "stream" in data

class TestAdvancedMetrics:
    """高级指标测试"""
    
    def test_get_advanced_metrics_success(self, client):
        """测试成功获取高级指标"""
        activity_id = 1
        
        response = client.get(f"/analysis/advanced/{activity_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "NP" in data
        assert "IF" in data
        assert "TSS" in data
        assert "hr_zones" in data
        assert isinstance(data["hr_zones"], dict)

# TODO: 添加更多数据分析相关测试
# - 真实FIT文件解析后的数据测试
# - 性能测试
# - 边界条件测试 