"""
运动员相关接口测试
测试运动员创建、获取、更新等基本功能
"""

import pytest
from fastapi import status

# 使用MySQL数据库进行测试，如果使用sqlite，则注释掉这行
# pytest_plugins = ["tests.conftest"]  # 注释掉，因为conftest.py会自动加载

class TestAthleteCreation:
    """运动员创建测试"""
    
    def test_create_athlete_success(self, client, sample_user_data):
        """测试成功创建运动员"""
        response = client.post("/athletes/", json=sample_user_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == sample_user_data["name"]
        assert data["ftp"] == sample_user_data["ftp"]
        assert data["max_hr"] == sample_user_data["max_hr"]
        assert data["weight"] == sample_user_data["weight"]
        assert "id" in data
    
    def test_create_athlete_minimal_data(self, client):
        """测试使用最少数据创建运动员（只有name）"""
        minimal_data = {"name": "最小运动员"}
        response = client.post("/athletes/", json=minimal_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["name"] == minimal_data["name"]
        assert data["ftp"] is None
        assert data["max_hr"] is None
        assert data["weight"] is None
    
    def test_create_athlete_missing_name(self, client):
        """测试缺少必填字段name"""
        invalid_data = {
            "ftp": 250.0,
            "max_hr": 185,
            "weight": 70.5
        }
        response = client.post("/athletes/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestAthleteRetrieval:
    """运动员获取测试"""
    
    def test_get_athlete_success(self, client, sample_user_data):
        """测试成功获取运动员"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 获取运动员
        response = client.get(f"/athletes/{athlete_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == athlete_id
        assert data["name"] == sample_user_data["name"]
        assert data["ftp"] == sample_user_data["ftp"]
        assert data["max_hr"] == sample_user_data["max_hr"]
        assert data["weight"] == sample_user_data["weight"]
    
    def test_get_athlete_not_found(self, client):
        """测试获取不存在的运动员"""
        response = client.get("/athletes/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "运动员未找到"
    
    def test_get_athletes_list(self, client, sample_user_data):
        """测试获取运动员列表"""
        # 创建多个运动员
        for i in range(3):
            athlete_data = sample_user_data.copy()
            athlete_data["name"] = f"运动员{i+1}"
            client.post("/athletes/", json=athlete_data)
        
        response = client.get("/athletes/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 3
        assert all("id" in athlete for athlete in data)
        assert all("name" in athlete for athlete in data)

class TestAthleteUpdate:
    """运动员信息更新测试"""
    
    def test_update_athlete_success(self, client, sample_user_data, sample_user_update_data):
        """测试成功更新运动员信息"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 更新运动员信息
        response = client.put(f"/athletes/{athlete_id}", json=sample_user_update_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == athlete_id
        assert data["name"] == sample_user_data["name"]  # name应该保持不变
        assert data["ftp"] == sample_user_update_data["ftp"]
        assert data["max_hr"] == sample_user_update_data["max_hr"]
        assert data["weight"] == sample_user_update_data["weight"]
    
    def test_update_athlete_partial(self, client, sample_user_data):
        """测试部分更新运动员信息"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 只更新FTP
        partial_update = {"ftp": 300.0}
        response = client.put(f"/athletes/{athlete_id}", json=partial_update)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["ftp"] == 300.0
        assert data["max_hr"] == sample_user_data["max_hr"]  # 其他字段保持不变
        assert data["weight"] == sample_user_data["weight"]
    
    def test_update_athlete_not_found(self, client, sample_user_update_data):
        """测试更新不存在的运动员"""
        response = client.put("/athletes/99999", json=sample_user_update_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "运动员未找到"

class TestAthleteMetrics:
    """运动员指标测试"""
    
    def test_add_athlete_metric_success(self, client, sample_user_data):
        """测试成功添加运动员指标"""
        # 先创建运动员
        create_response = client.post("/athletes/", json=sample_user_data)
        athlete_id = create_response.json()["id"]
        
        # 添加指标
        metric_data = {
            "metric_name": "测试指标",
            "metric_value": 100.5
        }
        response = client.post(f"/athletes/{athlete_id}/metrics", json=metric_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["athlete_id"] == athlete_id
        assert data["metric_name"] == metric_data["metric_name"]
        assert data["metric_value"] == metric_data["metric_value"]
        assert "id" in data
        assert "updated_at" in data 