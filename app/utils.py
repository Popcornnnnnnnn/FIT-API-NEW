"""
本文件包含数据库连接和会话管理的工具函数。

主要功能：
1. 数据库连接配置（从环境变量读取，避免硬编码）
2. 数据库会话管理
3. FastAPI依赖注入
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import get_database_url


DATABASE_URL = get_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI 依赖项：获取数据库会话（Session）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
