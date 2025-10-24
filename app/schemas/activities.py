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


class BestPowerResponse(BaseModel):
    """最佳功率响应"""
    best_powers: Dict[str, int] = Field(..., description="各时间窗最佳功率，键如 5s/1min/20min 等")


class BestPowerCurveRecord(BaseModel):
    """运动员全局最佳功率曲线（逐秒）。"""
    athlete_id: int = Field(..., description="运动员ID（本地）")
    length: int = Field(..., description="曲线长度（秒）")
    best_curve: List[int] = Field(..., description="每秒最佳平均功率数组")


class IntervalItem(BaseModel):
    """单个区间的统计信息"""

    start: int = Field(..., description="区间起点（秒）")
    end: int = Field(..., description="区间终点（秒，开区间）")
    duration: int = Field(..., description="持续时间（秒）")
    classification: str = Field(..., description="区间分类，如 sprint/vo2max 等")
    average_power: float = Field(..., description="区间平均功率")
    peak_power: float = Field(..., description="区间峰值功率")
    normalized_power: float = Field(..., description="区间标准化功率")
    intensity_factor: float = Field(..., description="区间强度因子")
    power_ratio: float = Field(..., description="平均功率与 FTP 的比值")
    time_above_95: float = Field(..., description="功率超过 95% FTP 的时间占比")
    time_above_106: float = Field(..., description="功率超过 106% FTP 的时间占比")
    time_above_120: float = Field(..., description="功率超过 120% FTP 的时间占比")
    time_above_150: float = Field(..., description="功率超过 150% FTP 的时间占比")
    heart_rate_avg: Optional[float] = Field(None, description="区间平均心率")
    heart_rate_max: Optional[int] = Field(None, description="区间最大心率")
    heart_rate_slope: Optional[float] = Field(None, description="心率斜率（bpm / s）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加信息")


class ZoneSegmentVisual(BaseModel):
    metric: str = Field(..., description="强度来源类型（power 或 heart_rate）")
    zone: Optional[str] = Field(None, description="所属区间编号，如 Z1")
    label: Optional[str] = Field(None, description="区间名称")
    start_time: float = Field(..., description="片段开始时间（秒）")
    end_time: float = Field(..., description="片段结束时间（秒）")
    duration_seconds: float = Field(..., description="片段持续时间（秒）")
    height: float = Field(..., description="相对高度（0-1，映射到图形高度）")
    intensity_ratio: float = Field(..., description="平均强度相对于阈值的比例")
    average_value: float = Field(..., description="片段平均绝对值（功率或心率）")


class IntervalsResponse(BaseModel):
    """活动区间识别结果"""

    duration: int = Field(..., description="活动总时长（秒）")
    ftp: float = Field(..., description="用于计算的 FTP")
    items: List[IntervalItem] = Field(..., description="区间详情列表")
    preview_image: Optional[str] = Field(None, description="预览图路径（相对于项目根目录）")
    zone_segments: Optional[List[ZoneSegmentVisual]] = Field(
        None,
        description="分区可视化片段列表，包含开始/结束时间、高度、强度等信息",
    )


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
    best_power_record: Optional[BestPowerCurveRecord] = Field(None, description="运动员全局最佳功率曲线（逐秒）")
    intervals: Optional[IntervalsResponse] = Field(None, description="区间识别结果")
    zone_preview_path: Optional[str] = Field(None, description="分区预览图路径")
