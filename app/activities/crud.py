"""
Activities模块的数据库操作函数

包含活动相关的数据库查询和操作。
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Tuple, Dict, Any, List
from ..streams.models import TbActivity, TbAthlete
from ..streams.crud import StreamCRUD
from ..utils import get_db
import numpy as np
from fitparse import FitFile
from io import BytesIO
import requests

def update_database_field(db: Session, table_class, record_id: int, field_name: str, value: Any) -> bool:
    """
    通用的数据库字段更新函数
    
    Args:
        db: 数据库会话
        table_class: 表模型类（如TbActivity, TbAthlete等）
        record_id: 记录ID
        field_name: 要更新的字段名
        value: 要更新的值
        
    Returns:
        bool: 更新是否成功
    """
    try:
        # 查询记录
        record = db.query(table_class).filter(table_class.id == record_id).first()
        if not record:
            return False
        
        # 检查字段是否存在
        if not hasattr(record, field_name):
            return False
        
        # 更新字段值
        setattr(record, field_name, value)
        
        # 提交更改
        db.commit()
        return True
        
    except Exception as e:
        # 回滚事务
        db.rollback()
        return False

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

def get_activity_stream_data(db: Session, activity_id: int) -> Optional[Dict[str, Any]]: # ! 重要函数
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
            result['avg_power'] = int(session_data['avg_power'])
        elif 'power' in stream_data and stream_data['power']:
            valid_powers = [p for p in stream_data['power'] if p is not None and p > 0]
            if valid_powers:
                result['avg_power'] = int(sum(valid_powers) / len(valid_powers))
            else:
                result['avg_power'] = None
        else:
            result['avg_power'] = None
        
        # 6. 卡路里（估算，保留整数）
        # ! 这里有问题
        if session_data and 'total_calories' in session_data:
            result['calories'] = int(session_data['total_calories'])
        else:
            # 估算卡路里：基于功率、时间和体重
            avg_power = result['avg_power'] if result['avg_power'] is not None else 0
            result['calories'] = estimate_calories(
                avg_power, 
                parse_time_to_seconds(result['moving_time']), 
                athlete.weight if athlete.weight else 70
            )
        
        # 7. 训练负荷（无单位）
        if float(athlete.ftp) and float(athlete.ftp) > 0 and result['avg_power'] is not None and result['avg_power'] > 0:
            result['training_load'] = calculate_and_save_training_load(
                db,
                activity_id,
                result['avg_power'], 
                float(athlete.ftp), 
                parse_time_to_seconds(result['moving_time'])
            )
        else:
            result['training_load'] = 0
        
        # 8. 状态值
        result['status'] = None
        
        # 9. 平均心率（保留整数）
        if session_data and 'avg_heart_rate' in session_data:
            result['avg_heartrate'] = int(session_data['avg_heart_rate'])
        elif 'heartrate' in stream_data and stream_data['heartrate']:
            valid_hr = [hr for hr in stream_data['heartrate'] if hr is not None and hr > 0]
            if valid_hr:
                result['avg_heartrate'] = int(sum(valid_hr) / len(valid_hr))
            else:
                result['avg_heartrate'] = None
        else:
            result['avg_heartrate'] = None
        
        # 10. 最高海拔（米，保留整数）
        if 'altitude' in stream_data and stream_data['altitude']:
            result['max_altitude'] = int(max(stream_data['altitude']))
        else:
            result['max_altitude'] = None
        
        return result
        
    except Exception as e:
        return None

def get_session_data(fit_url: str) -> Optional[Dict[str, Any]]: # ! 重要函数
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
                'total_calories', 'total_ascent', 'total_descent',
                'avg_cadence', 'max_cadence', 'left_right_balance',
                'left_torque_effectiveness', 'right_torque_effectiveness',
                'left_pedal_smoothness', 'right_pedal_smoothness',
                'avg_speed', 'max_speed', 'avg_temperature', 'max_temperature', 'min_temperature',
                'normalized_power', "training_stress_score","avg_speed", "max_speed"
                "intensity_factor"
            ]
            
            for field in fields:
                value = message.get_value(field)
                if value is not None:
                    session_data[field] = value
            
            return session_data
        
        return None
        
    except Exception as e:
        return None

def get_cadence_fields_from_records(fit_url: str) -> Optional[Dict[str, Any]]:
    """
    从FIT文件的records中提取踏频相关字段
    
    Args:
        fit_url: FIT文件URL
        
    Returns:
        Dict[str, Any]: 踏频相关字段数据，如果解析失败则返回None
    """
    try:
        # 下载FIT文件
        response = requests.get(fit_url)
        if response.status_code != 200:
            return None
        
        fit_data = response.content
        
        # 解析FIT文件
        fitfile = FitFile(BytesIO(fit_data))
        
        # 踏频相关字段
        cadence_fields = {
            'left_right_balance': [],
            'left_torque_effectiveness': [],
            'right_torque_effectiveness': [],
            'left_pedal_smoothness': [],
            'right_pedal_smoothness': []
        }
        
        # 从records中提取踏频相关字段
        for record in fitfile.get_messages('record'):
            for field_name in cadence_fields.keys():
                value = record.get_value(field_name)
                if value is not None:
                    cadence_fields[field_name].append(float(value))
        
        # 计算平均值（如果有数据的话）
        result = {}
        for field_name, values in cadence_fields.items():
            if values:
                result[field_name] = sum(values) / len(values)
        
        return result if result else None
        
    except Exception as e:
        return None

def get_all_left_right_balance_values(fit_url: str) -> Optional[List[int]]:
    """
    从FIT文件的records中获取所有left_right_balance值
    
    Args:
        fit_url: FIT文件URL
        
    Returns:
        List[int]: 所有left_right_balance值列表，如果解析失败则返回None
    """
    try:
        # 下载FIT文件
        response = requests.get(fit_url)
        if response.status_code != 200:
            return None
        
        fit_data = response.content
        
        # 解析FIT文件
        fitfile = FitFile(BytesIO(fit_data))
        
        # 从records中提取所有left_right_balance值
        left_right_balance_values = []
        
        for record in fitfile.get_messages('record'):
            value = record.get_value('left_right_balance')
            if value is not None:
                left_right_balance_values.append(int(value))
        
        return left_right_balance_values if left_right_balance_values else None
        
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
        int: 训练负荷
    """
    if avg_power <= 0 or ftp <= 0 or duration_seconds <= 0:
        return 0
    
    # 计算强度因子（IF）
    intensity_factor = avg_power / ftp
    
    # 计算训练负荷：IF^2 * 持续时间（小时）
    duration_hours = duration_seconds / 3600.0
    training_load = (intensity_factor ** 2) * duration_hours
    
    return int(training_load * 100)

