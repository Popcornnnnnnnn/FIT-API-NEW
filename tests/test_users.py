"""
用户相关接口测试
测试用户创建、获取、更新等基本功能
"""

import pytest
from fastapi import status


# 说明：
# 1. pytest_plugins = [...] 这种写法会让pytest自动加载 tests/conftest_mysql.py 里的所有fixture（包括 sample_user_data、client 等），
#    所以本文件虽然没有显式 import sample_user_data，但 pytest 会自动注入参数名同名的 fixture。
# 2. 你在测试代码里用到 sample_user_data 时，pytest 会自动调用 conftest_mysql.py 里的 sample_user_data fixture。
# 3. 如果你发现测试后数据库表里没有内容，是因为 conftest_mysql.py 里的 db_session fixture 每个测试用例会新建事务，测试结束后回滚（transaction.rollback()），
#    所以测试数据不会真正写入数据库（这是为了测试隔离，防止脏数据污染）。
# 4. 如果你想让测试数据真正写入数据库，可以临时注释掉 conftest_mysql.py 里 db_session fixture 的 transaction.rollback()，但一般不建议这样做。

# 说明：下面的测试类和方法是如何与 app/users.py 中的 API 接口关联的？
#
# 1. 测试用例通过 client（pytest fixture，见 conftest_mysql.py）模拟 HTTP 请求，直接调用 FastAPI 应用的接口。
# 2. 例如 client.post("/users/", ...) 实际上会触发 app/users.py 中 @router.post("/", ...) 的 create_user 视图函数。
# 3. client 是基于 TestClient(app)，而 app 是 FastAPI 实例，已经在 main.py 里 include_router(users.router)，所以 /users/ 路径会路由到 app/users.py 的相关接口。
# 4. 请求体 json=sample_user_data 会被 FastAPI 自动解析为 schemas.UserCreate，并传递给 create_user。
# 5. 响应内容和状态码由 app/users.py 的接口返回，测试用例断言这些内容是否符合预期。
#
# 总结：测试代码通过 TestClient 直接请求 FastAPI 路由，和 app/users.py 的 API 形成一一对应，属于集成测试（API 层）。

# ! 关于pytest_plugins = ["tests.conftest"] 这种方式指定conftest文件相关的问题

