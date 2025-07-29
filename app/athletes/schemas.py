"""
本文件定义了运动员相关的Pydantic数据模型，用于API请求和响应的数据验证与序列化。

包含以下模型：
1. AthleteBase: 运动员基础模型，包含基本字段
2. AthleteCreate: 创建运动员时的请求模型
3. AthleteUpdate: 更新运动员时的请求模型
4. Athlete: 运动员完整响应模型
5. AthleteMetricBase: 运动员指标基础模型
6. AthleteMetricCreate: 创建指标时的请求模型
7. AthleteMetric: 指标完整响应模型
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional
import datetime

class AthleteBase(BaseModel):
    """运动员基础模型"""
    name: str
    ftp: Optional[float] = None
    max_hr: Optional[int] = None
    weight: Optional[float] = None
    wj: Optional[float] = 20000  # 无氧储备，单位焦耳，默认20000

class AthleteCreate(AthleteBase):
    """创建运动员时的请求模型"""
    pass

class AthleteUpdate(BaseModel):
    """更新运动员时的请求模型（所有字段都是可选的）"""
    name: Optional[str] = None
    ftp: Optional[float] = None
    max_hr: Optional[int] = None
    weight: Optional[float] = None
    wj: Optional[float] = None  # 无氧储备，单位焦耳

class Athlete(AthleteBase):
    """运动员完整响应模型"""
    id: int
    model_config = ConfigDict(from_attributes=True)  # 允许从ORM对象创建

class AthleteMetricBase(BaseModel):
    """运动员指标基础模型"""
    metric_name: str
    metric_value: float

class AthleteMetricCreate(AthleteMetricBase):
    """创建指标时的请求模型"""
    pass

class AthleteMetric(AthleteMetricBase):
    """指标完整响应模型"""
    id: int
    athlete_id: int
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)  # 允许从ORM对象创建 