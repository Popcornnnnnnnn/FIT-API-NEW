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
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
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

# 数据库模型
class TbActivity(Base):
    """活动表模型"""
    __tablename__ = "tb_activity"
    
    id = Column(Integer, primary_key=True, index=True, comment="活动ID")
    athlete_id = Column(Integer, comment="运动员ID")
    upload_fit_url = Column(String(500), comment="FIT文件下载URL")

class TbAthlete(Base):
    """运动员表模型"""
    __tablename__ = "tb_athlete"
    
    id = Column(Integer, primary_key=True, index=True, comment="运动员ID")
    max_heartrate = Column(Integer, comment="最大心率")
    ftp = Column(Float, comment="功能阈值功率")
    w_balance = Column(Float, comment="W'平衡")
    weight = Column(Float, comment="体重(kg)")

# 流数据模型
class BaseStream(BaseModel):
    """基础流数据类"""
    original_size: int = Field(..., description="数据点总数")
    resolution: Resolution = Field(..., description="数据分辨率")
    series_type: SeriesType = Field(..., description="系列类型")

class DistanceStream(BaseStream):
    """距离流数据"""
    data: List[float] = Field(..., description="距离数据点（米）")
    series_type: SeriesType = Field(default=SeriesType.DISTANCE, description="系列类型")

class TimeStream(BaseStream):
    """时间流数据"""
    data: List[int] = Field(..., description="时间数据点（秒）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型")

class AltitudeStream(BaseStream):
    """海拔流数据"""
    data: List[int] = Field(..., description="海拔数据点（米，整数）")

class CadenceStream(BaseStream):
    """踏频流数据"""
    data: List[int] = Field(..., description="踏频数据点（RPM）")

class HeartRateStream(BaseStream):
    """心率流数据"""
    data: List[int] = Field(..., description="心率数据点（BPM）")

class SpeedStream(BaseStream):
    """速度流数据"""
    data: List[float] = Field(..., description="速度数据点（米/秒）")

class LatitudeStream(BaseStream):
    """纬度流数据"""
    data: List[float] = Field(..., description="纬度数据点")

class LongitudeStream(BaseStream):
    """经度流数据"""
    data: List[float] = Field(..., description="经度数据点")

class PowerStream(BaseStream):
    """功率流数据"""
    data: List[int] = Field(..., description="功率数据点（瓦特）")

class TemperatureStream(BaseStream):
    """温度流数据"""
    data: List[float] = Field(..., description="温度数据点（摄氏度）")

class BestPowerStream(BaseStream):
    """最佳功率曲线流数据（每秒区间最大均值）"""
    data: List[int] = Field(..., description="最佳功率曲线（每秒区间最大均值，整数）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，只允许time")

class PowerHrRatioStream(BaseStream):
    """功率/心率比流数据"""
    data: List[float] = Field(..., description="功率/心率比数据点")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，允许time和distance")

class TorqueStream(BaseStream):
    """扭矩流数据（单位：牛·米，整数）"""
    data: List[int] = Field(..., description="扭矩数据点（牛·米，整数）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，默认time")

class SPIStream(BaseStream):
    """SPI流数据（单位：瓦特/转，保留两位小数）"""
    data: List[float] = Field(..., description="SPI数据点（瓦特/转，保留两位小数）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，默认time")

class WBalanceStream(BaseStream):
    """W'平衡流数据（单位：千焦）"""
    data: List[float] = Field(..., description="W'平衡数据点（千焦，保留一位小数）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，默认time")

class VAMStream(BaseStream):
    """VAM流数据（单位：米/小时）"""
    data: List[int] = Field(..., description="VAM数据点（米/小时，整数）")
    series_type: SeriesType = Field(default=SeriesType.TIME, description="系列类型，默认time")

