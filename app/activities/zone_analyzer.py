"""
区间分析器

实现功率和心率的区间分析功能。
"""

from typing import List, Dict, Any
from ..core.analytics.time_utils import format_time
from ..core.analytics import zones as core_zones


class ZoneAnalyzer:
    """区间分析器 (兼容旧接口)，内部委托给 core.analytics.zones"""

    @staticmethod
    def format_time(seconds: int) -> str:
        return format_time(seconds) or "0s"

    @staticmethod
    def calculate_percentage(time_in_zone: int, total_time: int) -> str:
        if total_time == 0:
            return "0.0%"
        return f"{(time_in_zone / total_time) * 100:.1f}%"

    @staticmethod
    def analyze_power_zones(power_data: List[int], ftp: int) -> List[Dict[str, Any]]:
        return core_zones.analyze_power_zones(power_data, ftp)

    @staticmethod
    def analyze_heartrate_zones(hr_data: List[int], max_hr: int) -> List[Dict[str, Any]]:
        return core_zones.analyze_heartrate_zones(hr_data, max_hr)