def calculate_and_save_training_load(db: Session, activity_id: int, avg_power: int, ftp: float, duration_seconds: int) -> int:
    """
    计算训练负荷并保存到数据库
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        avg_power: 平均功率（瓦特）
        ftp: 功能阈值功率（瓦特）
        duration_seconds: 运动时长（秒）
        
    Returns:
        int: 训练负荷值
    """
    # 计算训练负荷
    training_load = calculate_training_load(avg_power, ftp, duration_seconds)
    
    # 保存到数据库
    update_success = update_database_field(db, TbActivity, activity_id, 'training_stress_score', training_load)
    
    if not update_success:
        # 如果更新失败，记录错误但不影响返回值
        print(f"警告：无法将训练负荷值 {training_load} 保存到活动 {activity_id} 的数据库")
    
    return training_load

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
            result['avg_power'] = int(session_data['avg_power'])
        else:
            result['avg_power'] = int(sum(valid_powers) / len(valid_powers))
        
        # 2. 最大功率（保留整数）
        if session_data and 'max_power' in session_data:
            result['max_power'] = int(session_data['max_power'])
        else:
            result['max_power'] = int(max(valid_powers))
        
        # 3. 标准化功率（保留整数）
        if session_data and 'normalized_power' in session_data:
            result['normalized_power'] = int(session_data['normalized_power'])
        else:
            result['normalized_power'] = calculate_normalized_power(valid_powers)
        
        # 4. 强度因子（保留两位小数）
        if session_data and 'intensity_factor' in session_data:
            result['intensity_factor'] = round(session_data['intensity_factor'], 2)
        else:
            if ftp and ftp > 0:
                result['intensity_factor'] = round(result['normalized_power'] / ftp, 2)
            else:
                result['intensity_factor'] = None
        
        # 5. 总做功（保留整数）
        result['total_work'] = calculate_total_work(valid_powers)
        
        # 6. 变异性指数（保留两位小数）
        if result['avg_power'] > 0:
            result['variability_index'] = round(result['normalized_power'] / result['avg_power'], 2)
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

