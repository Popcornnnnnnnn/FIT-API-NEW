"""
Activities模块的数据模型

包含活动区间分析相关的数据结构和模型。
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, BIGINT
from ..db_base import Base

class ZoneType(str, Enum):
    """区间类型枚举"""
    POWER = "power"
    HEARTRATE = "heartrate"

class DistributionBucket(BaseModel):
    """区间分布桶"""
    min: int = Field(..., description="区间最小值")
    max: int = Field(..., description="区间最大值")
    time: str = Field(..., description="在该区间的时间（格式化字符串）")
    percentage: str = Field(..., description="该区间占总时长的百分比")

class ZoneData(BaseModel):
    """区间数据"""
    distribution_buckets: List[DistributionBucket] = Field(..., description="区间分布桶列表")
    type: str = Field(..., description="区间类型（power或heartrate）")

class ZoneResponse(BaseModel):
    """区间响应数据"""
    zones: List[ZoneData] = Field(..., description="区间数据列表")

# 缓存表模型
class TbActivityCache(Base):
    """活动数据缓存表"""
    __tablename__ = "tb_activity_cache"
    
    id = Column(BIGINT, primary_key=True, autoincrement=True, index=True)
    activity_id = Column(BIGINT, unique=True, index=True, nullable=False, comment="活动ID")
    cache_key = Column(String(255), nullable=False, comment="缓存键（用于标识不同的缓存版本）")
    file_path = Column(String(500), nullable=False, comment="JSON文件在服务器上的存储路径")
    file_size = Column(BIGINT, comment="文件大小（字节）")
    created_at = Column(DateTime, nullable=False, comment="缓存创建时间")
    updated_at = Column(DateTime, nullable=False, comment="缓存更新时间")
    expires_at = Column(DateTime, comment="缓存过期时间")
    is_active = Column(Integer, default=1, comment="是否激活（1=激活，0=禁用）")
    metadata = Column(Text, comment="缓存元数据（JSON格式）") 