"""本地流心率指标装配（平均/最大/恢复）。"""
from typing import Dict, Any, Optional
from ...core.analytics.hr import (
    filter_hr_smooth,
    recovery_rate,
)


def compute_heartrate_info(stream_data: Dict[str, Any], power_data_present: bool, session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    hr_data = stream_data.get('heart_rate', [])
    if not hr_data:
        return None

    valid_hr = filter_hr_smooth(hr_data)
    if not valid_hr:
        return None

    result: Dict[str, Any] = {}
    if session_data and 'avg_heart_rate' in session_data:
        result['avg_heartrate'] = int(session_data['avg_heart_rate'])
    else:
        result['avg_heartrate'] = int(sum(valid_hr) / len(valid_hr))

    if session_data and 'max_heart_rate' in session_data:
        result['max_heartrate'] = int(session_data['max_heart_rate'])
    else:
        result['max_heartrate'] = int(max(valid_hr))

    if power_data_present:
        result['heartrate_recovery_rate'] = recovery_rate(hr_data)
    else:
        result['heartrate_recovery_rate'] = 0

    return result