def get_activity_heartrate_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的心率相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 心率相关信息，如果不存在则返回None
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
        
        # 获取心率数据
        heartrate_data = stream_data.get('heartrate', [])
        if not heartrate_data:
            return None
        
        # 过滤有效的心率数据（大于0）
        valid_hr = [hr for hr in heartrate_data if hr is not None and hr > 0]
        if not valid_hr:
            return None
        
        result = {}
        
        # 1. 平均心率（保留整数）
        if session_data and 'avg_heart_rate' in session_data:
            result['avg_heartrate'] = int(session_data['avg_heart_rate'])
        else:
            result['avg_heartrate'] = int(sum(valid_hr) / len(valid_hr))
        
        # 2. 最大心率（保留整数）
        if session_data and 'max_heart_rate' in session_data:
            result['max_heartrate'] = int(session_data['max_heart_rate'])
        else:
            result['max_heartrate'] = int(max(valid_hr))
        
        # 3. 心率恢复速率（返回None）
        result['heartrate_recovery_rate'] = None
        
        # 4. 心率滞后（返回None）
        result['heartrate_lag'] = None
        
        # 5. 效率指数（保留两位小数）
        result['efficiency_index'] = calculate_efficiency_index(stream_data, athlete.ftp)
        
        # 6. 解耦率（百分比，保留一位小数）
        result['decoupling_rate'] = calculate_decoupling_rate(stream_data)
        
        return result
        
    except Exception as e:
        return None

def calculate_efficiency_index(stream_data: Dict[str, Any], ftp: str) -> float:
    """
    计算效率指数
    
    Args:
        stream_data: 流数据
        ftp: FTP值（字符串类型）
        
    Returns:
        float: 效率指数（保留两位小数）
    """
    try:
        # 获取功率和心率数据
        power_data = stream_data.get('power', [])
        heartrate_data = stream_data.get('heartrate', [])
        
        if not power_data or not heartrate_data:
            return 0.0
        
        # 过滤有效数据
        valid_powers = [p for p in power_data if p is not None and p > 0]
        valid_hr = [hr for hr in heartrate_data if hr is not None and hr > 0]
        
        if not valid_powers or not valid_hr:
            return 0.0
        
        # 计算平均功率和平均心率
        avg_power = sum(valid_powers) / len(valid_powers)
        avg_hr = sum(valid_hr) / len(valid_hr)
        
        # 效率指数 = 平均功率 / 平均心率
        if avg_hr > 0:
            efficiency_index = avg_power / avg_hr
            return round(efficiency_index, 2)
        
        return 0.0
        
    except Exception as e:
        return 0.0

def calculate_decoupling_rate(stream_data: Dict[str, Any]) -> str:
    """
    计算解耦率
    
    Args:
        stream_data: 流数据
        
    Returns:
        str: 解耦率（百分比，保留一位小数，带%符号）
    """
    try:
        # 获取功率和心率数据
        power_data = stream_data.get('power', [])
        heartrate_data = stream_data.get('heartrate', [])
        
        if not power_data or not heartrate_data:
            return "0.0%"
        
        # 过滤有效数据
        valid_powers = [p for p in power_data if p is not None and p > 0]
        valid_hr = [hr for hr in heartrate_data if hr is not None and hr > 0]
        
        if not valid_powers or not valid_hr:
            return "0.0%"
        
        # 确保数据长度一致，取较短的长度
        min_length = min(len(valid_powers), len(valid_hr))
        if min_length < 10:  # 至少需要10个数据点
            return "0.0%"
        
        # 截取相同长度的数据
        powers = valid_powers[:min_length]
        heart_rates = valid_hr[:min_length]
        
        # 将数据分为前半部分和后半部分
        mid_point = min_length // 2
        
        first_half_powers = powers[:mid_point]
        first_half_hr = heart_rates[:mid_point]
        second_half_powers = powers[mid_point:]
        second_half_hr = heart_rates[mid_point:]
        
        # 计算前半部分的功率/心率比
        first_half_ratio = 0.0
        if first_half_hr and any(hr > 0 for hr in first_half_hr):
            first_half_avg_power = sum(first_half_powers) / len(first_half_powers)
            first_half_avg_hr = sum(first_half_hr) / len(first_half_hr)
            if first_half_avg_hr > 0:
                first_half_ratio = first_half_avg_power / first_half_avg_hr
        
        # 计算后半部分的功率/心率比
        second_half_ratio = 0.0
        if second_half_hr and any(hr > 0 for hr in second_half_hr):
            second_half_avg_power = sum(second_half_powers) / len(second_half_powers)
            second_half_avg_hr = sum(second_half_hr) / len(second_half_hr)
            if second_half_avg_hr > 0:
                second_half_ratio = second_half_avg_power / second_half_avg_hr
        
        # 计算解耦率：前半部分功率/心率 - 后半部分功率/心率
        if first_half_ratio > 0 and second_half_ratio > 0:
            decoupling_rate = first_half_ratio - second_half_ratio
            # 转换为百分比
            decoupling_percentage = (decoupling_rate / first_half_ratio) * 100
            return f"{round(decoupling_percentage, 1)}%"
        
        return "0.0%"
        
    except Exception as e:
        return "0.0%" 

