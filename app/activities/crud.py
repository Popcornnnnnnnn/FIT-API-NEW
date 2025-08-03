"""
Activities模块的数据库操作函数

包含活动相关的数据库查询和操作。
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Tuple, Dict, Any
from ..streams.models import TbActivity, TbAthlete
from ..streams.crud import StreamCRUD
from ..utils import get_db
import numpy as np
from fitparse import FitFile
from io import BytesIO
import requests

# @ 这里没问题
def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    """
    根据活动ID获取活动和运动员信息

    这里返回的是对应 activity_id 的活动表（tb_activity）和其关联的运动员表（tb_athlete）的一整行内容，
    即分别为 TbActivity 和 TbAthlete 的完整 ORM 实例对象。
    你可以通过 activity.<字段名> 或 athlete.<字段名> 访问该行的所有字段。

    Args:
        db: 数据库会话
        activity_id: 活动ID

    Returns:
        Tuple[TbActivity, TbAthlete]: 活动和运动员的完整数据库行对象，如果不存在则返回None
    """
    # 查询活动信息（返回 tb_activity 的一整行内容）
    activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
    if not activity:
        return None

    # 查询运动员信息（返回 tb_athlete 的一整行内容）
    athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
    if not athlete:
        return None
    return activity, athlete


def get_activity_stream_data(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的流数据
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 流数据字典，如果不存在则返回None
    """
    try:
        # 查询活动信息
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return None
        
        
        # ! 这里有问题
        # 使用StreamCRUD获取流数据
        stream_crud = StreamCRUD()
        stream_data = stream_crud._get_or_parse_stream_data(db, activity)
        

        if not stream_data:
            return None
        
        # 转换为字典格式
        result = {}
        # 从模型类访问 model_fields，而不是从实例
        for field_name in stream_data.__class__.model_fields:
            if field_name not in ('timestamp',):  # 只排除timestamp，保留distance和elapsed_time
                data = getattr(stream_data, field_name)
                if data and any(x is not None and x != 0 for x in data):
                    result[field_name] = data
        return result
        
    except Exception as e:
        return None

