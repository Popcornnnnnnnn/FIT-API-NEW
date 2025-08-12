"""
Activities模块的数据库操作函数

包含活动相关的数据库查询和操作。
"""

from sqlalchemy.orm import Session
from typing import Optional, Tuple, Dict, Any, List
from ..streams.models import TbActivity, TbAthlete
from .data_manager import activity_data_manager
import requests
from fitparse import FitFile
from io import BytesIO 
import numpy as np

# --------------数据库相关--------------
def update_database_field(
    db: Session, 
    table_class, 
    record_id: int, 
    field_name: str, 
    value: Any
) -> bool:
    try:
        record = db.query(table_class).filter(table_class.id == record_id).first()
        if not record:
            return False
        if not hasattr(record, field_name):
            return False
        setattr(record, field_name, value)
        db.commit()
        return True
        
    except Exception as e:
        # 回滚事务
        db.rollback()
        return False

def get_activity_athlete(
    db: Session, 
    activity_id: int
) -> Optional[Tuple[TbActivity, TbAthlete]]:
    # 查询活动信息（返回 tb_activity 的一整行内容）
    activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
    if not activity:
        return None

    # 查询运动员信息（返回 tb_athlete 的一整行内容）
    athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
    if not athlete:
        return None
    return activity, athlete



# --------------所有接口相关的整体信息--------------
def get_activity_overall_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None 
        
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None

        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        
        result = {}
        
        if session_data and 'total_distance' in session_data:
            result['distance'] = round(session_data['total_distance'] / 1000, 2)
        else:
            result['distance'] = round(max(stream_data['distance']) / 1000, 2)

    
        if session_data and 'total_timer_time' in session_data:
            moving_time = session_data['total_timer_time']
            result['moving_time'] = format_time(moving_time)
        else:
            moving_time = max(stream_data.get('elapsed_time', []))
            result['moving_time'] = format_time(moving_time)
        
        if session_data and 'avg_speed' in session_data:
            result['average_speed'] = round(float(session_data['avg_speed']) * 3.6, 1)
        else:
            result['average_speed'] = round(sum(stream_data.get('speed', [])) / len(stream_data.get('speed', [])), 1)

        if 'total_ascent' in session_data and session_data['total_ascent']:
            result['elevation_gain'] = int(session_data['total_ascent'])
        else:
            result['elevation_gain'] = int(calculate_elevation_gain(stream_data.get('enhanced_altitude', [])))
        
        if session_data and 'avg_power' in session_data:
            result['avg_power'] = int(session_data['avg_power'])
        elif 'power' in stream_data and stream_data['power']:
            result['avg_power'] = int(sum(stream_data['power']) / len(stream_data['power']))
        else:
            result['avg_power'] = None
        
        if float(athlete.ftp) and float(athlete.ftp) > 0 and result['avg_power'] is not None and result['avg_power'] > 0:
            result['training_load'] = calculate_and_save_training_load(
                db,
                activity_id,
                result['avg_power'], 
                float(athlete.ftp), 
                moving_time
            )
        else:
            result['training_load'] = None
    
        result['status'] = athlete.tsb
        
        if session_data and 'avg_heart_rate' in session_data:
            result['avg_heartrate'] = int(session_data['avg_heart_rate'])
        elif "heart_rate" in stream_data:
            result['avg_heartrate'] = int(sum(stream_data['heart_rate']) / len(stream_data['heart_rate']))
        else:
            result['avg_heartrate'] = None
        
        if 'altitude' in stream_data and stream_data['altitude']:
            result['max_altitude'] = int(max(stream_data['altitude']))
        else:
            result['max_altitude'] = None

        if "total_calories" in session_data:
            result['calories'] = int(session_data['total_calories'])
        elif result['avg_power'] is not None:
            result['calories'] = estimate_calories_with_power(
                result['avg_power'], 
                moving_time, 
                athlete.weight if athlete.weight else 70
            )
        elif result['avg_heartrate'] is not None:
            result['calories'] = estimate_calories_with_heartrate(
                result['avg_heartrate'], 
                moving_time, 
                athlete.weight if athlete.weight else 70
            )
        else:
            result['calories'] = None
        
        
        return result   
    except Exception as e:
        return None