def get_activity_cadence_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的踏频相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 踏频相关信息，如果不存在则返回None
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
        
        # 获取踏频数据
        cadence_data = stream_data.get('cadence', [])
        if not cadence_data:
            return None
        
        # 过滤有效的踏频数据（大于0）
        valid_cadences = [c for c in cadence_data if c is not None and c > 0]
        if not valid_cadences:
            return None
        
        result = {}
        
        # 1. 平均踏频（整数）- 优先从session中获取
        if session_data and 'avg_cadence' in session_data:
            result['avg_cadence'] = int(session_data['avg_cadence'])
        else:
            result['avg_cadence'] = int(sum(valid_cadences) / len(valid_cadences))
        
        # 2. 最大踏频（整数）- 优先从session中获取
        if session_data and 'max_cadence' in session_data:
            result['max_cadence'] = int(session_data['max_cadence'])
        else:
            result['max_cadence'] = int(max(valid_cadences))
        
        # 3. 左右平衡（优先从session中获取，没有则从records中计算）
        result['left_right_balance'] = get_left_right_balance(session_data, stream_data, activity.upload_fit_url)
        
        # 4. 左右扭矩效率
        result['left_torque_effectiveness'] = get_torque_effectiveness(session_data, stream_data, 'left', activity.upload_fit_url)
        result['right_torque_effectiveness'] = get_torque_effectiveness(session_data, stream_data, 'right', activity.upload_fit_url)
        
        # 5. 左右踏板平顺度
        result['left_pedal_smoothness'] = get_pedal_smoothness(session_data, stream_data, 'left', activity.upload_fit_url)
        result['right_pedal_smoothness'] = get_pedal_smoothness(session_data, stream_data, 'right', activity.upload_fit_url)
        
        # 6. 踏板总行程数（计算总踩踏次数）
        result['total_strokes'] = calculate_total_strokes(valid_cadences)
        
        return result
        
    except Exception as e:
        return None

def get_left_right_balance(session_data: Optional[Dict[str, Any]], stream_data: Dict[str, Any], fit_url: str) -> Optional[Dict[str, int]]:
    """
    获取左右平衡数据
    
    Args:
        session_data: session段数据
        stream_data: 流数据
        fit_url: FIT文件URL
        
    Returns:
        Optional[Dict[str, int]]: 左右平衡值，格式为{"left": 49, "right": 51}，如果没有则返回None
    """
    def parse_left_right(value: int) -> Optional[Tuple[int, int]]:
        """解析左右平衡值"""
        try:
            # 正常的record值解析
            side_flag = value & 0x01
            percent = value >> 1
            if side_flag == 1:
                right = percent
                left = 100 - percent
            else:
                left = percent
                right = 100 - percent
            return (left, right)
        except (ValueError, TypeError):
            return None
    
    # 直接从records中获取
    all_values = get_all_left_right_balance_values(fit_url)
    if all_values:
        parsed_values = []
        for value in all_values:
            parsed = parse_left_right(value)
            if parsed:
                parsed_values.append(parsed)
        
        if parsed_values:
            left_values = [lr[0] for lr in parsed_values]
            right_values = [lr[1] for lr in parsed_values]
            
            avg_left = int(round(sum(left_values) / len(left_values)))
            avg_right = int(round(sum(right_values) / len(right_values)))
            
            return {"left": avg_left, "right": avg_right}
    
    return None

def get_torque_effectiveness(session_data: Optional[Dict[str, Any]], stream_data: Dict[str, Any], side: str, fit_url: str) -> Optional[float]:
    """
    获取扭矩效率数据
    
    Args:
        session_data: session段数据
        stream_data: 流数据
        side: 左右侧（'left'或'right'）
        fit_url: FIT文件URL
        
    Returns:
        Optional[float]: 扭矩效率值，如果没有则返回None
    """
    # 优先从session中获取
    if session_data:
        field_name = f'{side}_torque_effectiveness'
        if field_name in session_data:
            return float(session_data[field_name])
    
    # 从records中获取
    records_data = get_cadence_fields_from_records(fit_url)
    if records_data:
        field_name = f'{side}_torque_effectiveness'
        if field_name in records_data:
            return records_data[field_name]
    
    return None