class TestUserCreation:
    """用户创建测试"""

    def test_create_user_success(self, client, sample_user_data):
        """
        这里的 client 参数是 pytest fixture 注入的测试客户端对象（TestClient 实例），
        它用于模拟 HTTP 请求，直接调用 FastAPI 应用的接口。

        具体来说，client 是在 tests/conftest_mysql.py 里定义的 fixture：
            @pytest.fixture
            def client(db_session):
                app.dependency_overrides[get_db] = lambda: db_session
                with TestClient(app) as test_client:
                    yield test_client
                app.dependency_overrides.clear()

        作用：
        - client 就是 fastapi.testclient.TestClient(app) 的实例。
        - 它可以像 requests 一样发起 get/post/put/delete 请求，直接请求你的 FastAPI 路由。
        - 这样你可以在测试里用 client.post(...)、client.get(...) 等方法，模拟前端/外部请求你的 API。
        - client 会自动使用测试数据库（通过依赖覆盖 get_db），保证测试隔离。

        总结：client 是一个“测试用的 HTTP 客户端”，让你在测试代码里像用 requests 一样请求自己的 FastAPI 应用，拿到响应结果做断言。
        """

        response = client.post("/users/", json=sample_user_data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == sample_user_data["name"]
        assert data["ftp"] == sample_user_data["ftp"]
        assert data["max_hr"] == sample_user_data["max_hr"]
        assert data["weight"] == sample_user_data["weight"]
        assert "id" in data

    def test_create_user_minimal_data(self, client):
        """测试使用最少数据创建用户（只有name）"""
        minimal_data = {"name": "最小用户"}
        # 这里同样会走 app/users.py 的 create_user 路由
        response = client.post("/users/", json=minimal_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == minimal_data["name"]
        assert data["ftp"] is None
        assert data["max_hr"] is None
        assert data["weight"] is None

    def test_create_user_missing_name(self, client):
        """测试缺少必填字段name"""
        invalid_data = {
            "ftp": 250.0,
            "max_hr": 185,
            "weight": 70.5
        }
        # 依然是请求 app/users.py 的 create_user 路由，但因为缺少 name 字段，FastAPI 会返回 422
        response = client.post("/users/", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

class TestUserRetrieval:
    """用户获取测试"""
    
    def test_get_user_success(self, client, sample_user_data):
        """测试成功获取用户"""
        # 先创建用户
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        # 获取用户
        response = client.get(f"/users/{user_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == user_id
        assert data["name"] == sample_user_data["name"]
        assert data["ftp"] == sample_user_data["ftp"]
        assert data["max_hr"] == sample_user_data["max_hr"]
        assert data["weight"] == sample_user_data["weight"]
    
    def test_get_user_not_found(self, client):
        """测试获取不存在的用户"""
        response = client.get("/users/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
    
    def test_get_users_list(self, client, sample_user_data):
        """测试获取用户列表"""
        # 创建多个用户
        for i in range(3):
            user_data = sample_user_data.copy()
            user_data["name"] = f"用户{i+1}"
            client.post("/users/", json=user_data)
        
        response = client.get("/users/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) >= 3
        assert all("id" in user for user in data)
        assert all("name" in user for user in data)

class TestUserUpdate:
    """用户信息更新测试"""
    
    def test_update_user_success(self, client, sample_user_data, sample_user_update_data):
        """测试成功更新用户信息"""
        # 先创建用户
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        # 更新用户信息
        response = client.put(f"/users/{user_id}", json=sample_user_update_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["id"] == user_id
        assert data["name"] == sample_user_data["name"]  # name应该保持不变
        assert data["ftp"] == sample_user_update_data["ftp"]
        assert data["max_hr"] == sample_user_update_data["max_hr"]
        assert data["weight"] == sample_user_update_data["weight"]
    
    def test_update_user_partial(self, client, sample_user_data):
        """测试部分更新用户信息"""
        # 先创建用户
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        # 只更新FTP
        partial_update = {"ftp": 300.0}
        response = client.put(f"/users/{user_id}", json=partial_update)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["ftp"] == 300.0
        assert data["max_hr"] == sample_user_data["max_hr"]  # 其他字段保持不变
        assert data["weight"] == sample_user_data["weight"]
    
    def test_update_user_not_found(self, client, sample_user_update_data):
        """测试更新不存在的用户"""
        response = client.put("/users/99999", json=sample_user_update_data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"

class TestUserMetrics:
    """用户指标测试"""
    
    def test_add_user_metric_success(self, client, sample_user_data):
        """测试成功添加用户指标"""
        # 先创建用户
        create_response = client.post("/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        # 添加指标
        metric_data = {
            "metric_name": "测试指标",
            "metric_value": 100.5
        }
        response = client.post(f"/users/{user_id}/metrics", json=metric_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["user_id"] == user_id
        assert data["metric_name"] == metric_data["metric_name"]
        assert data["metric_value"] == metric_data["metric_value"]
        assert "id" in data
        assert "updated_at" in data

class TestDataValidation:
    """数据验证测试"""
    
    def test_invalid_ftp_type(self, client):
        """测试FTP类型错误"""
        invalid_data = {
            "name": "测试用户",
            "ftp": "不是数字",
            "max_hr": 185,
            "weight": 70.5
        }
        response = client.post("/users/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_max_hr_type(self, client):
        """测试最大心率类型错误"""
        invalid_data = {
            "name": "测试用户",
            "ftp": 250.0,
            "max_hr": "不是数字",
            "weight": 70.5
        }
        response = client.post("/users/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_weight_type(self, client):
        """测试体重类型错误"""
        invalid_data = {
            "name": "测试用户",
            "ftp": 250.0,
            "max_hr": 185,
            "weight": "不是数字"
        }
        response = client.post("/users/", json=invalid_data)
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY 