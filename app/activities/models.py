"""
Activities模块的数据模型

包含活动区间分析相关的数据结构和模型。
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

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