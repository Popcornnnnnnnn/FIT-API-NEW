"""
conftest_mysql.py 说明：

1. pytest 是如何自动发现并加载本文件的？
   - pytest 会自动查找所有名为 conftest.py 或 conftest_xxx.py 的文件（如本文件名为 conftest_mysql.py），
     并自动加载其中定义的 fixture（夹具）。
   - 只要你的测试用例（如 test_users.py）通过 pytest_plugins = ["tests.conftest_mysql"] 指定了本文件，
     pytest 就会自动导入本文件，并注册所有 fixture。
   - 这样，测试用例里只要参数名和 fixture 名字一致（如 client、db_session），pytest 就会自动注入对应的 fixture。

2. TestClient 是怎么被创建出来并注入到测试用例的？
   - 本文件定义了 client 这个 pytest fixture（见下方 @pytest.fixture def client ...）。
   - 只要测试用例函数有 client 参数，pytest 会自动调用本 fixture，返回 TestClient(app) 实例。
   - 这个 TestClient 会自动用测试数据库（通过依赖覆盖 get_db），让你在测试里像用 requests 一样请求 FastAPI 应用。

3. 你只需要在测试用例里写 def test_xxx(client): ...，pytest 会自动帮你准备好 client（TestClient 实例），
   并且所有数据库操作都在测试事务里，测试结束后自动清理。

"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.utils import get_db
from fastapi.testclient import TestClient
from app.main import app
from urllib.parse import quote_plus

# 读取环境变量或使用默认MySQL测试库
password = "plz@myshit"
encoded_password = quote_plus(password)
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://root:{encoded_password}@localhost/fitdb"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """测试前建表，测试后可选删表"""
    Base.metadata.create_all(bind=engine)
    yield
    # Base.metadata.drop_all(bind=engine)  # 如需测试后删表，取消注释

@pytest.fixture(autouse=False)
def clean_tables():
    """每个测试后清空所有表（可选，需在测试中显式使用）"""
    yield
    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()

@pytest.fixture
def db_session():
    """
    提供一个数据库 session，所有通过 client 发起的请求都用同一个 session（同一个事务）。
    测试结束后自动关闭 session 并提交事务（如需测试隔离可改为 rollback）。
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.commit()
    # transaction.rollback()  # 如果想每次测试后回滚（推荐测试隔离），用 rollback
    connection.close()

@pytest.fixture
def client(db_session):
    """
    提供 FastAPI 的 TestClient，自动用测试数据库 session。
    只要测试用例参数有 client，pytest 会自动注入本 fixture。
    """
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_user_data():
    return {
        "name": "测试用户",
        "ftp": 250.0,
        "max_hr": 185,
        "weight": 70.5
    }

@pytest.fixture
def sample_user_update_data():
    return {
        "ftp": 260.0,
        "max_hr": 190,
        "weight": 71.0
    }