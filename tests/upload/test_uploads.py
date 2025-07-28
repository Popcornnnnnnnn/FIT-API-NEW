"""
文件上传相关接口测试
测试文件上传、状态查询等功能
"""

import pytest
from fastapi import status
import io

class TestFitFileUpload:
    """FIT文件上传测试（旧接口）"""
    
    def test_upload_fit_file_success(self, client, sample_user_data):
        """测试成功上传FIT文件"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的FIT文件
        fit_file = io.BytesIO(b"mock fit file content")
        
        response = client.post(
            f"/uploads/fit?athlete_id={athlete_id}",
            files={"file": ("test.fit", fit_file, "application/octet-stream")}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activity_id" in data
        assert "file_path" in data
        assert data["status"] == "pending"
    
    def test_upload_fit_file_invalid_type(self, client, sample_user_data):
        """测试上传非FIT文件"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的文本文件
        text_file = io.BytesIO(b"this is not a fit file")
        
        response = client.post(
            f"/uploads/fit?athlete_id={athlete_id}",
            files={"file": ("test.txt", text_file, "text/plain")}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "只允许上传.fit文件"
    
    def test_upload_fit_file_no_file(self, client, sample_user_data):
        """测试没有文件的上传请求"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        response = client.post(f"/uploads/fit?athlete_id={athlete_id}")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestNewFileUpload:
    """新文件上传接口测试"""
    
    def test_upload_file_success(self, client, sample_user_data):
        """测试成功上传文件（新接口）"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的FIT文件
        fit_file = io.BytesIO(b"mock fit file content")
        
        response = client.post(
            "/uploads/",
            files={"file": ("test.fit", fit_file, "application/octet-stream")},
            data={
                "athlete_id": athlete_id,
                "name": "测试活动",
                "description": "这是一个测试活动",
                "trainer": "false",
                "commute": "false",
                "data_type": "fit"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activity_id" in data
        assert "id_str" in data
        assert "external_id" in data
        assert data["status"] == "pending"
        assert data["error"] is None
    
    def test_upload_file_with_all_optional_params(self, client, sample_user_data):
        """测试上传文件时提供所有可选参数"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的FIT文件
        fit_file = io.BytesIO(b"mock fit file content")
        
        response = client.post(
            "/uploads/",
            files={"file": ("test.fit", fit_file, "application/octet-stream")},
            data={
                "athlete_id": athlete_id,
                "name": "完整测试活动",
                "description": "包含所有可选参数的活动",
                "trainer": "true",
                "commute": "true",
                "data_type": "fit",
                "external_id": "test_external_123"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["activity_id"] > 0
        assert data["external_id"] == "test_external_123"
        assert data["status"] == "pending"
    
    def test_upload_file_invalid_data_type(self, client, sample_user_data):
        """测试不支持的文件格式"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟文件
        test_file = io.BytesIO(b"test file content")
        
        response = client.post(
            "/uploads/",
            files={"file": ("test.xyz", test_file, "application/octet-stream")},
            data={
                "athlete_id": athlete_id,
                "data_type": "xyz"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "不支持的文件格式" in response.json()["detail"]
    
    def test_upload_file_missing_athlete_id(self, client):
        """测试缺少运动员ID"""
        # 创建模拟的FIT文件
        fit_file = io.BytesIO(b"mock fit file content")
        
        response = client.post(
            "/uploads/",
            files={"file": ("test.fit", fit_file, "application/octet-stream")},
            data={
                "data_type": "fit"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestUploadStatus:
    """上传状态查询测试"""
    
    def test_get_upload_status_success(self, client):
        """测试成功获取上传状态"""
        response = client.get("/uploads/1/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activity_id" in data
        assert "status" in data
        assert "progress" in data
        assert "message" in data 