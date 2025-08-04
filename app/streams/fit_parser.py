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
            'power', 'temperature', 'best_power', 'power_hr_ratio',
            'torque', 'spi', 'w_balance', 'vam'
        }
    
    def parse_fit_file(self, file_data: bytes, athlete_info: Optional[Dict[str, Any]] = None) -> StreamData:
        """
        解析FIT文件数据
        
        Args:
            file_data: FIT文件的二进制数据
            athlete_info: 运动员信息，包含ftp和wj字段，用于w_balance计算
            
        Returns:
            StreamData: 包含所有流数据的对象
        """
        try:
            # 使用fitparse库解析真实的FIT文件
            return self._parse_real_fit_data(file_data, athlete_info)
        except Exception as e:
            # 如果解析失败，返回空的StreamData
            return StreamData()
    
    def _parse_real_fit_data(self, file_data: bytes, athlete_info: Optional[Dict[str, Any]] = None) -> StreamData:
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
        heartrates = []
        speeds = []
        latitudes = []
        longitudes = []
        powers = []
        temperatures = []
        
        # 解析所有记录
        record_count = 0
        prev_timestamp = None
        elapsed_time = []
        total_elapsed = 0
        expected_interval = 1  # 采样间隔秒数，默认1秒，可根据实际情况调整

        # region DEBUG
        # 打印record字段中的名称
        # for record in fitfile.get_messages('record'):
        #     field_names = [field.name for field in record.fields]
        #     print("record字段名称:", field_names)
        #     break  # 只打印第一个record的字段名称即可
        # endregion


        # 打印 session（record）中的所有字段名称及其值，便于调试
        # for record in fitfile.get_messages('session'):
        #     print("session字段：")
        #     for field in record.fields:
        #         print(f"  {field.name}: {field.value}")

        for record in fitfile.get_messages('record'):
            record_count += 1
            
            # 提取时间戳
            try:
                timestamp = record.get_value('timestamp')
                if timestamp:
                    if len(timestamps) == 0:
                        start_time = timestamp
                        prev_timestamp = timestamp
                        total_elapsed = 0
                        elapsed_time.append(0)
                    else:
                        delta = (timestamp - prev_timestamp).total_seconds()
                        # 如果间隔大于2倍采样间隔，视为暂停
                        if delta > expected_interval * 2:
                            total_elapsed += expected_interval  # 只加一个采样间隔
                        else:
                            total_elapsed += delta
                        elapsed_time.append(int(total_elapsed))
                        prev_timestamp = timestamp
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
            
            # 提取海拔（米）- 优先使用enhanced_altitude，保留到整数
            altitude = record.get_value('enhanced_altitude')
            if altitude is None:
                altitude = record.get_value('altitude')
            if altitude is not None:
                altitudes.append(int(round(float(altitude))))
            
            # 提取踏频（RPM）
            cadence = record.get_value('cadence')
            if cadence is not None:
                cadences.append(int(cadence))
            
            # 提取心率（BPM）
            hr = record.get_value('heart_rate')
            if hr is not None:
                heartrates.append(int(hr))
            
            # 提取速度（米/秒）- 优先使用enhanced_speed，转换为千米/小时并保留一位小数
            speed = record.get_value('enhanced_speed')
            if speed is None:
                speed = record.get_value('speed')
            if speed is not None:
                # 转换为千米/小时：米/秒 * 3.6 = 千米/小时
                speed_kmh = float(speed) * 3.6
                speeds.append(round(speed_kmh, 1))
            
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
                best_powers.append(int(round(max_avg)))  # 保留到整数
            return best_powers

        best_powers = calculate_best_power_curve(powers)
    
        # ! 计算功率/心率比（只有 power 和 heartrate 都有值且长度一致时才计算，否则为空）
        # 计算功率/心率比，通过时间戳对齐，不要求长度一致
        power_hr_ratio = []
        if timestamps and powers and heartrates:
            # 构建时间戳到功率和心率的映射
            power_map = {}
            hr_map = {}
            for idx, ts in enumerate(timestamps):
                if idx < len(powers):
                    power_map[ts] = powers[idx]
                if idx < len(heartrates):
                    hr_map[ts] = heartrates[idx]
            # 以所有时间戳为基准，计算比值
            for ts in timestamps:
                p = power_map.get(ts)
                hr = hr_map.get(ts)
                if (
                    p is not None and hr is not None and hr > 0
                    and p is not None and hr is not None
                ):
                    power_hr_ratio.append(round(float(p) / float(hr), 2))
                else:
                    # 避免 None，填充为 0.0
                    power_hr_ratio.append(0.0)
        else:
            power_hr_ratio = [0.0 for _ in timestamps]
        
        # 计算扭矩（牛·米，整数）和 SPI（功率/踏频，保留两位小数），通过时间戳对齐，不要求 powers 和 cadences 长度一致，空的记录为 0
        torque = []
        spi = []
        if timestamps and powers and cadences:
            # 构建时间戳到功率和踏频的映射
            power_map = {}
            cadence_map = {}
            for idx, ts in enumerate(timestamps):
                if idx < len(powers):
                    power_map[ts] = powers[idx]
                if idx < len(cadences):
                    cadence_map[ts] = cadences[idx]
            for ts in timestamps:
                p = power_map.get(ts)
                c = cadence_map.get(ts)
                if (
                    p is not None and c is not None and c > 0
                ):
                    # 扭矩 = 功率 / (踏频 * 2 * pi / 60)
                    t = p / (c * 2 * 3.1415926 / 60)
                    torque.append(int(round(t)))
                    spi.append(round(p / c, 2))
                else:
                    torque.append(0)
                    spi.append(0.0)
        else:
            torque = [0 for _ in timestamps]
            spi = [0.0 for _ in timestamps]
        
        # 计算W'平衡（W' Balance）
        w_balance = []
        if athlete_info and powers and athlete_info.get('ftp') and athlete_info.get('wj'):
            W_prime = athlete_info['wj']  # 无氧储备
            CP = int(athlete_info['ftp'])      # 功能阈值功率
            
            dt = 1.0  # 时间间隔（秒）
            # 使用标准的 Skiba 模型参数
            tau = 546.0  # 恢复时间常数（秒），约9分钟
            
            balance = W_prime  # 初始储备
            
            for p in powers:
                if p is None:
                    w_balance.append(round(balance / 1000, 1))  # 转换为千焦，保留一位小数
                    continue
                
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
        
        # 计算VAM（垂直海拔爬升，米/小时）- 保留到整数
        vam = []
        if timestamps and altitudes:
            window_seconds = 5  # 5秒滑动窗口
            
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
                        if i >= window_seconds and i - window_seconds < len(altitudes) and i < len(altitudes):
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
                        if idx_start < len(altitudes) and i < len(altitudes):
                            delta_alt = altitudes[i] - altitudes[idx_start]
                            delta_time = timestamps[i] - timestamps[idx_start]
                            if delta_time >= window_seconds * 0.5:  # 至少50%的时间窗口
                                vam_value = delta_alt / (delta_time / 3600.0)
                            else:
                                vam_value = 0.0
                        else:
                            vam_value = 0.0
                    
                    vam.append(int(round(vam_value * 1.4)))  # 保留到整数，乘以1.4是经验值
                except Exception as e:
                    vam.append(0)
        else:
            # 如果没有海拔数据，填充为0
            vam = [0 for _ in timestamps]

        # 过滤VAM异常值，超过5000或低于-5000的设为0
        # !过滤突变值
        vam = [v if -5000 <= v <= 5000 else 0 for v in vam]
        
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
            temperature=temperatures,
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