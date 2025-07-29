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
            'power', 'temperature', 'best_power', 'power_hr_ratio'
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
            
            
            # 提取距离（米）
            try:
                distance = record.get_value('distance')
                if distance is not None:
                    distances.append(float(distance))
            except:
                pass
            
            # 提取海拔（米）- 优先使用enhanced_altitude
            altitude = record.get_value('enhanced_altitude')
            if altitude is None:
                altitude = record.get_value('altitude')
            if altitude is not None:
                altitudes.append(float(altitude))
            
            # 提取踏频（RPM）
            cadence = record.get_value('cadence')
            if cadence is not None:
                cadences.append(int(cadence))
            
            # 提取心率（BPM）
            hr = record.get_value('heart_rate')
            if hr is not None:
                heart_rates.append(int(hr))
            
            # 提取速度（米/秒）- 优先使用enhanced_speed
            speed = record.get_value('enhanced_speed')
            if speed is None:
                speed = record.get_value('speed')
            if speed is not None:
                speeds.append(float(speed))
            
            # 提取GPS坐标
            lat = record.get_value('position_lat')
            if lat is not None:
                latitudes.append(float(lat))
            lon = record.get_value('position_long')
            if lon is not None:
                longitudes.append(float(lon))
            
            # 提取功率（瓦特）
            power = record.get_value('power')
            if power is not None:
                powers.append(int(power))
            
            # 提取温度（摄氏度）
            temp = record.get_value('temperature')
            if temp is not None:
                temperatures.append(float(temp))

        # 计算最佳功率曲线
        def calculate_best_power_curve(powers: list) -> list:
            """
            计算最佳功率输出（Best Power Curve），每秒区间的最大均值
            返回列表 best_powers，其中 best_powers[0] = 1秒内最大平均功率，best_powers[1] = 2秒内最大平均功率，依此类推
            """
            n = len(powers)
            best_powers = []
            for window in range(1, n + 1):
                max_avg = 0
                if n >= window:
                    window_sum = sum(powers[:window])
                    max_avg = window_sum / window
                    for i in range(1, n - window + 1):
                        window_sum = window_sum - powers[i - 1] + powers[i + window - 1]
                        avg = window_sum / window
                        if avg > max_avg:
                            max_avg = avg
                best_powers.append(max_avg)
            return best_powers

        best_powers = calculate_best_power_curve(powers)
        
        # ! 计算功率/心率比（只有 power 和 heart_rate 都有值且长度一致时才计算，否则为空）
        # 计算功率/心率比，通过时间戳对齐，不要求长度一致
        power_hr_ratio = []
        if timestamps and powers and heart_rates:
            # 构建时间戳到功率和心率的映射
            power_map = {}
            hr_map = {}
            for idx, ts in enumerate(timestamps):
                if idx < len(powers):
                    power_map[ts] = powers[idx]
                if idx < len(heart_rates):
                    hr_map[ts] = heart_rates[idx]
            # 以所有时间戳为基准，计算比值
            for ts in timestamps:
                p = power_map.get(ts)
                hr = hr_map.get(ts)
                if (
                    p is not None and hr is not None and hr > 0
                    and p is not None and hr is not None
                ):
                    power_hr_ratio.append(round(float(p) / float(hr), 3))
                else:
                    # 避免 None，填充为 0.0
                    power_hr_ratio.append(0.0)
        else:
            power_hr_ratio = [0.0 for _ in timestamps]
        
        # 不再补零，保持原始数据长度
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
            temperature=temperatures,
            best_power=best_powers,
            power_hr_ratio=power_hr_ratio
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