"""
FIT文件解析器

用于解析FIT文件中的records数据，提取各种流数据。
使用fitparse库进行真实的FIT文件解析。
"""

import base64
import json
from typing import Dict, List, Optional, Any
from fitparse import FitFile
from io import BytesIO
from .models import StreamData, Resolution

class FitParser:
    """FIT文件解析器"""
    
    def __init__(self):
        """初始化解析器"""
        self.supported_fields = {
            'timestamp', 'distance', 'altitude', 'cadence', 
            'heart_rate', 'speed', 'latitude', 'longitude', 
            'power', 'temperature'
        }
    
    def parse_fit_file(self, file_data: bytes) -> StreamData:
        """
        解析FIT文件数据
        
        Args:
            file_data: FIT文件的二进制数据
            
        Returns:
            StreamData: 包含所有流数据的对象
        """
        try:
            # 使用fitparse库解析真实的FIT文件
            return self._parse_real_fit_data(file_data)
        except Exception as e:
            # 如果解析失败，返回空的StreamData
            print(f"FIT文件解析失败: {e}")
            return StreamData()
    
    def _parse_real_fit_data(self, file_data: bytes) -> StreamData:
        """
        解析真实的FIT文件数据
        使用fitparse库提取所有可用的流数据
        """
        # 创建FitFile对象
        fitfile = FitFile(BytesIO(file_data))
        
        # 初始化数据列表
        timestamps = []
        distances = []
        altitudes = []
        cadences = []
        heart_rates = []
        speeds = []
        latitudes = []
        longitudes = []
        powers = []
        temperatures = []
        
        # 解析所有记录
        record_count = 0
        for record in fitfile.get_messages('record'):
            record_count += 1
            
            # 提取时间戳
            try:
                timestamp = record.get_value('timestamp')
                if timestamp:
                    # 转换为相对时间戳（秒）
                    if len(timestamps) == 0:
                        start_time = timestamp
                    timestamps.append(int((timestamp - start_time).total_seconds()))
            except:
                pass
            
            # 只处理前几个记录进行调试
            if record_count <= 5:
                print(f"Record {record_count}: timestamp={len(timestamps)}, distance={len(distances)}, power={len(powers)}, cadence={len(cadences)}")
            
            # 提取距离（米）
            try:
                distance = record.get_value('distance')
                if distance is not None:
                    distances.append(float(distance))
            except:
                pass
            
            # 提取海拔（米）- 优先使用enhanced_altitude
            altitude = None
            if 'enhanced_altitude' in record:
                altitude = record.get_value('enhanced_altitude')
            elif 'altitude' in record:
                altitude = record.get_value('altitude')
            
            if altitude is not None:
                altitudes.append(float(altitude))
            
            # 提取踏频（RPM）
            try:
                cadence = record.get_value('cadence')
                if cadence is not None:
                    cadences.append(int(cadence))
            except:
                pass
            
            # 提取心率（BPM）
            if 'heart_rate' in record:
                hr = record.get_value('heart_rate')
                if hr is not None:
                    heart_rates.append(int(hr))
            
            # 提取速度（米/秒）- 优先使用enhanced_speed
            speed = None
            if 'enhanced_speed' in record:
                speed = record.get_value('enhanced_speed')
            elif 'speed' in record:
                speed = record.get_value('speed')
            
            if speed is not None:
                speeds.append(float(speed))
            
            # 提取GPS坐标
            if 'position_lat' in record:
                lat = record.get_value('position_lat')
                if lat is not None:
                    latitudes.append(float(lat))
            
            if 'position_long' in record:
                lon = record.get_value('position_long')
                if lon is not None:
                    longitudes.append(float(lon))
            
            # 提取功率（瓦特）
            try:
                power = record.get_value('power')
                if power is not None:
                    powers.append(int(power))
            except:
                pass
            
            # 提取温度（摄氏度）
            if 'temperature' in record:
                temp = record.get_value('temperature')
                if temp is not None:
                    temperatures.append(float(temp))
        
        # 确保所有列表长度一致（使用最长列表的长度）
        lengths = [len(timestamps), len(distances), len(altitudes), len(cadences),
                  len(heart_rates), len(speeds), len(latitudes), len(longitudes),
                  len(powers), len(temperatures)]
        max_len = max(lengths) if lengths else 0
        
        # 填充缺失的数据（使用默认值）
        timestamps.extend([0] * (max_len - len(timestamps)))
        distances.extend([0.0] * (max_len - len(distances)))
        altitudes.extend([0.0] * (max_len - len(altitudes)))
        cadences.extend([0] * (max_len - len(cadences)))
        heart_rates.extend([0] * (max_len - len(heart_rates)))
        speeds.extend([0.0] * (max_len - len(speeds)))
        latitudes.extend([0.0] * (max_len - len(latitudes)))
        longitudes.extend([0.0] * (max_len - len(longitudes)))
        powers.extend([0] * (max_len - len(powers)))
        temperatures.extend([0.0] * (max_len - len(temperatures)))
        
        return StreamData(
            timestamp=timestamps,
            distance=distances,
            altitude=altitudes,
            cadence=cadences,
            heart_rate=heart_rates,
            speed=speeds,
            latitude=latitudes,
            longitude=longitudes,
            power=powers,
            temperature=temperatures
        )
    
    def get_available_streams(self, stream_data: StreamData) -> List[str]:
        """获取可用的流类型列表"""
        return stream_data.get_available_streams()
    
    def get_stream(self, stream_data: StreamData, stream_type: str, resolution: Resolution = Resolution.HIGH):
        """获取指定类型的流数据"""
        return stream_data.get_stream(stream_type, resolution)
    
    def get_summary_stats(self, stream_data: StreamData, stream_type: str) -> Optional[Dict[str, Any]]:
        """获取指定流类型的统计信息"""
        return stream_data.get_summary_stats(stream_type) 