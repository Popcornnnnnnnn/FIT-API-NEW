"""
pytest配置文件，定义测试环境和共享的测试夹具（fixtures）。

主要功能：
1. 配置测试数据库连接
2. 提供数据库会话管理
3. 提供FastAPI测试客户端
4. 提供测试数据样本

pytest自动发现机制：
- pytest会自动查找所有名为conftest.py的文件
- 自动加载其中定义的fixture（夹具）
- 测试用例中参数名与fixture名一致时自动注入
"""

import os
import pytest
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from app.utils import get_db
from fastapi.testclient import TestClient
from app.main import app
from urllib.parse import quote_plus

# 导入统一的Base和所有模型以确保它们被注册
from app.db_base import Base
from app.athletes.models import Athlete, AthleteMetric
from app.activities.models import Activity

password = "plz@myshit"
encoded_password = quote_plus(password)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://root:{encoded_password}@localhost/fitdb"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """测试前建表，测试后可选删表"""
    # 使用统一的Base创建所有表
    Base.metadata.create_all(bind=engine)
    yield
    # 如果需要测试后删表，取消注释
    # Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=False)
def clean_tables():
    """每个测试后清空所有表（可选，需在测试中显式使用）"""
    yield
    with engine.connect() as conn:
        # 使用统一的Base清空所有表
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()

@pytest.fixture
def db_session():
    """提供数据库会话，支持事务管理"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()  # 改为rollback以避免事务问题
    connection.close()

@pytest.fixture
def client(db_session):
    """提供FastAPI测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_user_data():
    """提供测试用的运动员数据样本"""
    return {
        "name": "测试用户",
        "ftp": 250.0,
        "max_hr": 185,
        "weight": 70.5
    }

@pytest.fixture
def sample_user_update_data():
    """提供测试用的运动员更新数据样本"""
    return {
        "ftp": 260.0,
        "max_hr": 190,
        "weight": 71.0
    }