def get_activity_overall_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的总体信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 活动总体信息，如果不存在则返回None
    """
    try:
        # 获取活动和运动员信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            return None
        
        activity, athlete = activity_athlete
        

        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None

        # 获取session段数据
        session_data = get_session_data(activity.upload_fit_url)
        
        # 计算各项指标
        result = {}
        
        # 1. 距离（千米，保留两位小数）
        if session_data and 'total_distance' in session_data:
            result['distance'] = round(session_data['total_distance'] / 1000, 2)
        elif 'distance' in stream_data and stream_data['distance']:
            max_distance = max(stream_data['distance'])
            result['distance'] = round(max_distance / 1000, 2)
        else:
            result['distance'] = 0.0

        # print(session_data)

        # 2. 移动时间（格式化字符串）
        if session_data and 'total_timer_time' in session_data:
            # 优先使用total_timer_time（不包括暂停时间）
            result['moving_time'] = format_time(session_data['total_timer_time'])
        elif session_data and 'total_elapsed_time' in session_data:
            # 如果没有total_timer_time，使用total_elapsed_time
            result['moving_time'] = format_time(session_data['total_elapsed_time'])
        elif 'elapsed_time' in stream_data and stream_data['elapsed_time']:
            max_elapsed = max(stream_data['elapsed_time'])
            result['moving_time'] = format_time(max_elapsed)
        else:
            result['moving_time'] = "00:00:00"
        
        # 3. 平均速度（千米每小时，保留一位小数）
        if result['distance'] > 0 and result['moving_time'] != "00:00:00":
            # 从格式化时间字符串解析秒数
            time_seconds = parse_time_to_seconds(result['moving_time'])
            if time_seconds > 0:
                result['average_speed'] = round(result['distance'] / (time_seconds / 3600), 1)
            else:
                result['average_speed'] = 0.0
        else:
            result['average_speed'] = 0.0
        
        # 4. 爬升海拔（米，保留整数）
        if 'total_ascent' in session_data and session_data['total_ascent']:
            elevation_gain = session_data['total_ascent']
            result['elevation_gain'] = int(elevation_gain)
        else:
            result['elevation_gain'] = 0
        
        # 5. 平均功率（瓦特，保留整数）
        if session_data and 'avg_power' in session_data:
            result['average_power'] = int(session_data['avg_power'])
        elif 'power' in stream_data and stream_data['power']:
            valid_powers = [p for p in stream_data['power'] if p is not None and p > 0]
            if valid_powers:
                result['average_power'] = int(sum(valid_powers) / len(valid_powers))
            else:
                result['average_power'] = None
        else:
            result['average_power'] = None
        
        # 6. 卡路里（估算，保留整数）
        # ! 这里有问题
        if session_data and 'total_calories' in session_data:
            result['calories'] = int(session_data['total_calories'])
        else:
            # 估算卡路里：基于功率、时间和体重
            avg_power = result['average_power'] if result['average_power'] is not None else 0
            result['calories'] = estimate_calories(
                avg_power, 
                parse_time_to_seconds(result['moving_time']), 
                athlete.weight if athlete.weight else 70
            )
        
        # 7. 训练负荷（无单位）
        if float(athlete.ftp) and float(athlete.ftp) > 0 and result['average_power'] is not None and result['average_power'] > 0:
            result['training_load'] = calculate_training_load(
                result['average_power'], 
                float(athlete.ftp), 
                parse_time_to_seconds(result['moving_time'])
            )
        else:
            result['training_load'] = 0
        
        # 8. 状态值
        result['status'] = None
        
        # 9. 平均心率（保留整数）
        if session_data and 'avg_heart_rate' in session_data:
            result['average_heart_rate'] = int(session_data['avg_heart_rate'])
        elif 'heart_rate' in stream_data and stream_data['heart_rate']:
            valid_hr = [hr for hr in stream_data['heart_rate'] if hr is not None and hr > 0]
            if valid_hr:
                result['average_heart_rate'] = int(sum(valid_hr) / len(valid_hr))
            else:
                result['average_heart_rate'] = None
        else:
            result['average_heart_rate'] = None
        
        # 10. 最高海拔（米，保留整数）
        if 'altitude' in stream_data and stream_data['altitude']:
            result['max_altitude'] = int(max(stream_data['altitude']))
        else:
            result['max_altitude'] = None
        
        return result
        
    except Exception as e:
        return None

def get_session_data(fit_url: str) -> Optional[Dict[str, Any]]:
    """
    从FIT文件中解析session段数据
    
    Args:
        fit_url: FIT文件URL
        
    Returns:
        Dict[str, Any]: session段数据，如果解析失败则返回None
    """
    try:
        # 下载FIT文件
        response = requests.get(fit_url)
        if response.status_code != 200:
            return None
        
        fit_data = response.content
        
        # 解析FIT文件
        fitfile = FitFile(BytesIO(fit_data))
        
        # 查找session消息
        for message in fitfile.get_messages('session'):
            session_data = {}
            
            # 提取session段中的字段
            fields = [
                'total_distance', 'total_elapsed_time', 'total_timer_time',
                'avg_power', 'max_power', 'avg_heart_rate', 'max_heart_rate',
                'total_calories', 'total_ascent', 'total_descent'
            ]
            
            for field in fields:
                value = message.get_value(field)
                if value is not None:
                    session_data[field] = value
            
            return session_data
        
        return None
        
    except Exception as e:
        return None

def format_time(seconds: int) -> str:
    """
    将秒数格式化为时间字符串
    
    Args:
        seconds: 秒数
        
    Returns:
        str: 格式化的时间字符串 (HH:MM:SS)
    """
    try:
        # 确保输入是整数
        if seconds is None:
            return "00:00:00"
        
        # 转换为整数，处理字符串或其他类型
        seconds = int(seconds)
        
        # 处理负数
        if seconds < 0:
            seconds = 0
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        # 如果转换失败，返回默认值
        return "00:00:00"

def parse_time_to_seconds(time_str: str) -> int:
    """
    将时间字符串解析为秒数
    
    Args:
        time_str: 时间字符串 (HH:MM:SS)
        
    Returns:
        int: 秒数
    """
    try:
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        return 0
    except:
        return 0

def calculate_elevation_gain(altitudes: list) -> float:
    """
    计算爬升海拔，参考VAM计算时的过滤和处理方法
    
    Args:
        altitudes: 海拔数据列表
        
    Returns:
        float: 爬升海拔（米）
    """
    if not altitudes or len(altitudes) < 2:
        return 0.0
    
    # 过滤异常值（参考VAM计算中的过滤方法）
    filtered_altitudes = []
    for i, alt in enumerate(altitudes):
        if alt is None:
            continue
        
        # 过滤异常值：超过5000米或低于-500米的设为None
        if alt > 5000 or alt < -500:
            continue
        
        # 如果与前一个有效值差异过大（超过100米），可能是异常值
        if filtered_altitudes and abs(alt - filtered_altitudes[-1]) > 100:
            continue
        
        filtered_altitudes.append(alt)
    
    if len(filtered_altitudes) < 2:
        return 0.0
    
    # 计算爬升
    elevation_gain = 0.0
    for i in range(1, len(filtered_altitudes)):
        diff = filtered_altitudes[i] - filtered_altitudes[i-1]
        if diff > 0:  # 只计算上升
            elevation_gain += diff
    
    return elevation_gain

def estimate_calories(avg_power: int, duration_seconds: int, weight_kg: float) -> int:
    """
    估算卡路里消耗
    
    Args:
        avg_power: 平均功率（瓦特）
        duration_seconds: 运动时长（秒）
        weight_kg: 体重（千克）
        
    Returns:
        int: 估算的卡路里消耗
    """
    if avg_power <= 0 or duration_seconds <= 0:
        return 0
    
    # 基于功率估算卡路里：功率 * 时间 * 效率系数
    # 假设人体效率约为25%，所以实际消耗的卡路里约为功率输出的4倍
    efficiency_factor = 4.0
    
    # 功率 * 时间（秒） * 效率系数 / 4184（1卡路里 = 4184焦耳）
    calories = (avg_power * duration_seconds * efficiency_factor) / 4184
    
    return int(calories)

def calculate_training_load(avg_power: int, ftp: float, duration_seconds: int) -> int:
    """
    计算训练负荷
    
    Args:
        avg_power: 平均功率（瓦特）
        ftp: 功能阈值功率（瓦特）
        duration_seconds: 运动时长（秒）
        
    Returns:
        float: 训练负荷
    """
    if avg_power <= 0 or ftp <= 0 or duration_seconds <= 0:
        return 0.0
    
    # 计算强度因子（IF）
    intensity_factor = avg_power / ftp
    
    # 计算训练负荷：IF^2 * 持续时间（小时）
    duration_hours = duration_seconds / 3600.0
    training_load = (intensity_factor ** 2) * duration_hours
    
    return int(training_load * 100)

def get_activity_power_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的功率相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 功率相关信息，如果不存在则返回None
    """
    try:
        # 获取活动和运动员信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            return None
        
        activity, athlete = activity_athlete
        
        # 获取FTP信息
        ftp = None
        if athlete.ftp:
            try:
                ftp = float(athlete.ftp)
            except (ValueError, TypeError):
                ftp = None
        
        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        # 获取session段数据
        session_data = get_session_data(activity.upload_fit_url)
        
        # 获取功率数据
        power_data = stream_data.get('power', [])
        if not power_data:
            return None
        
        # 过滤有效的功率数据（大于0）
        valid_powers = [p for p in power_data if p is not None and p > 0]
        if not valid_powers:
            return None
        
        result = {}
        
        # 1. 平均功率（保留整数）
        if session_data and 'avg_power' in session_data:
            result['average_power'] = int(session_data['avg_power'])
        else:
            result['average_power'] = int(sum(valid_powers) / len(valid_powers))
        
        # 2. 最大功率（保留整数）
        if session_data and 'max_power' in session_data:
            result['max_power'] = int(session_data['max_power'])
        else:
            result['max_power'] = int(max(valid_powers))
        
        # 3. 标准化功率（保留整数）
        result['normalized_power'] = calculate_normalized_power(valid_powers)
        
        # 4. 强度因子（保留两位小数）
        if ftp and ftp > 0:
            result['intensity_factor'] = round(result['normalized_power'] / ftp, 2)
        else:
            result['intensity_factor'] = None
        
        # 5. 总做功（保留整数）
        result['total_work'] = calculate_total_work(valid_powers)
        
        # 6. 变异性指数（保留两位小数）
        if result['average_power'] > 0:
            result['variability_index'] = round(result['normalized_power'] / result['average_power'], 2)
        else:
            result['variability_index'] = None
        
        # 7. 加权平均功率（返回None）
        result['weighted_average_power'] = None
        
        # 8. 高于FTP做功（保留整数）
        if ftp and ftp > 0:
            result['work_above_ftp'] = calculate_work_above_ftp(valid_powers, ftp)
        else:
            result['work_above_ftp'] = None
        
        # 9. 本次骑行的eFTP（返回None）
        result['eftp'] = None
        
        # 10. W平衡下降（保留一位小数）
        w_balance_data = stream_data.get('w_balance', [])
        if w_balance_data:
            result['w_balance_decline'] = calculate_w_balance_decline(w_balance_data)
        else:
            result['w_balance_decline'] = None
        
        return result
        
    except Exception as e:
        return None

