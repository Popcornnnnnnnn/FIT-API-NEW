from typing import Dict, Any, Optional
from ...core.analytics.time_utils import format_time
from ...core.analytics.altitude import elevation_gain
from ...core.analytics.training import calculate_training_load, estimate_calories_with_power, estimate_calories_with_heartrate


def compute_overall_info(
    stream_data: Dict[str, Any],
    session_data: Optional[Dict[str, Any]],
    athlete: Any,
) -> Optional[Dict[str, Any]]:
    if not stream_data:
        return None

    result: Dict[str, Any] = {}

    # distance (km)
    if session_data and 'total_distance' in session_data:
        result['distance'] = round(float(session_data['total_distance']) / 1000.0, 2)
    else:
        distance_stream = stream_data.get('distance', [])
        result['distance'] = round((max(distance_stream) / 1000.0), 2) if distance_stream else None

    # moving time
    if session_data and 'total_timer_time' in session_data:
        moving_time = int(session_data['total_timer_time'])
        result['moving_time'] = format_time(moving_time)
    else:
        moving_time = max(stream_data.get('elapsed_time', []) or [0])
        result['moving_time'] = format_time(moving_time)

    # average speed (km/h)
    if session_data and 'avg_speed' in session_data:
        result['average_speed'] = round(float(session_data['avg_speed']) * 3.6, 1)
    else:
        speeds = stream_data.get('speed', [])
        result['average_speed'] = round(sum(speeds) / len(speeds), 1) if speeds else None

    # elevation gain
    if session_data and 'total_ascent' in session_data and session_data['total_ascent']:
        result['elevation_gain'] = int(session_data['total_ascent'])
    else:
        alts = stream_data.get('altitude', [])
        result['elevation_gain'] = int(elevation_gain(alts)) if alts else None

    # avg power
    powers = stream_data.get('power', [])
    if session_data and 'avg_power' in session_data:
        result['avg_power'] = int(session_data['avg_power'])
    elif powers:
        valid = [p for p in powers if p is not None and p > 0]
        result['avg_power'] = int(sum(valid) / len(valid)) if valid else None
    else:
        result['avg_power'] = None

    # training load (TSS-like)
    try:
        ftp = int(athlete.ftp) if getattr(athlete, 'ftp', None) else 0
    except Exception:
        ftp = 0
    if ftp and result.get('avg_power') and moving_time:
        result['training_load'] = calculate_training_load(result['avg_power'], ftp, moving_time)
    else:
        result['training_load'] = None

    # status (ctl-atl) -> leave to caller to set if available
    result['status'] = None

    # avg heartrate
    if session_data and 'avg_heart_rate' in session_data:
        result['avg_heartrate'] = int(session_data['avg_heart_rate'])
    elif 'heart_rate' in stream_data:
        hrs = stream_data.get('heart_rate') or []
        result['avg_heartrate'] = int(sum(hrs) / len(hrs)) if hrs else None
    else:
        result['avg_heartrate'] = None

    # max altitude
    if session_data and 'max_altitude' in session_data:
        result['max_altitude'] = int(session_data['max_altitude'])
    else:
        alts = stream_data.get('altitude', [])
        result['max_altitude'] = int(max(alts)) if alts else None

    # calories
    if 'avg_power' in result and result['avg_power'] is not None:
        result['calories'] = estimate_calories_with_power(result['avg_power'], moving_time or 0, getattr(athlete, 'weight', 70) or 70)
    elif result.get('avg_heartrate') is not None:
        result['calories'] = estimate_calories_with_heartrate(result['avg_heartrate'], moving_time or 0, getattr(athlete, 'weight', 70) or 70)
    else:
        result['calories'] = None

    return result

