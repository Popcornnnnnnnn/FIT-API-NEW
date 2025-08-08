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
import numpy as np

class FitParser:
    """FIT文件解析器"""
    
    def __init__(self):
        """初始化解析器"""
        self.supported_fields = {
            'timestamp', 'distance', 'altitude', 'cadence', 
            'heartrate', 'speed', 'latitude', 'longitude', 
            'power', 'temp', 'best_power', 'power_hr_ratio',
            'torque', 'spi', 'w_balance', 'vam'
        }
    
    def parse_fit_file(
        self, 
        file_data: bytes, 
        athlete_info: Optional[Dict[str, Any]] = None
    ) -> StreamData:
        try:
            return self._parse_real_fit_data(file_data, athlete_info)
        except Exception as e:
            return StreamData() # 如果解析失败，返回空的StreamData
    
    def _parse_real_fit_data(
        self, 
        file_data: bytes, 
        athlete_info: Optional[Dict[str, Any]] = None
    ) -> StreamData:

        fitfile = FitFile(BytesIO(file_data))
        
        # 直接按顺序处理records数据
        timestamps = []
        distances = []
        altitudes = []
        cadences = []
        heartrates = []
        speeds = []
        latitudes = []
        longitudes = []
        powers = []
        temps = []
        elapsed_time = []
        
        start_time = None
        prev_timestamp = None
        total_elapsed = 0
        expected_interval = 1
        
        # INSERT_YOUR_CODE
        # 打印所有record中的字段（仅调试用，实际部署时请移除）
        for record in fitfile.get_messages('record'):
            print("record字段：", [field.name for field in record.fields])
            break  # 只打印第一个record的字段，避免输出过多

        for record in fitfile.get_messages('record'):
            # 提取时间戳
            timestamp = record.get_value('timestamp')
            if timestamp is None:
                continue
                
            if start_time is None:
                start_time = timestamp
            
            # 计算相对时间戳（秒）
            relative_timestamp = int((timestamp - start_time).total_seconds())
            
            # 提取distance
            distance = record.get_value('distance')
            if distance is None:
                continue
            
            # 计算elapsed_time
            if prev_timestamp is None:
                elapsed_time.append(0)
                prev_timestamp = relative_timestamp
            else:
                delta = relative_timestamp - prev_timestamp
                if delta > expected_interval * 2:
                    total_elapsed += expected_interval
                else:
                    total_elapsed += delta
                elapsed_time.append(int(total_elapsed))
                prev_timestamp = relative_timestamp
            
            # 添加基础数据
            timestamps.append(relative_timestamp)
            distances.append(float(distance))
            
            # 提取其他字段
            # 海拔
            altitude = record.get_value('enhanced_altitude')
            if altitude is None:
                altitude = record.get_value('altitude')
            altitudes.append(int(round(float(altitude))) if altitude is not None else 0)
            
            # 踏频
            cadence = record.get_value('cadence')
            cadences.append(int(cadence) if cadence is not None else 0)
            
            # 心率
            hr = record.get_value('heart_rate')
            heartrates.append(int(hr) if hr is not None else 0)
            
            # 速度
            speed = record.get_value('enhanced_speed')
            if speed is None:
                speed = record.get_value('speed')
            if speed is not None:
                speed_kmh = float(speed) * 3.6
                speeds.append(round(speed_kmh, 1))
            else:
                speeds.append(0.0)
            
            # GPS坐标
            lat = record.get_value('position_lat')
            latitudes.append(float(lat) if lat is not None else 0.0)
            
            lon = record.get_value('position_long')
            longitudes.append(float(lon) if lon is not None else 0.0)
            
            # 功率
            power = record.get_value('power')
            powers.append(int(power) if power is not None else 0)
            
            # 温度
            temp = record.get_value('temperature')
            temps.append(float(temp) if temp is not None else 0.0)


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
                best_powers.append(int(round(max_avg)))  # 保留到整数
            return best_powers

        best_powers = calculate_best_power_curve(powers)
    
        # 计算功率/心率比（现在所有字段都已对齐）
        power_hr_ratio = []
        for i in range(len(timestamps)):
            p = powers[i]
            hr = heartrates[i]
            if p > 0 and hr > 0:
                power_hr_ratio.append(round(float(p) / float(hr), 2))
            else:
                power_hr_ratio.append(0.0)
        
        # 计算扭矩（牛·米，整数）和 SPI（功率/踏频，保留两位小数）
        torque = []
        spi = []
        for i in range(len(timestamps)):
            p = powers[i]
            c = cadences[i]
            if p > 0 and c > 0:
                # 扭矩 = 功率 / (踏频 * 2 * pi / 60)
                t = p / (c * 2 * 3.1415926 / 60)
                torque.append(int(round(t)))
                spi.append(round(p / c, 2))
            else:
                torque.append(0)
                spi.append(0.0)
        
        # 计算W'平衡（W' Balance）
        w_balance = []
        if athlete_info and athlete_info.get('ftp') and athlete_info.get('wj'):
            W_prime = athlete_info['wj']  # 无氧储备
            CP = int(athlete_info['ftp'])      # 功能阈值功率
            
            dt = 1.0  # 时间间隔（秒）
            # 使用标准的 Skiba 模型参数
            tau = 546.0  # 恢复时间常数（秒），约9分钟
            
            balance = W_prime  # 初始储备
            
            for p in powers:
                # 简化计算：只有当功率明显高于 FTP 时才消耗 W'
                # 当功率低于 FTP 时，W' 会缓慢恢复
                if p > CP * 1.05:  # 功率超过 FTP 的 105% 时才消耗
                    # 消耗：线性损耗
                    balance -= (p - CP) * dt
                elif p < CP * 0.95:  # 功率低于 FTP 的 95% 时恢复
                    # 恢复：缓慢恢复
                    recovery = (W_prime - balance) * (dt / tau)
                    balance += recovery
                # 在 FTP 附近时，W' 基本保持不变
                
                balance = max(0.0, min(W_prime, balance))  # 限定范围
                w_balance.append(round(balance / 1000, 1))  # 转换为千焦，保留一位小数
        else:
            # 如果没有运动员信息或功率数据，填充为0
            w_balance = [0.0 for _ in timestamps]
        
        # ! 计算VAM（垂直海拔爬升，米/小时）- 不确定滑动窗口大小
        vam = []
        window_seconds = 50  # 50秒滑动窗口
        
        for i in range(len(timestamps)):
            try:
                # 找到窗口起点
                t_end = timestamps[i]
                t_start = t_end - window_seconds
                
                # 找到窗口内的起始点
                idx_start = None
                for j in range(i, -1, -1):
                    if timestamps[j] <= t_start:
                        idx_start = j
                        break
                
                # 计算VAM
                if idx_start is None:
                    # 对于数据不足的点，使用从开始到当前点的数据
                    if i >= window_seconds:
                        delta_alt = altitudes[i] - altitudes[i-window_seconds]
                        delta_time = timestamps[i] - timestamps[i-window_seconds]
                        if delta_time >= window_seconds * 0.7:  # 至少70%的时间窗口
                            vam_value = delta_alt / (delta_time / 3600.0)
                        else:
                            vam_value = 0.0
                    else:
                        vam_value = 0.0
                elif idx_start == i:
                    vam_value = 0.0
                else:
                    delta_alt = altitudes[i] - altitudes[idx_start]
                    delta_time = timestamps[i] - timestamps[idx_start]
                    if delta_time >= window_seconds * 0.5:  # 至少50%的时间窗口
                        vam_value = delta_alt / (delta_time / 3600.0)
                    else:
                        vam_value = 0.0
                
                vam.append(int(round(vam_value * 1.4)))  # 保留到整数，乘以1.4是经验值
            except Exception as e:
                vam.append(0)

        # 过滤VAM异常值，超过5000或低于-5000的设为0
        # !过滤突变值
        vam = [v if -5000 <= v <= 5000 else 0 for v in vam]

        # print(f"VAM最大值: {max(vam) if vam else None}, 最小值: {min(vam) if vam else None}")
        
        # 不再补零，保持原始数据长度
        return StreamData(
            timestamp=timestamps,
            distance=distances,
            altitude=altitudes,
            cadence=cadences,
            heartrate=heartrates,
            speed=speeds,
            latitude=latitudes,
            longitude=longitudes,
            power=powers,
            temp=temps,
            best_power=best_powers,
            power_hr_ratio=power_hr_ratio,
            elapsed_time=elapsed_time,
            torque=torque,
            spi=spi,
            w_balance=w_balance,
            vam=vam
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