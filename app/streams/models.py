"""
本文件定义了数据流相关的数据模型。

包含：
1. BaseStream - 基础流数据类
2. 具体的Stream类 - 继承BaseStream，包含具体的数据点
3. StreamData - 用于存储和访问FIT文件中的原始数据
4. 数据库模型 - tb_activity和tb_athlete表的映射
"""

from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import sys
from sqlalchemy import BIGINT, VARCHAR, Column, Integer, String, Float, Text, DateTime
from ..db_base import Base

class Resolution(str, Enum):
    """数据分辨率枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class SeriesType(str, Enum):
    """系列类型枚举"""
    DISTANCE = "distance"
    TIME = "time"
    NONE = "none"

class TbActivity(Base):
    """活动表模型"""
    __tablename__ = "tb_activity"
    
    id                    = Column(BIGINT, primary_key=True, index=True)
    athlete_id            = Column(BIGINT)
    upload_fit_url        = Column(VARCHAR(255))
    name                  = Column(VARCHAR(255))
    external_id           = Column(VARCHAR(255))
    tss                   = Column(Integer)
    tss_updated           = Column(Integer, default=0)
    start_date            = Column(DateTime)

class TbAthlete(Base):
    """运动员表模型"""
    __tablename__ = "tb_athlete"
    
    id            = Column(BIGINT, primary_key=True, index=True)
    max_heartrate = Column(Integer)
    ftp           = Column(VARCHAR(255))
    w_balance     = Column(Integer)
    weight        = Column(Integer)
    tsb           = Column(Integer)
    ctl           = Column(Integer)
    atl           = Column(Integer)

class TbAthletePowerRecords(Base):
    __tablename__ = "tb_athlete_power_records"
    
    athlete_id = Column(BIGINT, primary_key=True, index=True)
    power_5s_1st = Column(Integer)
    power_5s_1st_activity_id = Column(BIGINT)
    power_5s_2nd = Column(Integer)
    power_5s_2nd_activity_id = Column(BIGINT)
    power_5s_3rd = Column(Integer)
    power_5s_3rd_activity_id = Column(BIGINT)
    power_15s_1st = Column(Integer)
    power_15s_1st_activity_id = Column(BIGINT)
    power_15s_2nd = Column(Integer)
    power_15s_2nd_activity_id = Column(BIGINT)
    power_15s_3rd = Column(Integer)
    power_15s_3rd_activity_id = Column(BIGINT)
    power_30s_1st = Column(Integer)
    power_30s_1st_activity_id = Column(BIGINT)
    power_30s_2nd = Column(Integer)
    power_30s_2nd_activity_id = Column(BIGINT)
    power_30s_3rd = Column(Integer)
    power_30s_3rd_activity_id = Column(BIGINT)
    power_1m_1st = Column(Integer)
    power_1m_1st_activity_id = Column(BIGINT)
    power_1m_2nd = Column(Integer)
    power_1m_2nd_activity_id = Column(BIGINT)
    power_1m_3rd = Column(Integer)
    power_1m_3rd_activity_id = Column(BIGINT)
    power_2m_1st = Column(Integer)
    power_2m_1st_activity_id = Column(BIGINT)
    power_2m_2nd = Column(Integer)
    power_2m_2nd_activity_id = Column(BIGINT)
    power_2m_3rd = Column(Integer)
    power_2m_3rd_activity_id = Column(BIGINT)
    power_3m_1st = Column(Integer)
    power_3m_1st_activity_id = Column(BIGINT)
    power_3m_2nd = Column(Integer)
    power_3m_2nd_activity_id = Column(BIGINT)
    power_3m_3rd = Column(Integer)
    power_3m_3rd_activity_id = Column(BIGINT)
    power_5m_1st = Column(Integer)
    power_5m_1st_activity_id = Column(BIGINT)
    power_5m_2nd = Column(Integer)
    power_5m_2nd_activity_id = Column(BIGINT)
    power_5m_3rd = Column(Integer)
    power_5m_3rd_activity_id = Column(BIGINT)
    power_10m_1st = Column(Integer)
    power_10m_1st_activity_id = Column(BIGINT)
    power_10m_2nd = Column(Integer)
    power_10m_2nd_activity_id = Column(BIGINT)
    power_10m_3rd = Column(Integer)
    power_10m_3rd_activity_id = Column(BIGINT)
    power_15m_1st = Column(Integer)
    power_15m_1st_activity_id = Column(BIGINT)
    power_15m_2nd = Column(Integer)
    power_15m_2nd_activity_id = Column(BIGINT)
    power_15m_3rd = Column(Integer)
    power_15m_3rd_activity_id = Column(BIGINT)
    power_20m_1st = Column(Integer)
    power_20m_1st_activity_id = Column(BIGINT)
    power_20m_2nd = Column(Integer)
    power_20m_2nd_activity_id = Column(BIGINT)
    power_20m_3rd = Column(Integer)
    power_20m_3rd_activity_id = Column(BIGINT)
    power_30m_1st = Column(Integer)
    power_30m_1st_activity_id = Column(BIGINT)
    power_30m_2nd = Column(Integer)
    power_30m_2nd_activity_id = Column(BIGINT)
    power_30m_3rd = Column(Integer)
    power_30m_3rd_activity_id = Column(BIGINT)
    power_45m_1st = Column(Integer)
    power_45m_1st_activity_id = Column(BIGINT)
    power_45m_2nd = Column(Integer)
    power_45m_2nd_activity_id = Column(BIGINT)
    power_45m_3rd = Column(Integer)
    power_45m_3rd_activity_id = Column(BIGINT)
    power_60m_1st = Column(Integer)
    power_60m_1st_activity_id = Column(BIGINT)
    power_60m_2nd = Column(Integer)
    power_60m_2nd_activity_id = Column(BIGINT)
    power_60m_3rd = Column(Integer)
    power_60m_3rd_activity_id = Column(BIGINT)
    longest_ride_1st = Column(Integer)
    longest_ride_1st_activity_id = Column(BIGINT)
    longest_ride_2nd = Column(Integer)
    longest_ride_2nd_activity_id = Column(BIGINT)
    longest_ride_3rd = Column(Integer)
    longest_ride_3rd_activity_id = Column(BIGINT)
    max_elevation_1st = Column(Integer)
    max_elevation_1st_activity_id = Column(BIGINT)
    max_elevation_2nd = Column(Integer)
    max_elevation_2nd_activity_id = Column(BIGINT)
    max_elevation_3rd = Column(Integer)
    max_elevation_3rd_activity_id = Column(BIGINT)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

# 流数据模型
class BaseStream(BaseModel):
    """基础流数据类"""
    original_size: int        = Field(...)
    resolution   : Resolution = Field(...)
    series_type  : SeriesType = Field(...)

class DistanceStream(BaseStream):
    data       : List[float] = Field(...)
    series_type: SeriesType  = Field(default=SeriesType.DISTANCE)

class TimeStream(BaseStream):
    data       : List[int]  = Field(...)
    series_type: SeriesType = Field(default=SeriesType.TIME)

class AltitudeStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class CadenceStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class HeartRateStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class SpeedStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class LatitudeStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class LongitudeStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class PowerStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class TemperatureStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class BestPowerStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.TIME)

class PowerHrRatioStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.TIME)

class TorqueStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class SPIStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class WBalanceStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.TIME)

class VAMStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class LeftRightBalanceStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class LeftTorqueEffectivenessStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class RightTorqueEffectivenessStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class LeftPedalSmoothnessStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class RightPedalSmoothnessStream(BaseStream):
    data: List[float] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class ElapsedTimeStream(BaseStream):
    data: List[int] = Field(...)
    series_type: SeriesType = Field(default=SeriesType.DISTANCE)

class StreamData(BaseModel):
    """完整的流数据集合，用于存储FIT文件中的所有原始数据"""
    position_lat               : List[float] = Field(default_factory=list)
    timestamp                  : List[int]   = Field(default_factory=list)
    position_long              : List[float] = Field(default_factory=list)
    enhanced_altitude          : List[float] = Field(default_factory=list)
    distance                   : List[float] = Field(default_factory=list)
    altitude                   : List[int]   = Field(default_factory=list)
    enhanced_speed             : List[float] = Field(default_factory=list)
    speed                      : List[float] = Field(default_factory=list)
    power                      : List[int]   = Field(default_factory=list)
    heart_rate                 : List[int]   = Field(default_factory=list)
    cadence                    : List[int]   = Field(default_factory=list)
    left_right_balance         : List[float] = Field(default_factory=list)
    left_torque_effectiveness  : List[float] = Field(default_factory=list)
    right_torque_effectiveness : List[float] = Field(default_factory=list)
    left_pedal_smoothness      : List[float] = Field(default_factory=list)
    right_pedal_smoothness     : List[float] = Field(default_factory=list)
    temperature                : List[float] = Field(default_factory=list)
    best_power                 : List[int]   = Field(default_factory=list)
    power_hr_ratio             : List[float] = Field(default_factory=list)
    elapsed_time               : List[int]   = Field(default_factory=list)
    torque                     : List[int]   = Field(default_factory=list)
    spi                        : List[float] = Field(default_factory=list)
    w_balance                  : List[float] = Field(default_factory=list)
    vam                        : List[int]   = Field(default_factory=list)
    
    def get_stream(
        self, 
        stream_type: str, 
        resolution: Resolution
    ) -> Optional[BaseStream]:
        available = self.get_available_streams()
        if stream_type not in available:
            raise ValueError('该流类型在当前活动中不可用，请通过 available_streams 接口获取可用流类型')

        if stream_type not in StreamData.model_fields:
            return None
        
        data = getattr(self, stream_type)
        if not data:
            return None
        
       
        resampled_data = self._resample_data(data, resolution)
        stream_classes = {
            'distance'                  : DistanceStream,
            'time'                      : TimeStream,
            'timestamp'                 : TimeStream,  # 添加 timestamp 字段映射
            'altitude'                  : AltitudeStream,
            'cadence'                   : CadenceStream,
            'heart_rate'                : HeartRateStream,
            'speed'                     : SpeedStream,
            'position_lat'              : LatitudeStream,
            'latitude'                  : LatitudeStream,
            'position_long'             : LongitudeStream,
            'longitude'                 : LongitudeStream,
            'power'                     : PowerStream,
            'temp'                      : TemperatureStream,
            'temperature'               : TemperatureStream,
            'left_right_balance'        : LeftRightBalanceStream,
            'left_torque_effectiveness' : LeftTorqueEffectivenessStream,
            'right_torque_effectiveness': RightTorqueEffectivenessStream,
            'left_pedal_smoothness'     : LeftPedalSmoothnessStream,
            'right_pedal_smoothness'    : RightPedalSmoothnessStream,
            'best_power'                : BestPowerStream,
            'power_hr_ratio'            : PowerHrRatioStream,
            'elapsed_time'              : ElapsedTimeStream,
            'torque'                    : TorqueStream,
            'spi'                       : SPIStream,
            'w_balance'                 : WBalanceStream,
            'vam'                       : VAMStream,
        }
        if stream_type in stream_classes:
            return stream_classes[stream_type](
                original_size = len(data) ,
                resolution    = resolution ,
                data          = resampled_data ,
                series_type   = stream_classes[stream_type].model_fields['series_type'].default
            )
        return None
    
    def _resample_data(
        self, 
        data: List[Union[int, float]], 
        resolution: Resolution
    ) -> List[Union[int, float]]:
        if not data:
            return []
        original_size = len(data)
        if resolution == Resolution.HIGH:
            return data
        elif resolution == Resolution.MEDIUM:
            target_size = max(1, int(original_size * 0.25))
            step        = max(1, original_size // target_size)
            result      = data[::step]
            return result[:target_size]
        elif resolution == Resolution.LOW:
            target_size = max(1, int(original_size * 0.05))
            step        = max(1, original_size // target_size)
            result      = data[::step]
            return result[:target_size]
    
    def get_available_streams(self) -> List[str]:
        available = []
        for field_name in StreamData.model_fields:
            data = getattr(self, field_name)
            # power_hr_ratio 需要特殊判断
            if field_name == 'power_hr_ratio':
                if (
                    getattr(self, 'power') and any(getattr(self, 'power')) and
                    getattr(self, 'heart_rate') and any(getattr(self, 'heart_rate')) and
                    data and any(x is not None for x in data)
                ):
                    available.append(field_name)
                continue
            # best_power 依赖 power
            if field_name == 'best_power':
                if getattr(self, 'power') and any(x != 0 for x in getattr(self, 'power')):
                    available.append(field_name)
                continue
            # SPI 和 torque 需要 power 和 cadence 都有
            if field_name in ('spi', 'torque'):
                if getattr(self, 'power') and any(getattr(self, 'power')) and getattr(self, 'cadence') and any(getattr(self, 'cadence')):
                    available.append(field_name)
                continue
            # w_balance 需要 power 数据
            if field_name == 'w_balance':
                if getattr(self, 'power') and any(x != 0 for x in getattr(self, 'power')):
                    available.append(field_name)
                continue
            # vam 需要 altitude 数据
            if field_name == 'vam':
                if getattr(self, 'altitude') and any(x != 0 for x in getattr(self, 'altitude')):
                    available.append(field_name)
                continue
            # 其它流只要有非 None/非 0 数据即可
            if data and any(x is not None and x != 0 for x in data):
                available.append(field_name)
        return available