def get_pedal_smoothness(session_data: Optional[Dict[str, Any]], stream_data: Dict[str, Any], side: str, fit_url: str) -> Optional[float]:
    """
    获取踏板平顺度数据
    
    Args:
        session_data: session段数据
        stream_data: 流数据
        side: 左右侧（'left'或'right'）
        fit_url: FIT文件URL
        
    Returns:
        Optional[float]: 踏板平顺度值，如果没有则返回None
    """
    # 优先从session中获取
    if session_data:
        field_name = f'{side}_pedal_smoothness'
        if field_name in session_data:
            return float(session_data[field_name])
    
    # 从records中获取
    records_data = get_cadence_fields_from_records(fit_url)
    if records_data:
        field_name = f'{side}_pedal_smoothness'
        if field_name in records_data:
            return records_data[field_name]
    
    return None

def calculate_total_strokes(cadence_data: List[int]) -> int:
    """
    计算踏板总行程数
    
    Args:
        cadence_data: 踏频数据列表（RPM）
        
    Returns:
        int: 总踩踏次数
    """
    if not cadence_data:
        return 0
    
    # 假设每秒一个数据点，踏频是每分钟的转数
    # 总踩踏次数 = 所有踏频数据点之和 * (1/60) 分钟
    total_revolutions = sum(cadence_data) / 60.0
    
    return int(total_revolutions)

def get_activity_speed_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的速度相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 速度相关信息，如果不存在则返回None
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
        
        # 获取速度数据
        speed_data = stream_data.get('speed', [])
        power_data = stream_data.get('power', [])
        elapsed_time_data = stream_data.get('elapsed_time', [])
        
        if not speed_data:
            return None
        
        # 过滤有效的速度数据（大于0）
        valid_speeds = [s for s in speed_data if s is not None and s > 0]
        if not valid_speeds:
            return None
        
        result = {}
        
        # 1. 平均速度（千米每小时，保留一位小数）
        if session_data and 'avg_speed' in session_data:
            # 如果session中有速度数据，需要转换为km/h
            session_speed = session_data['avg_speed']
            if session_speed:
                # 假设session中的速度是m/s，转换为km/h
                result['average_speed'] = round(float(session_speed) * 3.6, 1)
            else:
                result['average_speed'] = round(sum(valid_speeds) / len(valid_speeds), 1)
        else:
            result['average_speed'] = round(sum(valid_speeds) / len(valid_speeds), 1)
        
        # 2. 最大速度（千米每小时，保留一位小数）
        if session_data and 'max_speed' in session_data:
            # 如果session中有最大速度数据，需要转换为km/h
            session_max_speed = session_data['max_speed']
            if session_max_speed:
                # 假设session中的速度是m/s，转换为km/h
                result['max_speed'] = round(float(session_max_speed) * 3.6, 1)
            else:
                result['max_speed'] = round(max(valid_speeds), 1)
        else:
            result['max_speed'] = round(max(valid_speeds), 1)
        
        # 3. 移动时间（格式化字符串）
        if session_data and 'total_timer_time' in session_data:
            result['moving_time'] = format_time(session_data['total_timer_time'])
        elif session_data and 'total_elapsed_time' in session_data:
            result['moving_time'] = format_time(session_data['total_elapsed_time'])
        elif elapsed_time_data:
            max_elapsed = max(elapsed_time_data)
            result['moving_time'] = format_time(max_elapsed)
        else:
            result['moving_time'] = "00:00:00"
        
        # 4. 全程耗时（总时间，格式化字符串）
        if session_data and 'total_elapsed_time' in session_data:
            result['total_time'] = format_time(session_data['total_elapsed_time'])
        elif elapsed_time_data:
            # 从elapsed_time数据计算总时间
            total_seconds = calculate_total_time_from_elapsed(elapsed_time_data)
            result['total_time'] = format_time(total_seconds)
        else:
            result['total_time'] = "00:00:00"
        
        # 5. 暂停时间（全程耗时减去移动时间）
        total_seconds = parse_time_to_seconds(result['total_time'])
        moving_seconds = parse_time_to_seconds(result['moving_time'])
        pause_seconds = total_seconds - moving_seconds
        result['pause_time'] = format_time(pause_seconds)
        
        # 6. 滑行时间（速度低于1km/h或功率低于10w的时间，暂停时间点不算在内）
        result['coasting_time'] = calculate_coasting_time(speed_data, power_data, elapsed_time_data)
        
        return result
        
    except Exception as e:
        return None

