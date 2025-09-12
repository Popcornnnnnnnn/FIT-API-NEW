"""
Activities模块的请求和响应模式

定义API接口的输入输出数据结构。
"""

from typing import List, Optional, Union, Any, Dict
from pydantic import BaseModel, Field, RootModel
from enum import Enum


class ZoneType(str, Enum):
    """区间类型枚举"""
    POWER = "power"
    HEARTRATE = "heartrate"
    HEART_RATE = "heart_rate"


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
    distance: Optional[float] = Field(None, description="距离（千米，保留两位小数）")
    moving_time: Optional[str] = Field(None, description="移动时间（格式化字符串）")
    average_speed: Optional[float] = Field(None, description="平均速度（千米每小时，保留一位小数）")
    elevation_gain: Optional[int] = Field(None, description="爬升海拔（米，保留整数）")
    avg_power: Optional[int] = Field(None, description="平均功率（瓦特，保留整数）")
    calories: Optional[int] = Field(None, description="卡路里（估算值，保留整数）")
    training_load: Optional[int] = Field(None, description="训练负荷（无单位，保留整数）")
    status: Optional[int] = Field(None, description="状态值")
    avg_heartrate: Optional[int] = Field(None, description="平均心率（保留整数）")
    max_altitude: Optional[int] = Field(None, description="最高海拔（米，保留整数）")


class PowerResponse(BaseModel):
    """活动功率信息响应"""
    avg_power: Optional[int] = Field(None, description="平均功率（瓦特，保留整数）")
    max_power: Optional[int] = Field(None, description="最大功率（瓦特，保留整数）")
    normalized_power: Optional[int] = Field(None, description="标准化功率（瓦特，保留整数）")
    intensity_factor: Optional[float] = Field(None, description="强度因子（标准化功率除以FTP，保留两位小数）")
    total_work: Optional[int] = Field(None, description="总做功（千焦，保留整数）")
    variability_index: Optional[float] = Field(None, description="变异性指数（保留两位小数）")
    weighted_average_power: Optional[int] = Field(None, description="加权平均功率")
    work_above_ftp: Optional[int] = Field(None, description="高于FTP做功（千焦，保留整数）")
    eftp: Optional[int] = Field(None, description="本次骑行的eFTP")
    w_balance_decline: Optional[float] = Field(None, description="W平衡下降（保留一位小数）")


class HeartrateResponse(BaseModel):
    """活动心率信息响应"""
    avg_heartrate: Optional[int] = Field(None, description="平均心率（保留整数）")
    max_heartrate: Optional[int] = Field(None, description="最大心率（保留整数）")
    heartrate_recovery_rate: Optional[int] = Field(None, description="心率恢复速率")
    heartrate_lag: Optional[int] = Field(None, description="心率滞后")
    efficiency_index: Optional[float] = Field(None, description="效率指数（保留两位小数）")
    decoupling_rate: Optional[str] = Field(None, description="解耦率（百分比，保留一位小数，带%符号）")


class CadenceResponse(BaseModel):
    """活动踏频信息响应"""
    avg_cadence: Optional[int] = Field(None, description="平均踏频（整数）")
    max_cadence: Optional[int] = Field(None, description="最大踏频（整数）")
    left_right_balance: Optional[Dict[str, int]] = Field(None, description="左右平衡，格式为{'left': 49, 'right': 51}")
    left_torque_effectiveness: Optional[float] = Field(None, description="左扭矩效率")
    right_torque_effectiveness: Optional[float] = Field(None, description="右扭矩效率")
    left_pedal_smoothness: Optional[float] = Field(None, description="左踏板平顺度")
    right_pedal_smoothness: Optional[float] = Field(None, description="右踏板平顺度")
    total_strokes: Optional[int] = Field(None, description="总踏频次数")


class SpeedResponse(BaseModel):
    """速度信息响应"""
    avg_speed: Optional[float] = Field(None, description="平均速度（千米每小时，保留一位小数）")
    max_speed: Optional[float] = Field(None, description="最大速度（千米每小时，保留一位小数）")
    moving_time: Optional[str] = Field(None, description="移动时间")
    total_time: Optional[str] = Field(None, description="总时间")
    pause_time: Optional[str] = Field(None, description="暂停时间")
    coasting_time: Optional[str] = Field(None, description="滑行时间")


class TrainingEffectResponse(BaseModel):
    """训练效果信息响应"""
    primary_training_benefit: Optional[str] = Field(None, description="主要训练收益")
    aerobic_effect: Optional[float] = Field(None, description="有氧效果")
    anaerobic_effect: Optional[float] = Field(None, description="无氧效果")
    training_load: Optional[int] = Field(None, description="训练负荷")
    carbohydrate_consumption: Optional[int] = Field(None, description="碳水消耗（约）")


class AltitudeResponse(BaseModel):
    """海拔信息响应"""
    elevation_gain: Optional[int] = Field(None, description="爬升海拔（米）")
    max_altitude: Optional[int] = Field(None, description="最高海拔（米）")
    max_grade: Optional[float] = Field(None, description="最大坡度（%）")
    total_descent: Optional[int] = Field(None, description="总下降（米）")
    min_altitude: Optional[int] = Field(None, description="最低海拔（米）")
    uphill_distance: Optional[float] = Field(None, description="上坡距离（公里）")
    downhill_distance: Optional[float] = Field(None, description="下坡距离（公里）")


class TemperatureResponse(BaseModel):
    """温度信息响应"""
    min_temp: Optional[int] = Field(None, description="最低温度（摄氏度）")
    avg_temp: Optional[int] = Field(None, description="平均温度（摄氏度）")
    max_temp: Optional[int] = Field(None, description="最高温度（摄氏度）")


class TrainingEffectRequest(BaseModel):
    """训练效果请求参数"""
    duration: Optional[int] = Field(None, description="训练时长（秒）")


class MultiStreamRequest(BaseModel):
    """多字段流数据请求"""
    keys: List[str] = Field(..., description="请求的流数据类型列表")
    resolution: str = Field(..., description="数据分辨率：low, medium, high")


class StreamDataItem(BaseModel):
    """流数据项"""
    type: str
    data: Optional[List[Any]]


class MultiStreamResponse(RootModel[List[StreamDataItem]]):
    """多字段流数据响应"""
    pass


class SegmentRecord(BaseModel):
    """分段记录信息"""
    segment_name: str = Field(..., description="分段名称")
    current_value: Union[int, float] = Field(..., description="当前值")
    rank: int = Field(..., description="历史排名（1、2、3）")
    activity_id: int = Field(..., description="活动ID")
    record_type: str = Field(..., description="记录类型（power、distance、elevation）")
    unit: str = Field(..., description="单位")
    previous_record: Optional[Union[int, float]] = Field(None, description="之前的记录值")
    improvement: Optional[Union[int, float]] = Field(None, description="提升值")


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
    streams: Optional[List[Dict[str, Any]]] = Field(None, description="流数据，数组格式，每个元素包含type、data、series_type、original_size、resolution字段")
    segment_records: Optional[List[SegmentRecord]] = Field(None, description="分段记录刷新信息")

