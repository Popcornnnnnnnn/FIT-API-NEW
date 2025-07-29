"""
本文件定义了活动相关的Pydantic数据模型，用于API请求和响应的数据验证与序列化。

包含以下模型：
1. ActivityBase: 活动基础模型，包含基本字段
2. ActivityCreate: 创建活动时的请求模型
3. ActivityUpdate: 更新活动时的请求模型
4. Activity: 活动完整响应模型
5. ActivitySummary: 活动摘要响应模型
6. ZoneBucket: 区间分布桶模型
7. ZoneDistribution: 区间分布模型
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
import datetime

class ActivityBase(BaseModel):
    """活动基础模型"""
    athlete_id: int
    activity_type: Optional[str] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_power: Optional[float] = None
    avg_hr: Optional[float] = None
    max_power: Optional[float] = None
    max_hr: Optional[float] = None

class ActivityCreate(ActivityBase):
    """创建活动时的请求模型"""
    pass

class ActivityUpdate(BaseModel):
    """更新活动时的请求模型（所有字段都是可选的）"""
    activity_type: Optional[str] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_power: Optional[float] = None
    avg_hr: Optional[float] = None
    max_power: Optional[float] = None
    max_hr: Optional[float] = None

class Activity(ActivityBase):
    """活动完整响应模型"""
    id: int
    file_path: Optional[str] = None
    summary_data: Optional[str] = None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)  # 允许从ORM对象创建

class ActivitySummary(BaseModel):
    """活动摘要响应模型"""
    activity_id: int
    distance_km: float
    duration_min: float
    avg_power: Optional[float] = None
    avg_hr: Optional[float] = None
    max_power: Optional[float] = None
    max_hr: Optional[float] = None
    activity_type: Optional[str] = None

class ZoneBucket(BaseModel):
    """区间分布桶模型"""
    min: float
    max: float
    time: int  # 时间（秒）
    string: str  # 格式化的时间字符串
    percentage: str  # 百分比字符串
    name: Optional[str] = None  # 区间名称

class ZoneDistribution(BaseModel):
    """区间分布模型"""
    distribution_buckets: List[ZoneBucket]
    type: str  # "power" 或 "heart_rate" 