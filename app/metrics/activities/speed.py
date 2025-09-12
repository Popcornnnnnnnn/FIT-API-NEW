"""本地流速度指标装配（平均/最大/移动/总时长/暂停/滑行）。"""
from typing import Dict, Any, Optional
from ...core.analytics.time_utils import format_time


def compute_speed_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    speed_data = stream_data.get('speed', [])
    if not speed_data:
        return None
    power_data = stream_data.get('power', [])

    result: Dict[str, Any] = {}
    if session_data and 'avg_speed' in session_data:
        result['avg_speed'] = round(float(session_data['avg_speed']) * 3.6, 1)
    else:
        result['avg_speed'] = round(sum(speed_data) / len(speed_data), 1)

    if session_data and 'max_speed' in session_data:
        result['max_speed'] = round(float(session_data['max_speed']) * 3.6, 1)
    else:
        result['max_speed'] = round(max(speed_data), 1)

    if session_data and 'total_timer_time' in session_data:
        moving_time = int(session_data['total_timer_time'])
        result['moving_time'] = format_time(moving_time)
    else:
        moving_time = max(stream_data.get('elapsed_time', []) or [0])
        result['moving_time'] = format_time(moving_time)

    if session_data and 'total_elapsed_time' in session_data:
        total_time = int(session_data['total_elapsed_time'])
        result['total_time'] = format_time(total_time)
    else:
        total_time = max(stream_data.get('timestamp', []) or [moving_time])
        result['total_time'] = format_time(total_time)

    pause_seconds = (total_time or 0) - (moving_time or 0)
    result['pause_time'] = format_time(pause_seconds)

    def calculate_coasting_time() -> str:
        coasting_seconds = 0
        for i in range(len(speed_data)):
            is_coasting = False
            if speed_data[i] < 1.0:
                is_coasting = True
            if power_data and not is_coasting and power_data[i] < 10:
                is_coasting = True
            if is_coasting:
                coasting_seconds += 1
        return format_time(coasting_seconds)

    result['coasting_time'] = calculate_coasting_time()
    return result