def calculate_total_time_from_elapsed(elapsed_time_data: List[int]) -> int:
    """
    从elapsed_time数据计算总时间
    
    Args:
        elapsed_time_data: elapsed_time数据列表
        
    Returns:
        int: 总时间（秒）
    """
    if not elapsed_time_data:
        return 0
    
    # 找到最大的elapsed_time，这通常是总时间
    max_elapsed = max(elapsed_time_data)
    
    # 但是elapsed_time可能不包括暂停时间，所以需要估算
    # 假设数据点之间的间隔是1秒，如果有大的间隔，说明有暂停
    total_time = max_elapsed
    
    # 检查数据点之间的间隔
    if len(elapsed_time_data) > 1:
        # 计算实际的数据点数量，这应该等于总时间（包括暂停）
        total_time = len(elapsed_time_data)
    
    return total_time

def calculate_coasting_time(speed_data: List[float], power_data: List[int], elapsed_time_data: List[int]) -> str:
    """
    计算滑行时间（速度低于1km/h或功率低于10w的时间，暂停时间点不算在内）
    
    Args:
        speed_data: 速度数据列表（km/h）
        power_data: 功率数据列表（W）
        elapsed_time_data: elapsed_time数据列表
        
    Returns:
        str: 滑行时间（格式化字符串）
    """
    if not speed_data or not elapsed_time_data:
        return "00:00:00"
    
    coasting_seconds = 0
    
    # 遍历所有数据点
    for i in range(len(speed_data)):
        if i >= len(elapsed_time_data):
            break
        
        # 检查是否为滑行状态
        is_coasting = False
        
        # 检查速度是否低于1km/h
        if i < len(speed_data) and speed_data[i] is not None:
            if speed_data[i] < 1.0:
                is_coasting = True
        
        # 检查功率是否低于10W
        if not is_coasting and i < len(power_data) and power_data[i] is not None:
            if power_data[i] < 10:
                is_coasting = True
        
        # 如果是滑行状态，计算这个时间段的持续时间
        if is_coasting:
            if i == 0:
                # 第一个数据点，假设持续1秒
                coasting_seconds += 1
            else:
                # 计算与前一个数据点的时间差
                current_elapsed = elapsed_time_data[i]
                prev_elapsed = elapsed_time_data[i-1]
                time_diff = current_elapsed - prev_elapsed
                
                # 如果时间差合理（不超过5秒），认为是连续滑行
                if time_diff <= 5:
                    coasting_seconds += time_diff
                else:
                    # 时间差过大，可能是有暂停，只计算1秒
                    coasting_seconds += 1
    
    return format_time(coasting_seconds) 

def get_activity_altitude_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的海拔相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 海拔相关信息，如果不存在则返回None
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
        
        # 获取海拔和距离数据
        altitude_data = stream_data.get('altitude', [])
        distance_data = stream_data.get('distance', [])
        
        if not altitude_data:
            return None
        
        # 过滤有效的海拔数据
        valid_altitudes = [alt for alt in altitude_data if alt is not None]
        if not valid_altitudes:
            return None
        
        result = {}
        
        # 1. 爬升海拔（米，保留整数）- 优先使用session中的total_ascent
        if session_data and 'total_ascent' in session_data and session_data['total_ascent']:
            result['elevation_gain'] = int(session_data['total_ascent'])
        else:
            result['elevation_gain'] = int(calculate_elevation_gain(valid_altitudes))
        
        # 2. 最高海拔（米，保留整数）
        result['max_altitude'] = int(max(valid_altitudes))
        
        # 3. 最大坡度（百分比，保留两位小数）
        result['max_grade'] = calculate_max_grade(altitude_data, distance_data)
        
        # 4. 累计下降（米，保留整数）- 优先使用session中的total_descent
        if session_data and 'total_descent' in session_data and session_data['total_descent']:
            result['total_descent'] = int(session_data['total_descent'])
        else:
            result['total_descent'] = int(calculate_total_descent(valid_altitudes))
        
        # 5. 最低海拔（米，保留整数）
        result['min_altitude'] = int(min(valid_altitudes))
        
        # 6. 上坡距离（千米，保留两位小数）
        result['uphill_distance'] = calculate_uphill_distance(altitude_data, distance_data)
        
        # 7. 下坡距离（千米，保留两位小数）
        result['downhill_distance'] = calculate_downhill_distance(altitude_data, distance_data)
        
        return result
        
    except Exception as e:
        return None