def calculate_normalized_power(powers: list) -> int:
    """
    计算标准化功率
    
    Args:
        powers: 功率数据列表
        
    Returns:
        int: 标准化功率
    """
    if not powers:
        return 0
    
    # 使用30秒滚动平均
    window_size = 30
    rolling_averages = []
    
    for i in range(len(powers)):
        start_idx = max(0, i - window_size + 1)
        window_powers = powers[start_idx:i+1]
        avg_power = sum(window_powers) / len(window_powers)
        rolling_averages.append(avg_power)
    
    # 计算滚动平均的4次方平均值的4次方根
    fourth_powers = [avg ** 4 for avg in rolling_averages]
    mean_fourth_power = sum(fourth_powers) / len(fourth_powers)
    normalized_power = mean_fourth_power ** 0.25
    
    return int(normalized_power)

def calculate_total_work(powers: list) -> int:
    """
    计算总做功（千焦）
    
    Args:
        powers: 功率数据列表（假设每秒一个数据点）
        
    Returns:
        int: 总做功（千焦）
    """
    if not powers:
        return 0
    
    # 功率 * 时间 = 做功，假设每秒一个数据点
    total_work = sum(powers)  # 瓦特 * 秒 = 焦耳
    total_work_kj = total_work / 1000  # 转换为千焦
    
    return int(total_work_kj)

def calculate_work_above_ftp(powers: list, ftp: float) -> int:
    """
    计算高于FTP的做功
    
    Args:
        powers: 功率数据列表
        ftp: 功能阈值功率
        
    Returns:
        int: 高于FTP的做功（千焦）
    """
    if not powers or ftp <= 0:
        return 0
    
    work_above_ftp = 0
    for power in powers:
        if power > ftp:
            work_above_ftp += (power - ftp)  # (W - FTP) * 时间（假设1秒）
    
    work_above_ftp_kj = work_above_ftp / 1000  # 转换为千焦
    return int(work_above_ftp_kj)

def calculate_w_balance_decline(w_balance_data: list) -> float:
    """
    计算W平衡下降
    
    Args:
        w_balance_data: W平衡数据列表
        
    Returns:
        float: W平衡下降值（保留一位小数）
    """
    if not w_balance_data:
        return None
    
    # 过滤有效数据
    valid_w_balance = [w for w in w_balance_data if w is not None]
    if not valid_w_balance:
        return None
    
    # 初始值减去最小值
    initial_value = valid_w_balance[0]
    min_value = min(valid_w_balance)
    decline = initial_value - min_value
    
    return round(decline, 1) 