class StreamData(BaseModel):
    """完整的流数据集合，用于存储FIT文件中的所有原始数据"""
    timestamp: List[int] = Field(default_factory=list, description="时间戳数据点")
    distance: List[float] = Field(default_factory=list, description="距离数据点")
    altitude: List[int] = Field(default_factory=list, description="海拔数据点（整数）")
    cadence: List[int] = Field(default_factory=list, description="踏频数据点")
    heart_rate: List[int] = Field(default_factory=list, description="心率数据点")
    speed: List[float] = Field(default_factory=list, description="速度数据点（千米/小时，保留一位小数）")
    latitude: List[float] = Field(default_factory=list, description="纬度数据点")
    longitude: List[float] = Field(default_factory=list, description="经度数据点")
    power: List[int] = Field(default_factory=list, description="功率数据点")
    temperature: List[float] = Field(default_factory=list, description="温度数据点")
    best_power: List[int] = Field(default_factory=list, description="最佳功率曲线（每秒区间最大均值，整数）")
    power_hr_ratio: List[float] = Field(default_factory=list, description="功率/心率比数据点")
    elapsed_time: List[int] = Field(default_factory=list, description="去除暂停后的累计运动时间（秒）")
    torque: List[int] = Field(default_factory=list, description="扭矩数据点（牛·米，整数）")
    spi: List[float] = Field(default_factory=list, description="SPI数据点（瓦特/转，保留两位小数）")
    w_balance: List[float] = Field(default_factory=list, description="W'平衡数据点（千焦，保留一位小数）")
    vam: List[int] = Field(default_factory=list, description="VAM数据点（米/小时，整数）")
    
    def get_stream(self, stream_type: str, resolution: Resolution = Resolution.HIGH, series_type: SeriesType = SeriesType.TIME) -> Optional[BaseStream]:
        """根据类型和分辨率获取流数据"""

        

        available = self.get_available_streams()
        if stream_type not in available:
            raise ValueError('该流类型在当前活动中不可用，请通过 available_streams 接口获取可用流类型')

        if stream_type not in StreamData.model_fields:
            return None
        
        data = getattr(self, stream_type)
        if not data:
            return None
        
        # best_power 只能 series_type=time 且 resolution=high
        if stream_type == 'best_power':
            if series_type != SeriesType.TIME:
                raise ValueError('best_power 只允许 series_type=time')
            if resolution != Resolution.HIGH:
                raise ValueError('best_power 只允许 resolution=high')
            # time 从 1 开始
            x_axis = list(range(1, len(data) + 1))
            return BestPowerStream(
                original_size=len(data),
                resolution=resolution,
                data=data,  # y轴数据
                series_type=SeriesType.TIME
            )
        # 其它流（包括 power_hr_ratio）统一处理
        resampled_data = self._resample_data(data, resolution)
        stream_classes = {
            'distance': DistanceStream,
            'time': TimeStream,
            'altitude': AltitudeStream,
            'cadence': CadenceStream,
            'heart_rate': HeartRateStream,
            'speed': SpeedStream,
            'latitude': LatitudeStream,
            'longitude': LongitudeStream,
            'power': PowerStream,
            'temperature': TemperatureStream,
            'best_power': BestPowerStream,
            'power_hr_ratio': PowerHrRatioStream,
            'torque': TorqueStream,
            'spi': SPIStream,
            'w_balance': WBalanceStream,
            'vam': VAMStream,
        }
        if stream_type in stream_classes:
            return stream_classes[stream_type](
                original_size=len(data),
                resolution=resolution,
                data=resampled_data,
                series_type=SeriesType.DISTANCE if stream_type == 'distance' else SeriesType.TIME
            )
        return None
    
    def _resample_data(self, data: List[Union[int, float]], resolution: Resolution) -> List[Union[int, float]]:
        """根据分辨率重采样数据"""
        if not data:
            return []
        original_size = len(data)
        if resolution == Resolution.HIGH:
            return data
        elif resolution == Resolution.MEDIUM:
            # 采样25%
            target_size = max(1, int(original_size * 0.25))
            step = max(1, original_size // target_size)
            result = data[::step]
            # 确保结果长度不超过目标长度
            return result[:target_size]
        elif resolution == Resolution.LOW:
            # 采样5%
            target_size = max(1, int(original_size * 0.05))
            step = max(1, original_size // target_size)
            result = data[::step]
            # 确保结果长度不超过目标长度
            return result[:target_size]
        return data
    
    def get_available_streams(self) -> List[str]:
        """
        只返回当前活动实际有数据且非全 None/空的字段。
        power_hr_ratio 只有在 power 和 heart_rate 都有数据且 power_hr_ratio 至少有一个非 None 时才返回。
        """
        available = []
        for field_name in StreamData.model_fields:
            if field_name in ('timestamp', 'distance', 'elapsed_time'):
                continue
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
                if getattr(self, 'power') and any(getattr(self, 'power')) and data and any(x != 0 for x in data):
                    available.append(field_name)
                continue
            # SPI 和 torque 需要 power 和 cadence 都有
            if field_name in ('spi', 'torque'):
                if getattr(self, 'power') and any(getattr(self, 'power')) and getattr(self, 'cadence') and any(getattr(self, 'cadence')):
                    available.append(field_name)
                continue
            # w_balance 需要 power 数据
            if field_name == 'w_balance':
                if getattr(self, 'power') and any(getattr(self, 'power')) and data and any(x != 0 for x in data):
                    available.append(field_name)
                continue
            # vam 需要 altitude 数据
            if field_name == 'vam':
                if getattr(self, 'altitude') and any(getattr(self, 'altitude')) and data and any(x != 0 for x in data):
                    available.append(field_name)
                continue
            # 其它流只要有非 None/非 0 数据即可
            if data and any(x is not None and x != 0 for x in data):
                available.append(field_name)
        return available
    
    def get_summary_stats(self, stream_type: str) -> Optional[Dict[str, Any]]:
        """获取指定流类型的统计信息（为其他接口预留）"""
        if stream_type not in StreamData.model_fields:
            return None
            
        data = getattr(self, stream_type)
        if not data:
            return None
            
        # 过滤掉None和无效值
        valid_data = [x for x in data if x is not None]
        if not valid_data:
            return None
            
        return {
            'count': len(valid_data),
            'min': min(valid_data),
            'max': max(valid_data),
            'avg': sum(valid_data) / len(valid_data),
            'total': sum(valid_data) if stream_type in ['distance', 'time'] else None
        } 