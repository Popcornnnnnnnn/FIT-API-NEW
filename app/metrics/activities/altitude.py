"""本地流海拔指标装配（爬升/下降/坡度/上下坡距离）。"""
from typing import Dict, Any, Optional
from ...core.analytics.altitude import elevation_gain, total_descent, max_grade_percent, uphill_downhill_distance_km


def compute_altitude_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    altitude_data = stream_data.get('altitude', [])
    distance_data = stream_data.get('distance', [])
    if not altitude_data:
        return None
    res: Dict[str, Any] = {}
    if session_data and session_data.get('total_ascent'):
        res['elevation_gain'] = int(session_data['total_ascent'])
    else:
        res['elevation_gain'] = int(elevation_gain(altitude_data))
    res  ['max_altitude']      = int(max(altitude_data)) if altitude_data else 0
    res  ['max_grade']         = max_grade_percent(altitude_data, distance_data)
    res  ['total_descent']     = int(session_data['total_descent']) if session_data and session_data.get('total_descent') else int(total_descent(altitude_data))
    res  ['min_altitude']      = int(min(altitude_data)) if altitude_data else 0
    up_km, down_km             = uphill_downhill_distance_km(altitude_data, distance_data)
    res  ['uphill_distance']   = up_km
    res  ['downhill_distance'] = down_km
    return res
