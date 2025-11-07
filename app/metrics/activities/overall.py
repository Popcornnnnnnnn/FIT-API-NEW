"""本地流 Overall 指标装配（距离/时间/速度/爬升/功率/卡路里等）。"""
from typing import Dict, Any, Optional
from ...core.analytics.time_utils import format_time
from ...core.analytics.altitude import elevation_gain
from ...core.analytics.training import (
    calculate_training_load,
    estimate_calories_with_power,
    estimate_calories_with_heartrate,
    calculate_running_training_load
)


def compute_overall_info(
    stream_data: Dict[str, Any], 
    session_data: Optional[Dict[str, Any]], 
    athlete: Any, 
    activity_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not stream_data:
        return None
    res: Dict[str, Any] = {}
    # 距离
    distance = (
        float(session_data['total_distance']) if session_data and 'total_distance' in session_data
        else (max(stream_data.get('distance', []) or [0]))
    )
    res['distance'] = round(distance / 1000.0, 2) if distance else None

    # 移动时间
    moving_time = (
        int(session_data['total_timer_time']) if session_data and 'total_timer_time' in session_data
        else max(stream_data.get('elapsed_time', []) or [0])
    )
    res['moving_time'] = format_time(moving_time)

    # 平均速度
    avg_speed = (
        float(session_data['avg_speed']) * 3.6 if session_data and 'avg_speed' in session_data
        else (sum(stream_data.get('speed', [])) / len(stream_data.get('speed', []))) * 3.6 if stream_data.get('speed') else None
    )
    res['average_speed'] = round(avg_speed, 1) if avg_speed is not None else None

    # 爬升
    elevation = (
        int(session_data['total_ascent']) if session_data and session_data.get('total_ascent')
        else int(elevation_gain(stream_data.get('altitude', []))) if stream_data.get('altitude') else None
    )
    res['elevation_gain'] = elevation

    # 平均功率
    if session_data and 'avg_power' in session_data:
        res['avg_power'] = int(session_data['avg_power'])
    else:
        powers = [p for p in stream_data.get('power', []) if p and p > 0]
        res['avg_power'] = int(sum(powers) / len(powers)) if powers else None
    
    if session_data and 'avg_heart_rate' in session_data:
        res['avg_heartrate'] = int(session_data['avg_heart_rate'])
    elif 'heart_rate' in stream_data:
        hrs = stream_data.get('heart_rate') or []
        res['avg_heartrate'] = int(sum(hrs) / len(hrs)) if hrs else None
    else:
        res['avg_heartrate'] = None

        
    ftp = int(athlete.ftp)
    from ...core.analytics.pace import parse_pace_string
    from ...core.analytics.training import (
        calculate_training_load,
        calculate_running_training_load,
        calculate_heart_rate_training_load
    )
    if activity_type in ["run", "trail_run", "virtual_run"]:
        # 跑步活动：优先使用 rTSS（有阈值配速设置），其次使用心率负荷
        ft_pace = parse_pace_string(athlete.lactate_threshold_pace)
        if ft_pace: res['training_load'] = calculate_running_training_load(1000.0 / (res['average_speed'] / 3.6), ft_pace, res['moving_time']) if ft_pace and res.get('average_speed') else None
        else: res['training_load'] = calculate_heart_rate_training_load(res['avg_heartrate'], athlete.max_heartrate, athlete.threshold_heartrate, moving_time) if athlete.max_heartrate and athlete.threshold_heartrate and res.get('avg_heartrate') else None
    elif activity_type in ["ride", "virtualride", "ebikeride"]:
        # 骑行活动：优先使用 TSS(有功率数据)，其次使用心率负荷
        ftp = int(athlete.ftp)
        powers = [p for p in stream_data.get('power', []) if p and p > 0]
        if powers: res['training_load'] = calculate_training_load(res['avg_power'], ftp, moving_time) if ftp and res.get('avg_power') else None
        else: res['training_load'] = calculate_heart_rate_training_load(res['avg_heartrate'], athlete.max_heartrate, athlete.threshold_heartrate, res['moving_time']) if athlete.max_heartrate and athlete.threshold_heartrate and res.get('avg_heartrate') else None
            
    else:
        # 其他活动：默认都使用心率负荷
        res['training_load'] = calculate_heart_rate_training_load(res['avg_heartrate'], athlete.max_heartrate, athlete.threshold_heartrate, moving_time) if athlete.max_heartrate and athlete.threshold_heartrate and res.get('avg_heartrate') else None

    # ! status在上一级函数处理了
        
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
