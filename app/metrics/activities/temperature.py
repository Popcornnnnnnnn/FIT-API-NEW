"""本地流温度指标装配（最低/平均/最高）。"""
from typing import Dict, Any, Optional


def compute_temperature_info(stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    temperature = stream_data.get('temperature', [])
    if not temperature:
        return None
    return {
        'min_temp': int(round(min(temperature))),
        'avg_temp': int(round(sum(temperature) / len(temperature))),
        'max_temp': int(round(max(temperature))),
    }
