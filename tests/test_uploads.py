"""
文件上传相关接口测试
测试FIT文件上传等功能
"""

import pytest
from fastapi import status
import io

# 使用MySQL数据库进行测试，如果使用sqlite，则注释掉这行
# pytest_plugins = ["tests.conftest"]  # 注释掉，因为conftest.py会自动加载

class TestFitFileUpload:
    """FIT文件上传测试"""
    
    def test_upload_fit_file_success(self, client, sample_user_data):
        """测试成功上传FIT文件"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的FIT文件
        fake_fit_content = b"fake fit file content"
        files = {"file": ("test.fit", io.BytesIO(fake_fit_content), "application/octet-stream")}
        
        response = client.post(f"/uploads/fit?athlete_id={athlete_id}", files=files)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == 1  # TODO: 返回真实的活动ID
        assert "file_path" in data
        assert data["status"] == "pending"
        assert "message" in data
        assert "created_at" in data
    
    def test_upload_fit_file_invalid_type(self, client, sample_user_data):
        """测试上传非FIT文件"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 创建模拟的非FIT文件
        fake_content = b"fake content"
        files = {"file": ("test.txt", io.BytesIO(fake_content), "text/plain")}
        
        response = client.post(f"/uploads/fit?athlete_id={athlete_id}", files=files)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "只允许上传.fit文件"
    
    def test_upload_fit_file_no_file(self, client, sample_user_data):
        """测试上传时没有文件"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        response = client.post(f"/uploads/fit?athlete_id={athlete_id}")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestUploadStatus:
    """上传状态测试"""
    
    def test_get_upload_status_success(self, client):
        """测试成功获取上传状态"""
        activity_id = 1
        
        response = client.get(f"/uploads/{activity_id}/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["activity_id"] == activity_id
        assert "status" in data
        assert "progress" in data
        assert "message" in data
        
        # 检查状态值是否有效
        assert data["status"] in ["pending", "processing", "completed", "failed"]
        assert 0 <= data["progress"] <= 100 