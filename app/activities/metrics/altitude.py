from typing import Dict, Any, Optional
from ...core.analytics.altitude import (
    elevation_gain,
    total_descent,
    max_grade_percent,
    uphill_downhill_distance_km,
)


def compute_altitude_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    altitude_data = stream_data.get('altitude', [])
    distance_data = stream_data.get('distance', [])
    if not altitude_data:
        return None

    result: Dict[str, Any] = {}
    if session_data and session_data.get('total_ascent'):
        result['elevation_gain'] = int(session_data['total_ascent'])
    else:
        result['elevation_gain'] = int(elevation_gain(altitude_data))

    result['max_altitude'] = int(max(altitude_data)) if altitude_data else 0
    result['max_grade'] = max_grade_percent(altitude_data, distance_data)

    if session_data and session_data.get('total_descent'):
        result['total_descent'] = int(session_data['total_descent'])
    else:
        result['total_descent'] = int(total_descent(altitude_data))

    result['min_altitude'] = int(min(altitude_data)) if altitude_data else 0
    up_km, down_km = uphill_downhill_distance_km(altitude_data, distance_data)
    result['uphill_distance'] = up_km
    result['downhill_distance'] = down_km
    return result