# !待优化
def calculate_max_grade(altitude_data: List[int], distance_data: List[float]) -> float:
    """
    计算最大坡度
    
    Args:
        altitude_data: 海拔数据列表（米）
        distance_data: 距离数据列表（米）
        
    Returns:
        float: 最大坡度（百分比，保留两位小数）
    """
    if not altitude_data or not distance_data or len(altitude_data) < 2 or len(distance_data) < 2:
        return 0.0
    
    max_grade = 0.0
    
    # 计算相邻点之间的坡度
    for i in range(1, min(len(altitude_data), len(distance_data))):
        if (altitude_data[i] is not None and altitude_data[i-1] is not None and 
            distance_data[i] is not None and distance_data[i-1] is not None):
            
            # 计算海拔差和距离差
            altitude_diff = altitude_data[i] - altitude_data[i-1]
            distance_diff = distance_data[i] - distance_data[i-1]
            
            # 避免除零错误
            if distance_diff > 0:
                # 坡度 = 海拔差 / 距离差 * 100%
                grade = (altitude_diff / distance_diff) * 100
                max_grade = max(max_grade, grade)
    
    return round(max_grade, 2)

def calculate_total_descent(altitudes: List[int]) -> float:
    """
    计算累计下降
    
    Args:
        altitudes: 海拔数据列表（米）
        
    Returns:
        float: 累计下降（米）
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
    
    # 计算下降
    total_descent = 0.0
    for i in range(1, len(filtered_altitudes)):
        diff = filtered_altitudes[i] - filtered_altitudes[i-1]
        if diff < 0:  # 只计算下降
            total_descent += abs(diff)
    
    return total_descent

def calculate_uphill_distance(altitude_data: List[int], distance_data: List[float]) -> float:
    """
    计算上坡距离
    
    Args:
        altitude_data: 海拔数据列表（米）
        distance_data: 距离数据列表（米）
        
    Returns:
        float: 上坡距离（千米，保留两位小数）
    """
    if not altitude_data or not distance_data or len(altitude_data) < 2 or len(distance_data) < 2:
        return 0.0
    
    uphill_distance = 0.0
    
    # 计算相邻点之间的上坡距离
    for i in range(1, min(len(altitude_data), len(distance_data))):
        if (altitude_data[i] is not None and altitude_data[i-1] is not None and 
            distance_data[i] is not None and distance_data[i-1] is not None):
            
            # 计算海拔差和距离差
            altitude_diff = altitude_data[i] - altitude_data[i-1]
            distance_diff = distance_data[i] - distance_data[i-1]
            
            # 如果是上坡（海拔增加），累加上坡距离
            if altitude_diff > 0 and distance_diff > 0:
                uphill_distance += distance_diff
    
    # 转换为千米并保留两位小数
    return round(uphill_distance / 1000, 2)

def calculate_downhill_distance(altitude_data: List[int], distance_data: List[float]) -> float:
    """
    计算下坡距离
    
    Args:
        altitude_data: 海拔数据列表（米）
        distance_data: 距离数据列表（米）
        
    Returns:
        float: 下坡距离（千米，保留两位小数）
    """
    if not altitude_data or not distance_data or len(altitude_data) < 2 or len(distance_data) < 2:
        return 0.0
    
    downhill_distance = 0.0
    
    # 计算相邻点之间的下坡距离
    for i in range(1, min(len(altitude_data), len(distance_data))):
        if (altitude_data[i] is not None and altitude_data[i-1] is not None and 
            distance_data[i] is not None and distance_data[i-1] is not None):
            
            # 计算海拔差和距离差
            altitude_diff = altitude_data[i] - altitude_data[i-1]
            distance_diff = distance_data[i] - distance_data[i-1]
            
            # 如果是下坡（海拔减少），累加下坡距离
            if altitude_diff < 0 and distance_diff > 0:
                downhill_distance += distance_diff
    
    # 转换为千米并保留两位小数
    return round(downhill_distance / 1000, 2) 

def get_activity_temperature_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的温度相关信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 温度相关信息，如果不存在则返回None
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
        
        # 获取温度数据
        temperature_data = stream_data.get('temp', [])
        if not temperature_data:
            return None
        
        # 过滤有效的温度数据（排除None值）
        valid_temperatures = [t for t in temperature_data if t is not None]
        if not valid_temperatures:
            return None
        
        result = {}
        
        # 1. 最低温度（保留整数）- 优先使用session中的数据
        if session_data and 'min_temperature' in session_data:
            result['min_temp'] = int(round(session_data['min_temperature']))
        else:
            result['min_temp'] = int(round(min(valid_temperatures)))
        
        # 2. 平均温度（保留整数）- 优先使用session中的数据
        if session_data and 'avg_temperature' in session_data:
            result['avg_temp'] = int(round(session_data['avg_temperature']))
        else:
            result['avg_temp'] = int(round(sum(valid_temperatures) / len(valid_temperatures)))
        
        # 3. 最大温度（保留整数）- 优先使用session中的数据
        if session_data and 'max_temperature' in session_data:
            result['max_temp'] = int(round(session_data['max_temperature']))
        else:
            result['max_temp'] = int(round(max(valid_temperatures)))
        
        return result
        
    except Exception as e:
        return None 

def get_activity_best_power_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的最佳功率信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 活动最佳功率信息，如果不存在则返回None
    """
    try:
        # 获取活动总体信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            return None
        
        activity, athlete = activity_athlete
        
        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        # 获取最佳功率数据
        best_powers_data = stream_data.get('best_power', [])
        if not best_powers_data:
            return None
        
        # 定义时间区间映射（秒）
        time_intervals = {
            '5s': 5,
            '30s': 30,
            '1min': 60,
            '5min': 300,
            '8min': 480,
            '20min': 1200,
            '30min': 1800,
            '1h': 3600
        }
        
        # 构建最佳功率响应
        best_powers = {}
        for interval_name, interval_seconds in time_intervals.items():
            # 检查是否有足够的数据点
            if len(best_powers_data) >= interval_seconds:
                best_powers[interval_name] = best_powers_data[interval_seconds - 1]  # 数组索引从0开始
        
        return {
            'best_powers': best_powers
        }
        
    except Exception as e:
        return None 