def get_activity_power_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        ftp = int(athlete.ftp)

        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        
        power_data = stream_data.get('power', [])
        if not power_data:
            return None

        valid_powers = [p for p in power_data if p is not None and p > 0]
        if not valid_powers:
            return None
        
        result = {}

        if session_data and 'avg_power' in session_data:
            result['avg_power'] = int(session_data['avg_power'])
        else:
            result['avg_power'] = int(sum(valid_powers) / len(valid_powers))
        
        if session_data and 'max_power' in session_data:
            result['max_power'] = int(session_data['max_power'])
        else:
            result['max_power'] = int(max(valid_powers))
        
        if session_data and 'normalized_power' in session_data:
            result['normalized_power'] = int(session_data['normalized_power'])
        else:
            result['normalized_power'] = calculate_normalized_power(valid_powers)
        
        if session_data and 'intensity_factor' in session_data:
            result['intensity_factor'] = round(session_data['intensity_factor'], 2)
        else:
            result['intensity_factor'] = round(result['normalized_power'] / ftp, 2)

        result['total_work'] = round(sum(valid_powers) / 1000, 0)
        
        if result['avg_power'] > 0:
            result['variability_index'] = round(result['normalized_power'] / result['avg_power'], 2)
        else:
            result['variability_index'] = None

        result['weighted_average_power'] = None
        result['work_above_ftp'] = int(sum([(power - ftp) for power in valid_powers if power > ftp]) / 1000)
        result['eftp'] = None
        
        w_balance_data = stream_data.get('w_balance', [])
        if w_balance_data:
            result['w_balance_decline'] = calculate_w_balance_decline(w_balance_data)
        else:
            result['w_balance_decline'] = None
        
        return result
        
    except Exception as e:
        return None

