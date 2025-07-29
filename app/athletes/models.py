"""
本文件定义了运动员相关的数据模型（ORM类），用于数据库表结构的声明。

1. Athlete 类：表示运动员实体，对应 athletes 表。包含运动员的基本信息（姓名、FTP、最大心率、体重），并通过关系关联其指标（metrics）和活动（activities）。
2. AthleteMetric 类：用于记录运动员在某一时刻的某项身体或运动能力指标（如某次测试的FTP、体脂率、最大摄氧量等），对应 athlete_metrics 表。每条 AthleteMetric 记录都属于一个运动员（athlete_id），并包含该指标的名称、数值和记录时间。这样可以追踪运动员随时间变化的各项能力或身体状态。
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from ..db_base import Base

class Athlete(Base):
    """
    运动员表模型
    - id: 主键
    - name: 运动员姓名，必填
    - ftp: 功能阈值功率（可选）
    - max_hr: 最大心率（可选）
    - weight: 体重（可选）
    - metrics: 该运动员的所有指标（AthleteMetric 关联）
    - activities: 该运动员的所有活动（Activity 关联，需在 app.activities.models 中定义）
    """
    __tablename__ = 'athletes'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    ftp = Column(Float, nullable=True)
    max_hr = Column(Integer, nullable=True)
    weight = Column(Float, nullable=True)
    wj = Column(Float, nullable=True, default=20000)  # 无氧储备，单位焦耳，默认20000
    metrics = relationship('AthleteMetric', back_populates='athlete')
    activities = relationship('Activity', back_populates='athlete', lazy='dynamic')

class AthleteMetric(Base):
    """
    运动员指标表模型
    AthleteMetric 不是指“运动员的单项指标”这个概念本身，而是指“某个运动员在某个时间点的某项具体指标的记录”。
    例如：2024年5月1日，张三的FTP为250；2024年6月1日，张三的体脂率为15%。每一条 AthleteMetric 记录就是这样一条具体的历史数据。
    - id: 主键
    - athlete_id: 外键，关联到 Athlete
    - metric_name: 指标名称（如 FTP、体脂率、最大摄氧量等）
    - metric_value: 指标数值
    - updated_at: 记录该指标的时间（通常为创建或最近一次更新的时间）
    - athlete: 反向引用，指向所属 Athlete
    """
    __tablename__ = 'athlete_metrics'
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey('athletes.id'))
    metric_name = Column(String(32), nullable=False)
    metric_value = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    athlete = relationship('Athlete', back_populates='metrics') 