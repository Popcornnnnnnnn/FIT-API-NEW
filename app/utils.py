"""
本文件包含数据库连接和会话管理的工具函数。

主要功能：
1. 数据库连接配置
2. 数据库会话管理
3. FastAPI依赖注入
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
from urllib.parse import quote_plus

# 本地开发环境数据库连接URL
# 生产环境建议通过环境变量DATABASE_URL进行配置

password = "plz@myshit"
encoded_password = quote_plus(password)  
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://root:{encoded_password}@localhost/fitdb"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI依赖项，用于获取数据库会话（Session）。
    
    每次请求调用get_db时，会创建一个新的数据库会话db，
    并在请求处理完毕后自动关闭，确保资源释放。
    """
    db = SessionLocal()
    try:
        yield db  # 提供数据库会话给依赖它的路径操作函数
    finally:
        db.close()  # 请求结束后关闭会话，防止连接泄漏