def get_activity_heartrate_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        
        heartrate_data = stream_data.get('heart_rate', [])
        if not heartrate_data:
            return None
  
        def filter_heartrate_data_with_smoothing(
            heartrate_data: List[Any]
        ) -> List[int]:
            filtered_data = []
            for i, hr in enumerate(heartrate_data):
                if hr is None:
                    continue
                if hr <= 0 or hr < 30:
                    continue
                if hr > 220:
                    continue
                if filtered_data and abs(hr - filtered_data[-1]) > 50:
                    continue
                
                filtered_data.append(hr)
            return filtered_data

        def calculate_efficiency_index(
        ) -> Optional[float]:
            try:
                power_data = stream_data.get('power', [])   
                valid_power = [p for p in power_data if p is not None and p > 0]
                NP = calculate_normalized_power(valid_power)
                avg_hr = sum(valid_hr) / len(valid_hr)
                return round(NP / avg_hr, 2)
            except Exception as e:
                return None

        def calculate_heartrate_recovery_rate(
        ) -> int:
            try:
                max_drop = 0
                window = 60
                n = len(valid_hr)
                
                for i in range(n - window):
                    start_hr = valid_hr[i]
                    end_hr = valid_hr[i + window]
                    drop = start_hr - end_hr
                    if drop > max_drop:
                        max_drop = drop
                
                return int(max_drop) if max_drop > 0 else 0
                
            except Exception as e:
                return 0

        def calculate_decoupling_rate(
        ) -> Optional[str]:
            try:
                min_length = min(len(power_data), len(heartrate_data))
                powers = power_data[:min_length]
                heart_rates = heartrate_data[:min_length]
                
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
                
                return None
                
            except Exception as e:
                return None 

        def calculate_heartrate_lag(
        ) -> Optional[int]:
            try:
                power_data = stream_data.get('power', [])
                heartrate_data = stream_data.get('heart_rate', [])
                power_valid = [p if p is not None else 0 for p in power_data]
                heartrate_valid = [h if h is not None else 0 for h in heartrate_data]
                power_array = np.array(power_valid)
                heartrate_array = np.array(heartrate_valid)

                power_norm = power_array - np.mean(power_array)
                heartrate_norm = heartrate_array - np.mean(heartrate_array)

                correlation = np.correlate(power_norm, heartrate_norm, mode='full')

                lag_max = np.argmax(correlation) - (len(power_array) - 1)
                max_corr = np.max(correlation)
                return int(abs(lag_max)) if max_corr > 0.3 * len(power_array) else None
            except Exception as e:
                return None

        # 过滤心率异常值
        valid_hr = filter_heartrate_data_with_smoothing(heartrate_data)
        
        result = {}
        
        if session_data and 'avg_heart_rate' in session_data:
            result['avg_heartrate'] = int(session_data['avg_heart_rate'])
        else:
            result['avg_heartrate'] = int(sum(valid_hr) / len(valid_hr))

        if session_data and 'max_heart_rate' in session_data:
            result['max_heartrate'] = int(session_data['max_heart_rate'])
        else:
            result['max_heartrate'] = int(max(valid_hr))
        
        if "power" in stream_data:
            power_data = stream_data.get('power', [])
            result['heartrate_recovery_rate'] = calculate_heartrate_recovery_rate()
            result['heartrate_lag'] = calculate_heartrate_lag()
            result['efficiency_index'] = calculate_efficiency_index()
            result['decoupling_rate'] = calculate_decoupling_rate()
        else:
            result['heartrate_recovery_rate'] = None
            result['heartrate_lag'] = None
            result['efficiency_index'] = None
            result['decoupling_rate'] = None
        
        return result
        
    except Exception as e:
        return None

def get_activity_cadence_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        
        cadence_data = stream_data.get('cadence', [])
        if not cadence_data:
            return None
        
        valid_cadences = [c for c in cadence_data if c is not None and c > 0]
        if not valid_cadences:
            return None
        
        result = {}
        
        if session_data and 'avg_cadence' in session_data:
            result['avg_cadence'] = int(session_data['avg_cadence'])
        else:
            result['avg_cadence'] = int(sum(valid_cadences) / len(valid_cadences))
        
        if session_data and 'max_cadence' in session_data:
            result['max_cadence'] = int(session_data['max_cadence'])
        else:
            result['max_cadence'] = int(max(valid_cadences))
        
        if "left_torque_effectiveness" and "right_torque_effectiveness" in stream_data:
            left_te_list = stream_data.get('left_torque_effectiveness', [])
            right_te_list = stream_data.get('right_torque_effectiveness', [])
            if left_te_list and right_te_list:
                result['left_torque_effectiveness'] = round(sum(left_te_list) / len(left_te_list), 2)
                result['right_torque_effectiveness'] = round(sum(right_te_list) / len(right_te_list), 2)
        else:
            result['left_torque_effectiveness'] = None
            result['right_torque_effectiveness'] = None

        if "left_pedal_smoothness" and "right_pedal_smoothness" in stream_data:
            left_ps_list = stream_data.get('left_pedal_smoothness', [])
            right_ps_list = stream_data.get('right_pedal_smoothness', [])
            if left_ps_list and right_ps_list:
                result['left_pedal_smoothness'] = round(sum(left_ps_list) / len(left_ps_list), 2)
                result['right_pedal_smoothness'] = round(sum(right_ps_list) / len(right_ps_list), 2)
        else:   
            result['left_pedal_smoothness'] = None
            result['right_pedal_smoothness'] = None

        def get_left_right_balance() -> Optional[Dict[str, int]]:
            def parse_left_right(value: float) -> Optional[Tuple[int, int]]: # ! 这里的解析方式应该没有问题
                """解析左右平衡值"""
                try:
                    # 将float转换为int进行位运算
                    int_value = int(value)
                    # 正常的record值解析
                    side_flag = int_value & 0x01
                    percent = int_value >> 1
                    if side_flag == 1:
                        right = percent
                        left = 100 - percent
                    else:
                        left = percent
                        right = 100 - percent
                    return (left, right)
                except (ValueError, TypeError):
                    return None
            
            left_right_balance_list = stream_data.get('left_right_balance', [])
            if not left_right_balance_list:
                return None
            else:
                parsed_values = []
                for value in left_right_balance_list:
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

        result['left_right_balance'] = get_left_right_balance()
        result['total_strokes'] = int(sum(cadence_data) / 60.0)
        return result
        
    except Exception as e:
        return None

