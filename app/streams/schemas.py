"""
本文件定义了数据流相关的Pydantic模型，用于API请求和响应。

包含：
1. 流数据请求模型
2. 流数据响应模型
3. 流数据统计模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Union
from enum import Enum

class Resolution(str, Enum):
    """数据分辨率枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class StreamRequest(BaseModel):
    """流数据请求模型"""
    keys: List[str] = Field(..., description="请求的流数据类型列表")
    resolution: Resolution = Field(default=Resolution.HIGH, description="数据分辨率")

class StreamResponse(BaseModel):
    """流数据响应模型"""
    type: str = Field(..., description="流数据类型")
    data: List[Union[int, float]] = Field(..., description="数据点列表")
    series_type: str = Field(..., description="系列类型")
    original_size: int = Field(..., description="原始数据点数量")
    resolution: str = Field(..., description="数据分辨率")

class StreamsResponse(BaseModel):
    """多个流数据响应模型"""
    streams: List[StreamResponse] = Field(..., description="流数据列表")
    activity_id: int = Field(..., description="活动ID")
    total_streams: int = Field(..., description="总流数据数量")

class StreamSummary(BaseModel):
    """流数据统计信息模型"""
    type: str = Field(..., description="流数据类型")
    count: int = Field(..., description="数据点数量")
    min_value: Optional[Union[int, float]] = Field(None, description="最小值")
    max_value: Optional[Union[int, float]] = Field(None, description="最大值")
    avg_value: Optional[float] = Field(None, description="平均值")
    total_value: Optional[Union[int, float]] = Field(None, description="总和（仅适用于distance和time）") 