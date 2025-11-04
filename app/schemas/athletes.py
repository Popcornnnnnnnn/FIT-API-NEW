"""
Athletes模块的请求和响应模式

定义运动员相关API接口的输入输出数据结构。
"""

from typing import Optional
from pydantic import BaseModel, Field


class DailyStateDetail(BaseModel):
    """每日状态详情"""
    athlete_id: int = Field(..., description="运动员ID")
    date: str = Field(..., description="日期（YYYY-MM-DD）")
    fitness: float = Field(..., description="健康度（最近42天平均TSS）")
    fatigue: float = Field(..., description="疲劳度（最近7天平均TSS）")
    daily_status: float = Field(..., description="状态值（fitness - fatigue）")


class DailyStateUpdateResponse(BaseModel):
    """每日状态更新响应"""
    message: str = Field(..., description="响应消息")
    status: str = Field(..., description="状态：success 或 failed")
    data: DailyStateDetail = Field(..., description="更新结果详情")

