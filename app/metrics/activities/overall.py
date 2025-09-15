"""本地流 Overall 指标装配（距离/时间/速度/爬升/功率/卡路里等）。"""
from typing import Dict, Any, Optional
from ...core.analytics.time_utils import format_time
from ...core.analytics.altitude import elevation_gain
from ...core.analytics.training import calculate_training_load, estimate_calories_with_power, estimate_calories_with_heartrate


def compute_overall_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]], athlete: Any, status: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if not stream_data:
        return None
    res: Dict[str, Any] = {}
    if session_data and 'total_distance' in session_data:
        res['distance'] = round(float(session_data['total_distance']) / 1000.0, 2)
    else:
        d = stream_data.get('distance', [])
        res['distance'] = round((max(d) / 1000.0), 2) if d else None
    if session_data and 'total_timer_time' in session_data:
        moving_time = int(session_data['total_timer_time'])
        res['moving_time'] = format_time(moving_time)
    else:
        moving_time = max(stream_data.get('elapsed_time', []) or [0])
        res['moving_time'] = format_time(moving_time)
    if session_data and 'avg_speed' in session_data:
        res['average_speed'] = round(float(session_data['avg_speed']) * 3.6, 1)
    else:
        s = stream_data.get('speed', [])
        res['average_speed'] = round(sum(s) / len(s), 1) if s else None
    if session_data and session_data.get('total_ascent'):
        res['elevation_gain'] = int(session_data['total_ascent'])
    else:
        alts = stream_data.get('altitude', [])
        res['elevation_gain'] = int(elevation_gain(alts)) if alts else None
    powers = stream_data.get('power', [])
    if session_data and 'avg_power' in session_data:
        res['avg_power'] = int(session_data['avg_power'])
    elif powers:
        valid = [p for p in powers if p is not None and p > 0]
        res['avg_power'] = int(sum(valid) / len(valid)) if valid else None
    else:
        res['avg_power'] = None
    try:
        ftp = int(athlete.ftp) if getattr(athlete, 'ftp', None) else 0
    except Exception:
        ftp = 0
    if ftp and res.get('avg_power') and moving_time:
        res['training_load'] = calculate_training_load(res['avg_power'], ftp, moving_time)
    else:
        res['training_load'] = None
    res['status'] = status 
    if session_data and 'avg_heart_rate' in session_data:
        res['avg_heartrate'] = int(session_data['avg_heart_rate'])
    elif 'heart_rate' in stream_data:
        hrs = stream_data.get('heart_rate') or []
        res['avg_heartrate'] = int(sum(hrs) / len(hrs)) if hrs else None
    else:
        res['avg_heartrate'] = None
    if session_data and 'max_altitude' in session_data:
        res['max_altitude'] = int(session_data['max_altitude'])
    else:
        alts = stream_data.get('altitude', [])
        res['max_altitude'] = int(max(alts)) if alts else None
    if 'avg_power' in res and res['avg_power'] is not None:
        res['calories'] = estimate_calories_with_power(res['avg_power'], moving_time or 0, getattr(athlete, 'weight', 70) or 70)
    elif res.get('avg_heartrate') is not None:
        res['calories'] = estimate_calories_with_heartrate(res['avg_heartrate'], moving_time or 0, getattr(athlete, 'weight', 70) or 70)
    else:
        res['calories'] = None
    return res