def get_activity_speed_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:

        activity, _ = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        
        speed_data = stream_data.get('speed', [])
        power_data = stream_data.get('power', [])
        
        
        result = {}
        
        if session_data and 'avg_speed' in session_data:
            result['avg_speed'] = round(float(session_data['avg_speed']) * 3.6, 1)
        else:
            result['avg_speed'] = round(sum(speed_data) / len(speed_data), 1)
        
        if session_data and 'max_speed' in session_data:
            result['max_speed'] = round(float(session_data['max_speed']) * 3.6, 1)
        else:
            result['max_speed'] = round(max(speed_data), 1)


        if session_data and 'total_timer_time' in session_data:
            moving_time = session_data['total_timer_time']
            result['moving_time'] = format_time(moving_time)
        else:
            moving_time = max(stream_data.get('elapsed_time', []))
            result['moving_time'] = format_time(moving_time)
        
        if session_data and 'total_elapsed_time' in session_data:
            total_time = session_data['total_elapsed_time']
            result['total_time'] = format_time(total_time)
        else:
            total_time = max(stream_data.get('timestamp', []))
            result['total_time'] = format_time(total_time)
        
        pause_seconds = total_time - moving_time
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
    except Exception as e:
        return None

def get_activity_altitude_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:

    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None

        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None

        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
    
        altitude_data = stream_data.get('altitude', [])
        distance_data = stream_data.get('distance', [])
        
        if not altitude_data:
            return None
        


        def calculate_max_grade() -> float:
            
            max_grade = 0.0
            # 使用间隔更多的点计算坡度，提高数据准确性
            # 间隔点数：每5个点计算一次坡度，或者每50米距离计算一次
            interval_points = 5  # 每5个点计算一次
            min_distance_interval = 50  # 最小距离间隔（米）
            
            for i in range(interval_points, min(len(altitude_data), len(distance_data))):
                # 获取当前点和间隔前的点
                current_idx = i
                previous_idx = i - interval_points
                
                if (altitude_data[current_idx] is not None and altitude_data[previous_idx] is not None and 
                    distance_data[current_idx] is not None and distance_data[previous_idx] is not None):
                    
                    # 计算海拔差和距离差
                    altitude_diff = altitude_data[current_idx] - altitude_data[previous_idx]
                    distance_diff = distance_data[current_idx] - distance_data[previous_idx]
                    
                    # 避免除零错误和异常值
                    if (distance_diff > min_distance_interval and distance_diff < 1000):  # 距离差至少50米，不超过1000米
                        # 坡度 = 海拔差 / 距离差 * 100%
                        grade = (altitude_diff / distance_diff) * 100
                        # 过滤不合理的坡度值（超过50%的坡度在现实中几乎不可能）
                        if abs(grade) <= 50:
                            max_grade = max(max_grade, abs(grade))
            
            return round(max_grade, 2)

        def calculate_total_descent() -> float:
            # 过滤异常值（参考VAM计算中的过滤方法）
            filtered_altitudes = []
            for i, alt in enumerate(altitude_data):
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

        def calculate_uphill_distance() -> float:
            uphill_distance = 0.0
            
            # 使用间隔更多的点计算上坡距离，提高数据准确性
            interval_points = 5  # 每5个点计算一次
            min_distance_interval = 50  # 最小距离间隔（米）
            
            for i in range(interval_points, min(len(altitude_data), len(distance_data))):
                # 获取当前点和间隔前的点
                current_idx = i
                previous_idx = i - interval_points
                
                if (altitude_data[current_idx] is not None and altitude_data[previous_idx] is not None and 
                    distance_data[current_idx] is not None and distance_data[previous_idx] is not None):
                    
                    # 计算海拔差和距离差
                    altitude_diff = altitude_data[current_idx] - altitude_data[previous_idx]
                    distance_diff = distance_data[current_idx] - distance_data[previous_idx]
                    
                    # 如果是上坡（海拔增加）且距离间隔合理，累加上坡距离
                    if altitude_diff > 1 and distance_diff > min_distance_interval:
                        uphill_distance += distance_diff
            
            # 转换为千米并保留两位小数
            return round(uphill_distance / 1000, 2)

        def calculate_downhill_distance() -> float:
            
            downhill_distance = 0.0
            
            # 使用间隔更多的点计算下坡距离，提高数据准确性
            interval_points = 5  # 每5个点计算一次
            min_distance_interval = 50  # 最小距离间隔（米）
            
            for i in range(interval_points, min(len(altitude_data), len(distance_data))):
                # 获取当前点和间隔前的点
                current_idx = i
                previous_idx = i - interval_points
                
                if (altitude_data[current_idx] is not None and altitude_data[previous_idx] is not None and 
                    distance_data[current_idx] is not None and distance_data[previous_idx] is not None):
                    
                    # 计算海拔差和距离差
                    altitude_diff = altitude_data[current_idx] - altitude_data[previous_idx]
                    distance_diff = distance_data[current_idx] - distance_data[previous_idx]
                    
                    # 如果是下坡（海拔减少）且距离间隔合理，累加下坡距离
                    if altitude_diff < -1 and distance_diff > min_distance_interval:
                        downhill_distance += distance_diff
            
            # 转换为千米并保留两位小数
            return round(downhill_distance / 1000, 2) 
        
        result = {}
        
        if session_data and 'total_ascent' in session_data and session_data['total_ascent']:
            result['elevation_gain'] = int(session_data['total_ascent'])
        else:
            result['elevation_gain'] = int(calculate_elevation_gain(altitude_data))
        
        result['max_altitude'] = int(max(altitude_data))
        result['max_grade'] = calculate_max_grade()
        
        if session_data and 'total_descent' in session_data and session_data['total_descent']:
            result['total_descent'] = int(session_data['total_descent'])
        else:
            result['total_descent'] = int(calculate_total_descent())
        
        result['min_altitude'] = int(min(altitude_data))
        result['uphill_distance'] = calculate_uphill_distance() 
        result['downhill_distance'] = calculate_downhill_distance()
        
        return result
        
    except Exception as e:
        return None

