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
        elapsed_time = []
        prev_ts = None
        total_elapsed = 0
        
        for ts in timestamp:
            if prev_ts is None:
                elapsed_time.append(0)
            else:
                delta = ts - prev_ts
                total_elapsed += min(delta, 1)  # 最大间隔1秒
                elapsed_time.append(int(total_elapsed))
            prev_ts = ts

        # 计算衍生指标
        best_power     = self._calculate_best_power_curve(power)
        power_hr_ratio = [round(p/hr, 2) if p > 0 and hr > 0 else 0.0 for p, hr in zip(power, heart_rate)]
        torque         = [int(round(p/(c*2*3.1415926/60))) if p > 0 and c > 0 else 0 for p, c in zip(power, cadence)]
        spi            = [round(p/c, 2) if p > 0 and c > 0 else 0.0 for p, c in zip(power, cadence)]
        w_balance      = self._calculate_w_balance(power, athlete_info)
        vam            = self._calculate_vam(timestamp, altitude)

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

    def _calculate_best_power_curve(
        self, 
        powers: list
    ) -> list:
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
            best_powers.append(int(round(max_avg)))
        return best_powers

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
        timestamps: list, 
        altitudes: list, 
        window_seconds: int = 50
    ) -> list:
        vam = []

        for i in range(len(timestamps)):
            try:
                t_end = timestamps[i]
                t_start = t_end - window_seconds
                
                # 找到窗口起点
                idx_start = None
                for j in range(i, -1, -1):
                    if timestamps[j] <= t_start:
                        idx_start = j
                        break
                
                # 计算VAM
                if idx_start is None:
                    if i >= window_seconds:
                        delta_alt = altitudes[i] - altitudes[i-window_seconds]
                        delta_time = timestamps[i] - timestamps[i-window_seconds]
                        vam_value = delta_alt / (delta_time / 3600.0) if delta_time >= window_seconds * 0.7 else 0.0
                    else:
                        vam_value = 0.0
                elif idx_start == i:
                    vam_value = 0.0
                else:
                    delta_alt = altitudes[i] - altitudes[idx_start]
                    delta_time = timestamps[i] - timestamps[idx_start]
                    vam_value = delta_alt / (delta_time / 3600.0) if delta_time >= window_seconds * 0.5 else 0.0
                
                vam.append(int(round(vam_value * 1.4)))
            except Exception:
                vam.append(0)
        
        # 过滤异常值
        return [v if -5000 <= v <= 5000 else 0 for v in vam]
