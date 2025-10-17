"""
FIT 文件解析器（基于 fitparse）：解析记录、计算衍生指标、返回 StreamData。
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
            'timestamp', 'position_lat', 'position_long', 'distance', 'enhanced_altitude', 'altitude', 'enhanced_speed', 'speed', 'power', 'heart_rate', 'cadence', 'left_right_balance', 'left_torque_effectiveness', 'right_torque_effectiveness', 'left_pedal_smoothness', 'right_pedal_smoothness', 'temperature', 'best_power', 'power_hr_ratio', 'elapsed_time', 'torque', 'spi', 'w_balance', 'vam'
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
        timestamp, position_lat, position_long, distance, enhanced_altitude, altitude, enhanced_speed, speed, power, heart_rate, cadence, left_right_balance, left_torque_effectiveness, right_torque_effectiveness, left_pedal_smoothness, right_pedal_smoothness, temperature = ([] for _ in range(17))
        
        start_time = None

        for record in fitfile.get_messages('record'):
            
            # 提取时间戳
            ts = record.get_value('timestamp')
            if ts is None:
                continue
                
            if start_time is None:
                start_time = ts
            
            # 计算相对时间戳（秒）
            relative_timestamp = int((ts - start_time).total_seconds())
            timestamp.append(relative_timestamp)
            
            # 提取distance
            dist = record.get_value('distance')
            distance.append(float(dist) if dist is not None else 0.0)

            # 提取其他字段
            # 海拔
            alt = record.get_value('enhanced_altitude')
            if alt is None:
                alt = record.get_value('altitude')
            altitude.append(int(round(float(alt))) if alt is not None else 0)
            enhanced_altitude.append(float(alt) if alt is not None else 0.0)
            
            # 踏频
            cad = record.get_value('cadence')
            cadence.append(int(cad) if cad is not None else 0)
            
            # 心率
            hr = record.get_value('heart_rate')
            heart_rate.append(int(hr) if hr is not None else 0)
            
            # 速度
            spd = record.get_value('enhanced_speed')
            if spd is None:
                spd = record.get_value('speed')
            if spd is not None:
                speed_kmh = float(spd) * 3.6
                speed.append(round(speed_kmh, 1))
                enhanced_speed.append(float(spd))
            else:
                speed.append(0.0)
                enhanced_speed.append(0.0)
            
            # GPS坐标
            lat = record.get_value('position_lat')
            position_lat.append(float(lat) if lat is not None else 0.0)
            
            lon = record.get_value('position_long')
            position_long.append(float(lon) if lon is not None else 0.0)
            
            # 功率
            pwr = record.get_value('power')
            power.append(int(pwr) if pwr is not None else 0)
            
            # 温度
            temp = record.get_value('temperature')
            temperature.append(float(temp) if temp is not None else 0.0)
            
            # 其他字段
            lrb = record.get_value('left_right_balance')
            left_right_balance.append(float(lrb) if lrb is not None else 0.0)
            
            lte = record.get_value('left_torque_effectiveness')
            left_torque_effectiveness.append(float(lte) if lte is not None else 0.0)
            
            rte = record.get_value('right_torque_effectiveness')
            right_torque_effectiveness.append(float(rte) if rte is not None else 0.0)
            
            lps = record.get_value('left_pedal_smoothness')
            left_pedal_smoothness.append(float(lps) if lps is not None else 0.0)
            
            rps = record.get_value('right_pedal_smoothness')
            right_pedal_smoothness.append(float(rps) if rps is not None else 0.0)

        # 计算elapsed_time
        timestamp_np = np.asarray(timestamp, dtype=np.int32)
        if timestamp_np.size:
            diffs = np.diff(timestamp_np, prepend=timestamp_np[0])
            diffs = np.clip(diffs, 0, 1)
            elapsed_time_np = np.cumsum(diffs)
            elapsed_time = elapsed_time_np.astype(int).tolist()
        else:
            elapsed_time = []

        # 计算衍生指标
        power_np = np.asarray(power, dtype=np.float64)
        heart_rate_np = np.asarray(heart_rate, dtype=np.float64)
        cadence_np = np.asarray(cadence, dtype=np.float64)

        with np.errstate(divide='ignore', invalid='ignore'):
            ratio = np.divide(power_np, heart_rate_np, out=np.zeros_like(power_np), where=(power_np > 0) & (heart_rate_np > 0))
        power_hr_ratio = np.round(ratio, 2).tolist()

        torque_np = np.zeros_like(power_np)
        mask = (power_np > 0) & (cadence_np > 0)
        torque_np[mask] = power_np[mask] / (cadence_np[mask] * 2 * np.pi / 60)
        torque = np.round(torque_np).astype(int).tolist()

        spi_np = np.zeros_like(power_np)
        spi_np[mask] = power_np[mask] / cadence_np[mask]
        spi = np.round(spi_np, 2).tolist()

        best_power = self._calculate_best_power_curve(power_np)
        w_balance  = self._calculate_w_balance(power_np.tolist(), athlete_info)
        vam        = self._calculate_vam(timestamp_np, np.asarray(altitude, dtype=np.float64))

        return StreamData(
            timestamp                  = timestamp,
            position_lat               = position_lat,
            position_long              = position_long,
            distance                   = distance,
            enhanced_altitude          = enhanced_altitude,
            altitude                   = altitude,
            enhanced_speed             = enhanced_speed,
            speed                      = speed,
            power                      = power,
            heart_rate                 = heart_rate,
            cadence                    = cadence,
            left_right_balance         = left_right_balance,
            left_torque_effectiveness  = left_torque_effectiveness,
            right_torque_effectiveness = right_torque_effectiveness,
            left_pedal_smoothness      = left_pedal_smoothness,
            right_pedal_smoothness     = right_pedal_smoothness,
            temperature                = temperature,
            best_power                 = best_power,
            power_hr_ratio             = power_hr_ratio,
            elapsed_time               = elapsed_time,
            torque                     = torque,
            spi                        = spi,
            w_balance                  = w_balance,
            vam                        = vam
        )

    def _calculate_best_power_curve(self, powers: np.ndarray) -> List[int]:
        max_duration = min(len(powers), 3600)
        if max_duration == 0:
            return []
        prefix = np.concatenate(([0.0], powers.cumsum()))
        best = np.zeros(max_duration, dtype=np.int32)
        for window in range(1, max_duration + 1):
            window_sums = prefix[window:] - prefix[:-window]
            best[window - 1] = int(round(window_sums.max() / window))
        return best.tolist()

    def _calculate_w_balance(
        self, 
        powers: list, 
        athlete_info: Optional[Dict[str, Any]] = None
    ) -> list:

        if not (athlete_info and athlete_info.get('ftp') and athlete_info.get('wj')):
            return [0.0] * len(powers)
        
        W_prime = athlete_info['wj']
        CP = int(athlete_info['ftp'])
        tau = 546.0
        balance = W_prime
        w_balance = []
        
        for p in powers:
            if p > CP * 1.05:
                balance -= (p - CP)
            elif p < CP * 0.95:
                recovery = (W_prime - balance) / tau
                balance += recovery
            
            balance = max(0.0, min(W_prime, balance))
            w_balance.append(round(balance / 1000, 1))
        
        return w_balance

    def _calculate_vam(
        self, 
        timestamps: np.ndarray, 
        altitudes: np.ndarray, 
        window_seconds: int = 50
    ) -> List[int]:
        if timestamps.size == 0 or altitudes.size == 0:
            return []
        start_times = timestamps - window_seconds
        idx = np.searchsorted(timestamps, start_times, side='left')
        idx = np.minimum(idx, np.arange(timestamps.size))
        delta_time = timestamps - timestamps[idx]
        delta_alt = altitudes - altitudes[idx]
        vam = np.zeros_like(delta_alt)
        valid = delta_time >= window_seconds * 0.5
        with np.errstate(divide='ignore', invalid='ignore'):
            vam[valid] = (delta_alt[valid] / (delta_time[valid] / 3600.0)) * 1.4
        vam = np.clip(vam, -5000, 5000)
        return np.round(vam).astype(int).tolist()