def get_activity_training_effect_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的训练效果信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 训练效果信息，如果不存在则返回None
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
        
        result = {}
        
        # 1. 主要训练益处 - 返回"none"
        result['primary_training_benefit'] = "none"
        
        # 2. 有氧效果 - 返回"none"
        result['aerobic_effect'] = "none"
        
        # 3. 无氧效果 - 返回"none"
        result['anaerobic_effect'] = "none"
        
        # 4. 训练负荷 - 和power中的训练负荷一样，保留到整数
        if float(athlete.ftp) and float(athlete.ftp) > 0:
            # 获取平均功率
            avg_power = None
            if session_data and 'avg_power' in session_data:
                avg_power = int(session_data['avg_power'])
            elif 'power' in stream_data and stream_data['power']:
                valid_powers = [p for p in stream_data['power'] if p is not None and p > 0]
                if valid_powers:
                    avg_power = int(sum(valid_powers) / len(valid_powers))
            
            # 获取运动时长
            duration_seconds = 0
            if session_data and 'total_timer_time' in session_data:
                duration_seconds = session_data['total_timer_time']
            elif session_data and 'total_elapsed_time' in session_data:
                duration_seconds = session_data['total_elapsed_time']
            elif 'elapsed_time' in stream_data and stream_data['elapsed_time']:
                duration_seconds = max(stream_data['elapsed_time'])
            
            if avg_power and avg_power > 0 and duration_seconds > 0:
                result['training_load'] = calculate_and_save_training_load(
                    db,
                    activity_id,
                    avg_power, 
                    float(athlete.ftp), 
                    duration_seconds
                )
            else:
                result['training_load'] = 0
        else:
            result['training_load'] = 0
        
        # 5. 碳水化合物消耗量 - 返回"none"
        result['carbohydrate_consumption'] = "none"
        
        return result
        
    except Exception as e:
        return None 

def get_activity_power_zones(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的功率区间数据
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 功率区间数据，如果不存在则返回None
    """
    try:
        # 获取活动和运动员信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            return None
        
        activity, athlete = activity_athlete
        
        # 检查FTP数据
        try:
            ftp = int(athlete.ftp)
        except (TypeError, ValueError):
            ftp = None
        if not ftp or ftp <= 0:
            return None
        
        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        # 获取功率数据
        power_data = stream_data.get('power', [])
        if not power_data:
            return None
        
        # 分析功率区间
        from .zone_analyzer import ZoneAnalyzer
        distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
        
        return {
            "distribution_buckets": distribution_buckets,
            "type": "power"
        }
        
    except Exception as e:
        return None

def get_activity_heartrate_zones(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的心率区间数据
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 心率区间数据，如果不存在则返回None
    """
    try:
        # 获取活动和运动员信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            return None
        
        activity, athlete = activity_athlete
        
        # 检查最大心率数据
        if not athlete.max_heartrate or athlete.max_heartrate <= 0:
            return None
        
        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        # 获取心率数据
        heartrate_data = stream_data.get('heartrate', [])
        if not heartrate_data:
            return None
        
        # 分析心率区间
        from .zone_analyzer import ZoneAnalyzer
        distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(heartrate_data, athlete.max_heartrate)
        
        return {
            "distribution_buckets": distribution_buckets,
            "type": "heartrate"
        }
        
    except Exception as e:
        return None 