def get_activity_temperature_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        temperature_data = stream_data.get('temperature', [])
        if not temperature_data:
            return None
        
        result = {}     
        result["min_temp"] = int(round(min(temperature_data)))
        result["avg_temp"] = int(round(sum(temperature_data) / len(temperature_data)))
        result["max_temp"] = int(round(max(temperature_data)))
        
        return result
        
    except Exception as e:
        return None 

def get_activity_best_power_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        best_powers_data = stream_data.get('best_power', [])
        if not best_powers_data:
            return None
        
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
        
        return { 'best_powers': best_powers }
        
    except Exception as e:
        return None 

def get_activity_training_effect_info(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        if 'power' not in stream_data:
            return None
        power_data = stream_data.get('power', [])
        
        
        ftp = int(athlete.ftp)
        result = {}
        result['aerobic_effect'] = _calculate_aerobic_effect(power_data, ftp)
        result['anaerobic_effect'] = _calculate_anaerobic_effect(power_data, ftp)

        
        primary_training_benefit, _ = _get_primary_training_benefit(
            _get_power_zone_percentages(power_data, ftp),
            _get_power_zone_time(power_data, ftp),
            round(len(power_data) / 60, 0),
            result['aerobic_effect'],
            result['anaerobic_effect'],
            ftp,
            max(power_data)
        )
        avg_power = int(sum(power_data) / len(power_data))
        result['primary_training_benefit'] = primary_training_benefit
        result['training_load'] = calculate_training_load(avg_power, ftp, len(power_data))
        calories = estimate_calories_with_power(avg_power, len(power_data), athlete.weight if athlete.weight else 70)
        result['carbohydrate_consumption'] = round(calories / 4.138, 0)     
        return result
        
    except Exception as e:
        return None 


# --------------海拔相关函数--------------
def calculate_elevation_gain(
    altitude_data: list
) -> float:
    # 过滤异常值（参考VAM计算中的过滤方法）
    filtered_altitudes = []
    for i, alt in enumerate(altitude_data):
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



# --------------时间相关函数--------------
def format_time(
    seconds: int
) -> Optional[str]:
    try:    
        seconds = int(seconds)        
        if seconds < 0:
            seconds = 0
        
        if seconds < 60:
            return f"{seconds}s"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours == 0:
            if minutes < 10:
                return f"{minutes}:{secs:02d}"
            else:
                return f"{minutes}:{secs:02d}"
        else:
            # 1小时以上，去掉小时前导零
            return f"{hours}:{minutes:02d}:{secs:02d}"
            
    except (ValueError, TypeError):
        return None




# --------------训练效果相关函数--------------
def estimate_calories_with_power( # ! 这个算法应该有点问题
    avg_power: int, 
    duration_seconds: int, 
    weight_kg: int
) -> Optional[int]:
    try:
        # 功率转换为卡路里的系数（约1）
        power_to_calories_factor = 1
        
        # 基础代谢率（BMR）贡献
        bmr_per_minute = 1.2  # 每分钟基础代谢消耗的卡路里
        
        # 计算总卡路里
        power_calories = avg_power * duration_seconds * power_to_calories_factor / 3600  # 转换为小时
        bmr_calories = bmr_per_minute * duration_seconds / 60  # 基础代谢消耗
        total_calories = power_calories + bmr_calories
        return int(total_calories)
    except Exception as e:
        print(f"计算卡路里时出错: {str(e)}")
        return None

def estimate_calories_with_heartrate(
    avg_heartrate: int, 
    duration_seconds: int, 
    weight_kg: int
) -> Optional[int]: # ! 理论上 6 应该替换成 0.2017 * 年龄，基于 Keytel 公式，适合中等强度运动估算
    try:
        return round((duration_seconds / 60) * (0.6309 * avg_heartrate + 0.1988 * weight_kg + 6 - 55.0969) / 4.184, 0)
    except Exception as e:
        print(f"计算卡路里时出错: {str(e)}")
        return None

def calculate_training_load(
    avg_power: int, 
    ftp: int, 
    duration_seconds: int
) -> int:
    intensity_factor = avg_power / ftp
    duration_hours = duration_seconds / 3600.0
    training_load = (intensity_factor ** 2) * duration_hours
    return int(training_load * 100)

def calculate_and_save_training_load(
    db: Session, 
    activity_id: int, 
    avg_power: int, 
    ftp: int, 
    duration_seconds: int
) -> Optional[int]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        if activity.tss_updated == 0:
            tss = calculate_training_load(avg_power, ftp, duration_seconds)
            update_database_field(db, TbActivity, activity_id, 'tss', tss)
            ctl = athlete.ctl
            atl = athlete.atl
            new_ctl = ctl + (tss - ctl) / 42
            new_atl = atl + (tss - atl) / 7
            update_database_field(db, TbAthlete, activity.athlete_id, "ctl", round(new_ctl, 0))
            update_database_field(db, TbAthlete, activity.athlete_id, "atl", round(new_atl, 0))
            update_database_field(db, TbActivity, activity_id, "tss_updated", 1)
            update_database_field(db, TbAthlete, activity.athlete_id, "tsb", round(new_atl - new_ctl, 0))
            return tss  
        else:
            return activity.tss
    except Exception as e:
        print(f"计算和保存训练负荷时出错: {str(e)}")
        return None


def _calculate_aerobic_effect(
    power_data: list, 
    ftp: int
) -> float:
    try:
        np = calculate_normalized_power(power_data)
        intensity_factor = np / ftp
        return round(min(5.0, intensity_factor * len(power_data) / 3600 + 0.5), 1)
    except Exception as e:
        print(f"计算有氧效果时出错: {str(e)}")
        return 0.0

def _calculate_anaerobic_effect(
    power_data: list, 
    ftp: int
) -> float:
    try:
        if len(power_data) < 30:
            return 0.0
        
        # 计算30秒峰值功率 - 使用滑动窗口，假设数据点是每秒一个
        peak_power_30s = 0
        for i in range(len(power_data) - 29):  # 确保有30个数据点
            window_avg = sum(power_data[i:i+30]) / 30
            if window_avg > peak_power_30s:
                peak_power_30s = window_avg
        
        # 计算无氧容量（超过FTP的功率总和，单位：千焦）
        # 假设数据点是每秒一个，所以功率值直接相加就是焦耳
        anaerobic_capacity = sum([max(0, p - ftp) for p in power_data if p > ftp]) / 1000
        
        # 计算无氧效果
        anaerobic_effect = min(4.0, 0.1 * (peak_power_30s / ftp) + 0.05 * anaerobic_capacity)
        return round(anaerobic_effect, 1)
    except Exception as e:
        print(f"计算无氧效果时出错: {str(e)}")
        return 0.0

def _get_power_zone_percentages(
    power_data: list, 
    ftp: int
) -> list:
    from .zone_analyzer import ZoneAnalyzer
    zones = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
    percentages = []
    for zone in zones:
        # zone['percentage'] 形如 "12.5%"
        percent_str = zone.get('percentage', '0.0%').replace('%', '')
        try:
            percent = float(percent_str)
        except Exception:
            percent = 0.0
        percentages.append(percent)
    return percentages

def _get_power_zone_time(
    power_data: list, 
    ftp: int
) -> list:
    from .zone_analyzer import ZoneAnalyzer
    zones = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
    times = []
    for zone in zones:
        # zone['time'] 形如 "1:23:45" 或 "45s"
        time_str = zone.get('time', '0s')
        # 解析时间字符串为秒
        if 's' in time_str:
            try:
                seconds = int(time_str.replace('s', ''))
            except Exception:
                seconds = 0
        elif ':' in time_str:
            parts = time_str.split(':')
            try:
                if len(parts) == 2:
                    # mm:ss
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    seconds = minutes * 60 + seconds
                elif len(parts) == 3:
                    # hh:mm:ss
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    seconds = 0
            except Exception:
                seconds = 0
        else:
            seconds = 0
        times.append(seconds)
    return times

def _get_primary_training_benefit(
    zone_distribution: list,
    zone_times: list,
    duration_min: int,
    aerobic_effect: float,
    anaerobic_effect: float,
    ftp: int,
    max_power: int,
) -> tuple:
    if duration_min < 5:
        return "时间过短, 无法判断", []

    ae_to_ne_ratio = aerobic_effect / (anaerobic_effect + 0.001)
    # 注意：zone_distribution 和 zone_times 已经是正确的索引（0-6对应Zone 1-7）
    intensity_ratio = max_power / ftp

    rules = [
        {
            "name": "Recovery",
            "conditions": [
                zone_distribution[0] > 85,  # Zone 1
                aerobic_effect < 1.5,
                anaerobic_effect < 0.5,
                duration_min < 90,
            ],
            "required_matches": 3
        },
        {
            "name": "Endurance (LSD)",
            "conditions": [
                zone_distribution[1] > 60,  # Zone 2
                aerobic_effect > 2.5,
                anaerobic_effect < 1.0,
                duration_min >= 90,
                ae_to_ne_ratio > 3.0
            ],
            "required_matches": 4
        },
        {
            "name": "Tempo",
            "conditions": [
                zone_distribution[2] > 40,  # Zone 3
                zone_distribution[3] < 30,  # Zone 4
                aerobic_effect > 2.0,
                anaerobic_effect < 1.5,
                ae_to_ne_ratio > 1.5
            ],
            "required_matches": 4
        },
        {
            "name": "Threshold",
            "conditions": [
                zone_distribution[3] > 35,  # Zone 4
                zone_distribution[4] < 25,  # Zone 5
                aerobic_effect > 3.0,
                anaerobic_effect > 1.0,
                1.0 < ae_to_ne_ratio < 2.5
            ],
            "required_matches": 4
        },
        {
            "name": "VO2Max Intervals",
            "conditions": [
                zone_distribution[4] > 25,  # Zone 5
                zone_times[4] > 8 * 60,  # 至少8分钟在Z5
                anaerobic_effect > 2.5,
                intensity_ratio > 1.3,
                ae_to_ne_ratio < 1.5
            ],
            "required_matches": 4
        },
        {
            "name": "Anaerobic Intervals",
            "conditions": [
                zone_distribution[5] > 15,  # Zone 6
                anaerobic_effect > 3.0,
                intensity_ratio > 1.5,
                ae_to_ne_ratio < 1.0,
                zone_times[5] > 3 * 60  # 至少3分钟在Z6
            ],
            "required_matches": 4
        },
        {
            "name": "Sprint Training",
            "conditions": [
                zone_distribution[6] > 8,  # Zone 7
                anaerobic_effect > 3.5,
                intensity_ratio > 1.8,
                zone_times[6] > 60,  # 至少1分钟在Z7
                ae_to_ne_ratio < 0.5
            ],
            "required_matches": 4
        }
    ]

    # 评估所有规则
    matched_types = []
    for rule in rules:
        matches = sum(1 for cond in rule["conditions"] if cond)
        if matches >= rule["required_matches"]:
            matched_types.append(rule["name"])

    if not matched_types:
        primary_type = "Mixed"
        secondary_type = []
    else:
        primary_type = matched_types[0]
        secondary_type = matched_types[1:]

    return primary_type, secondary_type

# --------------功率相关函数--------------
def calculate_normalized_power(
    powers: list
) -> int:
    window_size = 30
    rolling_averages = []   
    for i in range(len(powers)):
        start_idx = max(0, i - window_size + 1)
        window_powers = powers[start_idx:i+1]
        avg_power = sum(window_powers) / len(window_powers)
        rolling_averages.append(avg_power)
    fourth_powers = [avg ** 4 for avg in rolling_averages]
    mean_fourth_power = sum(fourth_powers) / len(fourth_powers)
    normalized_power = mean_fourth_power ** 0.25
    
    return round(normalized_power, 0)


def calculate_w_balance_decline(
    w_balance_data: list
) -> float:
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


# --------------其他文件中使用到的函数--------------
def get_activity_power_zones(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None

        ftp = int(athlete.ftp)
        
        # 获取流数据
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
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

def get_activity_heartrate_zones(
    db: Session, 
    activity_id: int
) -> Optional[Dict[str, Any]]:
    try:
        activity, athlete = get_activity_athlete(db, activity_id)
        if not activity:
            return None
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        
        # 获取心率数据
        heartrate_data = stream_data.get('heart_rate', [])
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

def get_session_data(
    fit_url: str
) -> Optional[Dict[str, Any]]: # ! 重要函数
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