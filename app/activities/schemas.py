"""
Activities模块的请求和响应模式

定义API接口的输入输出数据结构。
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field, RootModel
from enum import Enum
from typing import Dict

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

class OverallResponse(BaseModel):
    """活动总体信息响应"""
    distance: float = Field(..., description="距离（千米，保留两位小数）")
    moving_time: str = Field(..., description="移动时间（格式化字符串）")
    average_speed: float = Field(..., description="平均速度（千米每小时，保留一位小数）")
    elevation_gain: int = Field(..., description="爬升海拔（米，保留整数）")
    avg_power: Optional[int] = Field(None, description="平均功率（瓦特，保留整数）")
    calories: int = Field(..., description="卡路里（估算值，保留整数）")
    training_load: int = Field(..., description="训练负荷（无单位，保留整数）")
    status: Optional[str] = Field(None, description="状态值")
    avg_heartrate: Optional[int] = Field(None, description="平均心率（保留整数）")
    max_altitude: Optional[int] = Field(None, description="最高海拔（米，保留整数）") 

class PowerResponse(BaseModel):
    """活动功率信息响应"""
    avg_power: int = Field(..., description="平均功率（瓦特，保留整数）")
    max_power: int = Field(..., description="最大功率（瓦特，保留整数）")
    normalized_power: int = Field(..., description="标准化功率（瓦特，保留整数）")
    intensity_factor: Optional[float] = Field(None, description="强度因子（标准化功率除以FTP，保留两位小数）")
    total_work: int = Field(..., description="总做功（千焦，保留整数）")
    variability_index: Optional[float] = Field(None, description="变异性指数（保留两位小数）")
    weighted_average_power: Optional[int] = Field(None, description="加权平均功率")
    work_above_ftp: Optional[int] = Field(None, description="高于FTP做功（千焦，保留整数）")
    eftp: Optional[int] = Field(None, description="本次骑行的eFTP")
    w_balance_decline: Optional[float] = Field(None, description="W平衡下降（保留一位小数）") 

class HeartrateResponse(BaseModel):
    """活动心率信息响应"""
    avg_heartrate: int = Field(..., description="平均心率（保留整数）")
    max_heartrate: int = Field(..., description="最大心率（保留整数）")
    heartrate_recovery_rate: Optional[float] = Field(None, description="心率恢复速率")
    heartrate_lag: Optional[float] = Field(None, description="心率滞后")
    efficiency_index: float = Field(..., description="效率指数（保留两位小数）")
    decoupling_rate: str = Field(..., description="解耦率（百分比，保留一位小数，带%符号）") 

class CadenceResponse(BaseModel):
    """活动踏频信息响应"""
    avg_cadence: int = Field(..., description="平均踏频（整数）")
    max_cadence: int = Field(..., description="最大踏频（整数）")
    left_right_balance: Optional[Dict[str, int]] = Field(None, description="左右平衡，格式为{'left': 49, 'right': 51}")
    left_torque_effectiveness: Optional[float] = Field(None, description="左扭矩效率")
    right_torque_effectiveness: Optional[float] = Field(None, description="右扭矩效率")
    left_pedal_smoothness: Optional[float] = Field(None, description="左踏板平顺度")
    right_pedal_smoothness: Optional[float] = Field(None, description="右踏板平顺度")
    total_strokes: int = Field(..., description="踏板总行程数（一共踩踏了多少次）")

class SpeedResponse(BaseModel):
    """活动速度信息响应"""
    avg_speed: float = Field(..., description="平均速度（千米每小时，保留一位小数）")
    max_speed: float = Field(..., description="最大速度（千米每小时，保留一位小数）")
    moving_time: str = Field(..., description="移动时间（格式化字符串）")
    total_time: str = Field(..., description="全程耗时（格式化字符串）")
    pause_time: str = Field(..., description="暂停时间（格式化字符串）")
    coasting_time: str = Field(..., description="滑行时间（格式化字符串）") 

class AltitudeResponse(BaseModel):
    """活动海拔信息响应"""
    elevation_gain: int = Field(..., description="爬升海拔（米，保留整数）")
    max_altitude: int = Field(..., description="最高海拔（米，保留整数）")
    max_grade: float = Field(..., description="最大坡度（百分比，保留一 位小数）")
    total_descent: int = Field(..., description="累计下降（米，保留整数）")
    min_altitude: int = Field(..., description="最低海拔（米，保留整数）")
    uphill_distance: float = Field(..., description="上坡距离（千米，保留两位小数）")
    downhill_distance: float = Field(..., description="下坡距离（千米，保留两位小数）") 

class TemperatureResponse(BaseModel):
    """活动温度信息响应"""
    min_temp: int = Field(..., description="最低温度（摄氏度，保留整数）")
    avg_temp: int = Field(..., description="平均温度（摄氏度，保留整数）")
    max_temp: int = Field(..., description="最大温度（摄氏度，保留整数）") 

class BestPowerResponse(BaseModel):
    """活动最佳功率信息响应"""
    best_powers: Dict[str, int] = Field(..., description="最佳功率数据，键为时间区间（如'5s', '30s', '1min', '5min', '8min', '20min', '30min', '1h'），值为对应的最佳功率（瓦特）")

class TrainingEffectResponse(BaseModel):
    """活动训练效果信息响应"""
    primary_training_benefit: str = Field(..., description="主要训练益处")
    aerobic_effect: str = Field(..., description="有氧效果")
    anaerobic_effect: str = Field(..., description="无氧效果")
    training_load: int = Field(..., description="训练负荷（无单位，保留整数）")
    carbohydrate_consumption: str = Field(..., description="碳水化合物消耗量")

class StreamDataItem(BaseModel):
    """流数据项"""
    type: str = Field(..., description="流数据类型")
    data: Optional[List[Union[float, int]]] = Field(None, description="流数据数组，如果字段不存在则为None")

class MultiStreamRequest(BaseModel):
    """多字段流数据请求"""
    keys: List[str] = Field(..., description="请求的流数据类型列表")
    resolution: str = Field(..., description="数据分辨率：low, medium, high")

class MultiStreamResponse(RootModel[List[StreamDataItem]]):
    """多字段流数据响应"""
    pass

class AllActivityDataResponse(BaseModel):
    """活动所有数据响应"""
    overall: Optional[OverallResponse] = Field(None, description="总体信息")
    power: Optional[PowerResponse] = Field(None, description="功率信息")
    heartrate: Optional[HeartrateResponse] = Field(None, description="心率信息")
    cadence: Optional[CadenceResponse] = Field(None, description="踏频信息")
    speed: Optional[SpeedResponse] = Field(None, description="速度信息")
    training_effect: Optional[TrainingEffectResponse] = Field(None, description="训练效果信息")
    altitude: Optional[AltitudeResponse] = Field(None, description="海拔信息")
    temp: Optional[TemperatureResponse] = Field(None, description="温度信息")
    zones: Optional[List[ZoneData]] = Field(None, description="区间分析信息")
    best_powers: Optional[Dict[str, int]] = Field(None, description="最佳功率信息")