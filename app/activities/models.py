"""
本文件定义了活动相关的数据模型（ORM类），用于数据库表结构的声明。

Activity 类：表示运动活动实体，对应 activities 表。包含活动的基本信息（类型、距离、时长、功率、心率等），并通过外键关联到运动员（athlete_id）。
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship
import datetime
from ..db_base import Base

class Activity(Base):
    """
    活动表模型
    - id: 主键
    - athlete_id: 外键，关联到运动员表
    - file_path: FIT文件路径
    - file_data: 原始文件数据（二进制）
    - file_name: 原始文件名
    - name: 活动名称
    - description: 活动描述
    - trainer: 是否在训练台上进行
    - commute: 是否通勤活动
    - data_type: 文件格式（fit, tcx, gpx等）
    - external_id: 外部标识符
    - status: 处理状态（pending, processing, completed, failed）
    - error: 错误信息
    - activity_type: 活动类型（骑行、跑步等）
    - distance_km: 距离（公里）
    - duration_min: 时长（分钟）
    - avg_power: 平均功率
    - avg_hr: 平均心率
    - max_power: 最大功率
    - max_hr: 最大心率
    - summary_data: 活动摘要JSON数据
    - created_at: 创建时间
    - athlete: 反向引用，指向所属运动员
    """
    __tablename__ = 'activities'
    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey('athletes.id'))
    file_path = Column(String(256))
    file_data = Column(LONGTEXT)  # 存储原始文件数据
    file_name = Column(String(256))  # 原始文件名
    name = Column(String(256), nullable=True)  # 活动名称
    description = Column(Text, nullable=True)  # 活动描述
    trainer = Column(Boolean, default=False)  # 是否在训练台上进行
    commute = Column(Boolean, default=False)  # 是否通勤活动
    data_type = Column(String(32), nullable=True)  # 文件格式：fit, tcx, gpx等
    external_id = Column(String(256), nullable=True)  # 外部标识符
    status = Column(String(32), default="pending")  # 处理状态
    error = Column(Text, nullable=True)  # 错误信息
    activity_type = Column(String(32), nullable=True)  # 活动类型：骑行、跑步等
    distance_km = Column(Float, nullable=True)         # 距离(公里)
    duration_min = Column(Float, nullable=True)        # 时长(分钟)
    avg_power = Column(Float, nullable=True)           # 平均功率
    avg_hr = Column(Float, nullable=True)              # 平均心率
    max_power = Column(Float, nullable=True)           # 最大功率
    max_hr = Column(Float, nullable=True)              # 最大心率
    summary_data = Column(Text, nullable=True)         # 活动摘要JSON数据
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # 关联运动员
    athlete = relationship('Athlete', back_populates='activities') 