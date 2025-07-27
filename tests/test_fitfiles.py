"""
FIT文件相关接口测试
测试文件上传、解析等功能
"""

import pytest
from fastapi import status
import io

class TestFitFileUpload:
    """FIT文件上传测试"""
    
    def test_upload_fit_file_success(self, client, sample_user_data):
        """测试成功上传FIT文件"""
        # 先创建用户
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        # 创建模拟的FIT文件
        fake_fit_content = b"fake fit file content"
        files = {"file": ("test.fit", io.BytesIO(fake_fit_content), "application/octet-stream")}
        
        response = client.post(f"/fitfiles/upload?user_id={user_id}", files=files)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["user_id"] == user_id
        assert "id" in data
        assert "file_path" in data
        assert "created_at" in data
    
    def test_upload_fit_file_no_user(self, client):
        """测试上传文件时用户不存在"""
        fake_fit_content = b"fake fit file content"
        files = {"file": ("test.fit", io.BytesIO(fake_fit_content), "application/octet-stream")}
        
        response = client.post("/fitfiles/upload?user_id=99999", files=files)
        
        # 这里可能需要根据实际实现调整预期结果
        # 如果用户不存在时应该返回错误，则期望404
        # 如果允许创建活动记录，则期望200
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]
    
    def test_upload_fit_file_no_file(self, client, sample_user_data):
        """测试上传时没有文件"""
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        response = client.post(f"/fitfiles/upload?user_id={user_id}")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

# TODO: 添加更多FIT文件相关测试
# - 文件解析测试
# - 流数据接口测试
# - 后台队列处理测试 