# 这个文件定义了项目的数据库模型（ORM模型），用于描述和操作数据库中的表结构。
# 使用 SQLAlchemy 的声明式基类（declarative_base）来定义模型类，每个类对应数据库中的一张表。

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
import datetime

Base = declarative_base()

# 用户表模型，存储用户基本信息
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)  # 用户ID，主键
    name = Column(String(64), nullable=False)           # 用户名
    ftp = Column(Float, nullable=True)                  # FTP (Functional Threshold Power)
    max_hr = Column(Integer, nullable=True)             # 最大心率
    weight = Column(Float, nullable=True)               # 体重 (kg)
    # 关联用户的指标和活动（与UserMetric和Activity表的关系）
    metrics = relationship('UserMetric', back_populates='user')
    activities = relationship('Activity', back_populates='user')

# 用户指标表模型，存储每个用户的各类指标（如体重、身高等）
class UserMetric(Base):
    __tablename__ = 'user_metrics'
    id = Column(Integer, primary_key=True, index=True)  # 指标ID，主键
    user_id = Column(Integer, ForeignKey('users.id'))   # 外键，关联用户
    metric_name = Column(String(32), nullable=False)    # 指标名称
    metric_value = Column(Float, nullable=False)        # 指标数值
    updated_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))  # 更新时间
    user = relationship('User', back_populates='metrics')            # 反向关系

# 活动表模型，存储用户上传的活动（如FIT文件）
class Activity(Base):
    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True, index=True)  # 活动ID，主键
    user_id = Column(Integer, ForeignKey('users.id'))   # 外键，关联用户
    file_path = Column(String(256))                     # 活动文件路径
    created_at = Column(DateTime, default=datetime.datetime.now(datetime.UTC))  # 创建时间
    # 可扩展更多字段，如摘要、分析结果等
    user = relationship('User', back_populates='activities')         # 反向关系