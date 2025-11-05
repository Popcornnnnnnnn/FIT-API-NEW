"""本地流 Overall 指标装配（距离/时间/速度/爬升/功率/卡路里等）。"""
from typing import Dict, Any, Optional
from ...core.analytics.time_utils import format_time
from ...core.analytics.altitude import elevation_gain
from ...core.analytics.training import (
    calculate_training_load,
    calculate_running_training_load,
    estimate_calories_with_power,
    estimate_calories_with_heartrate
)
from ...core.analytics.pace import (
    parse_pace_string
)


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
    
    # 注意：本地路径无法获取activity_data，暂时通过数据特征判断
    # 如果有功率数据，优先认为是骑行；否则如果有速度数据，可能是跑步
    has_power = res.get('avg_power') is not None or (powers and any(p for p in powers if p and p > 0))
    has_speed = 'speed' in stream_data and stream_data.get('speed') and any(s for s in stream_data.get('speed', []) if s and s > 0)
    is_running = not has_power and has_speed
    
    # 计算训练负荷
    try:
        ftp = int(athlete.ftp) if getattr(athlete, 'ftp', None) else 0
    except Exception:
        ftp = 0
    
    if is_running:
        # 跑步活动：使用 rTSS，直接使用原始平均配速计算
        # 获取阈值配速（lactate_threshold_pace字段）
        ft_pace = None
        if hasattr(athlete, 'lactate_threshold_pace') and athlete.lactate_threshold_pace:
            try:
                pace_val = athlete.lactate_threshold_pace
                if isinstance(pace_val, str):
                    ft_pace = parse_pace_string(pace_val)
                else:
                    # 如果不是字符串，直接转换为整数（假设已经是秒/公里）
                    ft_pace = int(pace_val)
            except (ValueError, AttributeError, TypeError):
                pass
        
        if ft_pace and ft_pace > 0 and moving_time:
            # 计算平均速度（m/s）
            avg_speed_ms = None
            if session_data and 'avg_speed' in session_data:
                # session_data中的avg_speed单位是 m/s
                avg_speed_ms = float(session_data['avg_speed'])
            else:
                speeds = stream_data.get('speed', [])
                if speeds:
                    valid_speeds = [s for s in speeds if s and s > 0]
                    if valid_speeds:
                        avg_speed = sum(valid_speeds) / len(valid_speeds)
                        # 检查速度单位：如果平均速度 > 10 m/s (36 km/h)，可能是 km/h，需要转换
                        if avg_speed > 10:  # 可能是 km/h
                            avg_speed_ms = avg_speed / 3.6
                        else:
                            avg_speed_ms = float(avg_speed)
            
            if avg_speed_ms and avg_speed_ms > 0:
                # 计算原始配速（秒/公里）
                raw_pace = 1000.0 / avg_speed_ms  # 配速 = 1000米 / 速度(m/s)
                # 使用原始配速计算训练负荷
                res['training_load'] = calculate_running_training_load(raw_pace, ft_pace, moving_time)
            else:
                res['training_load'] = None
        else:
            res['training_load'] = None
    else:
        # 骑车活动：使用现有的 TSS 计算
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
