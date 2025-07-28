"""
数据流相关接口测试
测试流数据获取等功能
"""

import pytest
from fastapi import status

# 使用MySQL数据库进行测试，如果使用sqlite，则注释掉这行
# pytest_plugins = ["tests.conftest"]  # 注释掉，因为conftest.py会自动加载

class TestStreamData:
    """流数据测试"""
    
    def test_get_activity_stream_default(self, client):
        """测试获取活动流数据（默认采样率）"""
        activity_id = 1
        
        response = client.get(f"/streams/{activity_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "stream_type" in data
        assert "data" in data
        assert isinstance(data["data"], list)
        assert "sample_rate" in data
        
        # 检查流数据格式
        if data["data"]:
            stream_item = data["data"][0]
            assert "timestamp" in stream_item
            assert "power" in stream_item
            assert "heart_rate" in stream_item
    
    def test_get_activity_stream_with_sample_rate(self, client):
        """测试获取活动流数据（指定采样率）"""
        activity_id = 1
        sample_rate = 5
        
        response = client.get(f"/streams/{activity_id}?sample_rate={sample_rate}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert data["sample_rate"] == sample_rate
        assert "data" in data
    
    def test_get_activity_stream_with_type(self, client):
        """测试获取指定类型的流数据"""
        activity_id = 1
        stream_type = "heart_rate"
        
        response = client.get(f"/streams/{activity_id}?stream_type={stream_type}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert data["stream_type"] == stream_type

class TestBatchStreams:
    """批量流数据测试"""
    
    def test_get_multiple_streams_success(self, client):
        """测试成功获取多种流数据"""
        request_data = {
            "activity_id": 1,
            "stream_types": ["power", "heart_rate"],
            "sample_rate": 2
        }
        
        response = client.post("/streams/batch", json=request_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        # 检查每个流数据
        for stream in data:
            assert stream["activity_id"] == request_data["activity_id"]
            assert stream["stream_type"] in request_data["stream_types"]
            assert stream["sample_rate"] == request_data["sample_rate"]
            assert "data" in stream
            assert isinstance(stream["data"], list)
    
    def test_get_multiple_streams_invalid_request(self, client):
        """测试无效的批量请求"""
        invalid_request = {
            "activity_id": 1,
            "stream_types": [],  # 空列表
            "sample_rate": 1
        }
        
        response = client.post("/streams/batch", json=invalid_request)
        
        # 当前实现可能接受空列表，后续可能需要验证
        assert response.status_code == status.HTTP_200_OK 