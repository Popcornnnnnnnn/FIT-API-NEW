"""
区间分析器

实现功率和心率的区间分析功能。
"""

from typing import List, Dict, Any
from collections import defaultdict
import math

class ZoneAnalyzer:
    """区间分析器"""
    
    @staticmethod
    def format_time(seconds: int) -> str:
        """
        将秒数格式化为时间字符串
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化的时间字符串，如 "1:23:45" 或 "45s"
        """
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{minutes}:{remaining_seconds:02d}"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            remaining_seconds = seconds % 60
            return f"{hours}:{minutes:02d}:{remaining_seconds:02d}"
    
    @staticmethod
    def calculate_percentage(time_in_zone: int, total_time: int) -> str:
        """
        计算百分比
        
        Args:
            time_in_zone: 区间内时间（秒）
            total_time: 总时间（秒）
            
        Returns:
            str: 百分比字符串，如 "12.5%"
        """
        if total_time == 0:
            return "0.0%"
        percentage = (time_in_zone / total_time) * 100
        return f"{percentage:.1f}%"
    
    @staticmethod
    def analyze_power_zones(
        power_data: List[int], 
        ftp: int
    ) -> List[Dict[str, Any]]:
        if not power_data or ftp <= 0:
            return []

        zones = [
            (0, int(ftp * 0.55)),                # Zone 1: < 55% FTP
            (int(ftp * 0.55), int(ftp * 0.75)),  # Zone 2: 55-75% FTP
            (int(ftp * 0.75), int(ftp * 0.90)),  # Zone 3: 75-90% FTP
            (int(ftp * 0.90), int(ftp * 1.05)),  # Zone 4: 90-105% FTP
            (int(ftp * 1.05), int(ftp * 1.20)),  # Zone 5: 105-120% FTP
            (int(ftp * 1.20), int(ftp * 1.50)),  # Zone 6: 120-150% FTP
            (int(ftp * 1.50), float('inf')),     # Zone 7: >150% FTP
        ]
        
        # 统计每个区间的时间
        zone_times = defaultdict(int)
        valid_data_count = 0  # 有效数据点计数
        
        for power in power_data:
            if power is None or power <= 0:
                continue
            
            valid_data_count += 1
            
            # 找到功率所属的区间
            for i, (min_power, max_power) in enumerate(zones):
                if min_power <= power < max_power:
                    zone_times[i] += 1
                    break
            else:
                # 如果超过所有区间，归入最后一个区间
                if power >= zones[-1][1]:
                    zone_times[len(zones) - 1] += 1
        
        # 构建结果
        result = []
        for i, (min_power, max_power) in enumerate(zones):
            time_in_zone = zone_times[i]
            max_value = -1 if max_power == float('inf') else max_power
            result.append({
                "min": min_power,
                "max": max_value,
                "time": ZoneAnalyzer.format_time(time_in_zone),
                "percentage": ZoneAnalyzer.calculate_percentage(time_in_zone, valid_data_count)
            })
        
        return result
    
    @staticmethod
    def analyze_heartrate_zones(
        hr_data: List[int], 
        max_hr: int
    ) -> List[Dict[str, Any]]:
        if not hr_data or max_hr <= 0:
            return []
        
        zones = [
            (0, int(max_hr * 0.60)),      # Zone 1: < 60% Max HR
            (int(max_hr * 0.60), int(max_hr * 0.70)),  # Zone 2: 60-70% Max HR
            (int(max_hr * 0.70), int(max_hr * 0.80)),  # Zone 3: 70-80% Max HR
            (int(max_hr * 0.80), int(max_hr * 0.90)),  # Zone 4: 80-90% Max HR
            (int(max_hr * 0.90), max_hr),  # Zone 5: 90-100% Max HR
        ]
        
        zone_times = defaultdict(int)
        valid_data_count = 0 
        
        for hr in hr_data:
            if hr is None or hr <= 0:
                continue
            
            valid_data_count += 1
            for i, (min_hr, max_hr_zone) in enumerate(zones):
                if min_hr <= hr < max_hr_zone:
                    zone_times[i] += 1
                    break
            else:
                if hr >= zones[-1][1]:
                    zone_times[len(zones) - 1] += 1
        
        result = []
        for i, (min_hr, max_hr_zone) in enumerate(zones):
            time_in_zone = zone_times[i]
            result.append({
                "min": min_hr,
                "max": max_hr_zone,
                "time": ZoneAnalyzer.format_time(time_in_zone),
                "percentage": ZoneAnalyzer.calculate_percentage(time_in_zone, valid_data_count)
            })
        
        return result 