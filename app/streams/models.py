"""
本文件定义了数据流相关的数据模型。

包含：
1. BaseStream - 基础流数据类
2. 具体的Stream类 - 继承BaseStream，包含具体的数据点
3. StreamData - 用于存储和访问FIT文件中的原始数据
"""

from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class Resolution(str, Enum):
    """数据分辨率枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class SeriesType(str, Enum):
    """系列类型枚举"""
    DISTANCE = "distance"
    TIME = "time"

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
    data: List[float] = Field(..., description="海拔数据点（米）")

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

class StreamData(BaseModel):
    """完整的流数据集合，用于存储FIT文件中的所有原始数据"""
    timestamp: List[int] = Field(default_factory=list, description="时间戳数据点")
    distance: List[float] = Field(default_factory=list, description="距离数据点")
    altitude: List[float] = Field(default_factory=list, description="海拔数据点")
    cadence: List[int] = Field(default_factory=list, description="踏频数据点")
    heart_rate: List[int] = Field(default_factory=list, description="心率数据点")
    speed: List[float] = Field(default_factory=list, description="速度数据点")
    latitude: List[float] = Field(default_factory=list, description="纬度数据点")
    longitude: List[float] = Field(default_factory=list, description="经度数据点")
    power: List[int] = Field(default_factory=list, description="功率数据点")
    temperature: List[float] = Field(default_factory=list, description="温度数据点")
    
    def get_stream(self, stream_type: str, resolution: Resolution = Resolution.HIGH) -> Optional[BaseStream]:
        """根据类型和分辨率获取流数据"""
        if stream_type not in StreamData.model_fields:
            return None
            
        data = getattr(self, stream_type)
        if not data:
            return None
            
        # 根据分辨率进行重采样
        resampled_data = self._resample_data(data, resolution)
        
        # 创建对应的Stream对象
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
            # 中等分辨率：保留50%的数据点
            step = max(1, original_size // (original_size // 2))
            return data[::step]
        elif resolution == Resolution.LOW:
            # 低分辨率：保留25%的数据点
            step = max(1, original_size // (original_size // 4))
            return data[::step]
        
        return data
    
    def get_available_streams(self) -> List[str]:
        """获取可用的流类型列表"""
        available = []
        for field_name in StreamData.model_fields:
            if field_name != 'timestamp' and getattr(self, field_name):
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