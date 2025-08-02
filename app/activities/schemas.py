"""
Activities模块的请求和响应模式

定义API接口的输入输出数据结构。
"""

from typing import List
from pydantic import BaseModel, Field
from enum import Enum

class ZoneType(str, Enum):
    """区间类型枚举"""
    POWER = "power"
    HEARTRATE = "heartrate"

class ZoneRequest(BaseModel):
    """区间请求参数"""
    key: ZoneType = Field(..., description="区间类型：power（功率）或heartrate（心率）")

class DistributionBucket(BaseModel):
    """区间分布桶"""
    min: int = Field(..., description="区间最小值")
    max: int = Field(..., description="区间最大值")
    time: str = Field(..., description="在该区间的时间（格式化字符串，如xx:xx:xx或xxs）")
    percentage: str = Field(..., description="该区间占总时长的百分比，如xx%")

class ZoneData(BaseModel):
    """区间数据"""
    distribution_buckets: List[DistributionBucket] = Field(..., description="区间分布桶列表")
    type: str = Field(..., description="区间类型（power或heartrate）")

class ZoneResponse(BaseModel):
    """区间响应数据"""
    zones: List[ZoneData] = Field(..., description="区间数据列表") 