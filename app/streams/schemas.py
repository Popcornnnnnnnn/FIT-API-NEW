"""
本文件定义了数据流相关的Pydantic数据模型，用于API请求和响应的数据验证与序列化。

包含以下模型：
1. StreamDataPoint: 单个数据点模型
2. StreamResponse: 流数据响应模型
3. StreamRequest: 流数据请求模型
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class StreamDataPoint(BaseModel):
    """单个数据点模型"""
    timestamp: float
    power: Optional[float] = None
    heart_rate: Optional[float] = None
    cadence: Optional[float] = None
    speed: Optional[float] = None
    distance: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

class StreamResponse(BaseModel):
    """流数据响应模型"""
    activity_id: int
    stream_type: str  # 流数据类型：power, heart_rate, gps等
    data: List[StreamDataPoint]
    sample_rate: Optional[int] = None

class StreamRequest(BaseModel):
    """流数据请求模型"""
    activity_id: int
    stream_types: List[str] = ["power", "heart_rate"]  # 请求的流数据类型
    sample_rate: Optional[int] = 1  # 采样率 