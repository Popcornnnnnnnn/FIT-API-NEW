"""
Strava 数据分析器

处理从 Strava API 获取的活动数据和流数据，转换为应用内部的数据结构。
"""

from cgi import print_arguments
from typing import Dict, Any, Optional, List, Tuple, Union
import numpy as np
from .schemas import (
    AllActivityDataResponse,
    OverallResponse,
    PowerResponse,
    HeartrateResponse,
    CadenceResponse,
    SpeedResponse,
    TrainingEffectResponse,
    AltitudeResponse,
    TemperatureResponse,
    ZoneData,
)
from .zone_analyzer import ZoneAnalyzer
from ..utils import get_db
from sqlalchemy.orm import Session
from .crud import get_activity_athlete, update_database_field
from ..streams.models import TbActivity, TbAthlete


class StravaAnalyzer:

    @staticmethod
    def analyze_activity_data(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        athlete_data: Dict[str, Any], # ! 暂时没有用到
        external_id: int,
        db: Session,
        keys: Optional[List[str]] = None,
        resolution: str = "high",
    ) -> AllActivityDataResponse:

        # 处理流数据
        streams = None
        if keys and stream_data:
            streams = StravaAnalyzer._extract_stream_data(stream_data, keys, external_id, db, resolution) 

        return AllActivityDataResponse(
            overall         = StravaAnalyzer.analyze_overall(activity_data, stream_data, external_id, db),
            power           = StravaAnalyzer.analyze_power(activity_data, stream_data, external_id, db),
            heartrate       = StravaAnalyzer.analyze_heartrate(activity_data, stream_data),
            cadence         = StravaAnalyzer.analyze_cadence(activity_data, stream_data),
            speed           = StravaAnalyzer.analyze_speed(activity_data, stream_data),
            training_effect = StravaAnalyzer.analyze_training_effect(activity_data, stream_data, external_id, db),
            altitude        = StravaAnalyzer.analyze_altitude(activity_data, stream_data),
            temp            = StravaAnalyzer.analyze_temperature(activity_data, stream_data),
            zones           = StravaAnalyzer.analyze_zones(activity_data, stream_data, external_id, db),
            best_powers     = StravaAnalyzer.analyze_best_powers(activity_data, stream_data),
            streams         = streams,
        )

    @staticmethod
    def analyze_overall(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        external_id: int,
        db: Session
    ) -> Optional[OverallResponse]:
        try:
            return OverallResponse(
                distance       = round(activity_data.get("distance") / 1000, 2),
                moving_time    = ZoneAnalyzer.format_time(int(activity_data.get("moving_time"))),
                average_speed  = round(activity_data.get("average_speed") * 3.6, 1),
                elevation_gain = int(activity_data.get("total_elevation_gain")),
                avg_power      = int(activity_data.get("average_watts")) if activity_data.get("average_watts") else None,
                calories       = int(activity_data.get("calories")),
                training_load  = StravaAnalyzer._get_tss_and_update(stream_data, external_id, db),
                status         = StravaAnalyzer._get_status_from_crud(external_id, db),
                avg_heartrate  = int(activity_data.get("average_heartrate")) if activity_data.get("average_heartrate") else None,
                max_altitude   = int(activity_data.get("elev_high")),
            )
        except Exception as e:
            print(f"分析总体信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_power(
        activity_data: Dict[str, Any], 
        stream_data: Dict[str, Any],
        external_id: int,
        db: Session
    ) -> Optional[PowerResponse]:
        if not stream_data or "watts" not in stream_data:
            return None
        try:
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])
            power_data = [p if p is not None else 0 for p in power_data]

            _, athlete        = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            w_balance_data    = StravaAnalyzer._calculate_w_balance_array(power_data, athlete)
            w_balance_decline = StravaAnalyzer._calculate_w_balance_decline(w_balance_data)

            ftp               = int(athlete.ftp)
            NP                = StravaAnalyzer._calculate_normalized_power(power_data)

            return PowerResponse(
                avg_power              = int(activity_data.get("average_watts")),
                max_power              = int(activity_data.get("max_watts")),
                normalized_power       = NP,
                total_work             = round(activity_data.get("kilojoules"), 0),
                intensity_factor       = round(NP / ftp, 2),
                variability_index      = round((NP / int(activity_data.get("average_watts"))), 2),
                weighted_average_power = int(activity_data.get("weighted_average_watts")),
                work_above_ftp         = StravaAnalyzer._calculate_work_above_ftp(power_data, ftp),
                eftp                   = None,                                                      
                w_balance_decline      = w_balance_decline,                                        # ! 这个接口还没有测试过
            )
        except Exception as e:
            print(f"分析功率信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_heartrate(
        activity_data: Dict[str, Any], 
        stream_data: Dict[str, Any]
    ) -> Optional[HeartrateResponse]:
        if not stream_data or "heartrate" not in stream_data:
            return None
        try:
            if "watts" not in stream_data:
                EF = None
                heartrate_lag = None
                decoupling_rate = None
            else:
                EF = round(activity_data.get("average_watts") / activity_data.get("average_heartrate"), 2)
                heartrate_lag = StravaAnalyzer._calculate_heartrate_lag(stream_data)
                decoupling_rate = StravaAnalyzer._calculate_decoupling_rate(stream_data)

            return HeartrateResponse(
                avg_heartrate           = int(activity_data.get("average_heartrate")),
                max_heartrate           = int(activity_data.get("max_heartrate")),
                heartrate_recovery_rate = StravaAnalyzer._calculate_heartrate_recovery_rate(stream_data),                                                    
                heartrate_lag           = heartrate_lag,                                                    
                efficiency_index        = EF,
                decoupling_rate         = decoupling_rate,  # ! 没有严格比对
            )
        except Exception as e:
            print(f"分析心率信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_cadence(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
    ) -> Optional[CadenceResponse]:
        if "cadence" not in stream_data:
            return None
        try:
            cadence_stream = stream_data.get("cadence", {})
            cadence_data = cadence_stream.get("data", [])
            cadence_data = [c if c is not None else 0 for c in cadence_data]
            return CadenceResponse(
                avg_cadence = int(activity_data.get("average_cadence")),
                max_cadence = max(cadence_data),
                left_right_balance = None,
                left_torque_effectiveness = None,
                right_torque_effectiveness = None,
                left_pedal_smoothness = None,
                right_pedal_smoothness = None,
                total_strokes = int(sum(c / 60 for c in cadence_data if c is not None)),
            )
        except Exception as e:
            print(f"分析踏频信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_speed(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
    ) -> Optional[SpeedResponse]:
        try:
            return SpeedResponse(
                avg_speed = round(activity_data.get("average_speed") * 3.6, 1),
                max_speed = round(activity_data.get("max_speed") * 3.6, 1),
                moving_time = ZoneAnalyzer.format_time(int(activity_data.get("moving_time"))),
                total_time = ZoneAnalyzer.format_time(int(activity_data.get("elapsed_time"))),
                pause_time = ZoneAnalyzer.format_time(int(activity_data.get("elapsed_time")) - int(activity_data.get("moving_time"))),
                coasting_time = ZoneAnalyzer.format_time(StravaAnalyzer._calculate_coasting_time(stream_data)),
            )
        except Exception as e:
            print(f"分析速度信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_training_effect(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session
    ) -> Optional[TrainingEffectResponse]:
        if "watts" not in stream_data:
            return None
        try:
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])
            power_data = [p if p is not None else 0 for p in power_data]
            
            activity, athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)

            aerobic_effect = StravaAnalyzer._calculate_aerobic_effect(power_data, int(athlete.ftp))
            anaerobic_effect = StravaAnalyzer._calculate_anaerobic_effect(power_data, int(athlete.ftp))
            power_zone_percentages = StravaAnalyzer._get_power_zone_percentages(power_data, int(athlete.ftp))
            power_zone_times = StravaAnalyzer._get_power_zone_time(power_data, int(athlete.ftp))

            primary_training_benefit, secondary_training_benefit = StravaAnalyzer._get_primary_training_benefit(
                power_zone_percentages,
                power_zone_times,
                round(len(power_data) / 60, 0),
                aerobic_effect, 
                anaerobic_effect, 
                int(athlete.ftp), 
                int(activity_data.get("max_watts"))
            )

            return TrainingEffectResponse(
                primary_training_benefit = primary_training_benefit,
                aerobic_effect = aerobic_effect,
                anaerobic_effect = anaerobic_effect,
                training_load = StravaAnalyzer._calculate_training_load(stream_data, external_id, db),
                carbohydrate_consumption = int(activity_data.get("calories", 0) / 4.138),
            )
        except Exception as e:
            print(f"分析训练效果信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_altitude(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
    ) -> Optional[AltitudeResponse]:
        if "altitude" not in stream_data:
            return None
        try:
            grade_stream = stream_data.get("grade_smooth", {})
            grade_data = grade_stream.get("data", [])
            grade_data = [g if g is not None else 0 for g in grade_data]

            return AltitudeResponse(
                elevation_gain = int(activity_data.get("total_elevation_gain")),
                max_altitude = int(activity_data.get("elev_high")),
                max_grade = round(max(grade_data), 1),
                total_descent = StravaAnalyzer._calculate_total_descent(stream_data),
                min_altitude = int(activity_data.get("elev_low")),
                uphill_distance = StravaAnalyzer._calculate_uphill_downhill_distance(stream_data)[0],
                downhill_distance = StravaAnalyzer._calculate_uphill_downhill_distance(stream_data)[1],
            )
        except Exception as e:
            print(f"分析海拔信息时出错: {str(e)}")
            return None
        
    @staticmethod
    def analyze_temperature(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
    ) -> Optional[TemperatureResponse]:
        if "temp" not in stream_data:
            return None
        try:
            temp_stream = stream_data.get("temp", {})
            temp_data = temp_stream.get("data", [])
            
            return TemperatureResponse(
                min_temp = int(min(temp_data)),
                max_temp = int(max(temp_data)),
                avg_temp = int(sum(temp_data) / len(temp_data)),
            )
        except Exception as e:
            print(f"分析温度信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_zones( 
        activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session
    ) -> Optional[List[ZoneData]]:
        try:
            activity_athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            if not activity_athlete:
                return None
            
            activity, athlete = activity_athlete
            zones_data = []

            if "watts" in stream_data and int(athlete.ftp) > 0:
                try:
                    ftp = int(athlete.ftp)
                    if ftp > 0:
                        power_stream = stream_data.get("watts", {})
                        power_data = power_stream.get("data", [])
                        power_data = [p if p is not None else 0 for p in power_data]
                        
                        if power_data:
                            from .zone_analyzer import ZoneAnalyzer
                            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
                            
                            if distribution_buckets:
                                zones_data.append(ZoneData(
                                    distribution_buckets=distribution_buckets,
                                    type="power"
                                ))
                except (ValueError, TypeError) as e:
                    print(f"分析功率区间时出错: {str(e)}")
            
            # 分析心率区间（如果有心率数据和最大心率）
            if "heartrate" in stream_data and athlete.max_heartrate:
                try:
                    max_heartrate = int(athlete.max_heartrate)
                    if max_heartrate > 0:
                        heartrate_stream = stream_data.get("heartrate", {})
                        heartrate_data = heartrate_stream.get("data", [])
                        heartrate_data = [hr if hr is not None else 0 for hr in heartrate_data]
                        
                        if heartrate_data:
                            from .zone_analyzer import ZoneAnalyzer
                            distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(heartrate_data, max_heartrate)
                            
                            if distribution_buckets:
                                zones_data.append(ZoneData(
                                    distribution_buckets=distribution_buckets,
                                    type="heartrate"
                                ))
                except (ValueError, TypeError) as e:
                    print(f"分析心率区间时出错: {str(e)}")
            
            return zones_data if zones_data else None           
        except Exception as e:
            print(f"分析区间信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_best_powers(
        activity_data: Dict[str, Any], 
        stream_data: Dict[str, Any]
    ) -> Optional[Dict[str, int]]:
        if "watts" not in stream_data:
            return None
        try:
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])
            power_data = [p if p is not None else 0 for p in power_data]
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
            best_powers = {}
            for interval_name, interval_seconds in time_intervals.items():
                max_avg_power = 0
                if len(power_data) < interval_seconds:
                    continue
                for i in range(len(power_data) - interval_seconds + 1):
                    window_powers = power_data[i:i + interval_seconds]
                    avg_power = sum(window_powers) / len(window_powers)
                    max_avg_power = max(max_avg_power, avg_power)
                if max_avg_power > 0:
                    best_powers[interval_name] = int(max_avg_power)
            return best_powers if best_powers else None         
        except Exception as e:
            print(f"分析最佳功率信息时出错: {str(e)}")
            return None
 
    # ---------------辅助方法（复用 activities/crud.py 中的算法）-----------------

    @staticmethod
    def _calculate_heartrate_recovery_rate(
        stream_data: Dict[str, Any]
    ) -> int:
        heartrate_stream = stream_data.get("heartrate", {})
        heartrate_data = heartrate_stream.get("data", []) if heartrate_stream else []
        if not heartrate_data or len(heartrate_data) < 60:
            return None
        max_drop = 0
        window = 60  # 60秒窗口
        n = len(heartrate_data)
        for i in range(n - window):
            start_hr = heartrate_data[i]
            end_hr = heartrate_data[i + window]
            if start_hr is not None and end_hr is not None:
                drop = start_hr - end_hr
                if drop > max_drop:
                    max_drop = drop
        return int(max_drop) if max_drop > 0 else 0

    @staticmethod
    def _calculate_heartrate_lag(
        stream_data: Dict[str, Any]
    ) -> Optional[int]: # ! 算法设计有问题
        try:
            power_stream = stream_data.get("watts")
            heartrate_stream = stream_data.get("heartrate")
            
            power_data = power_stream.get("data", [])
            power_valid = [p if p is not None else 0 for p in power_data]
            power_array = np.array(power_valid)

            heartrate_data = heartrate_stream.get("data", [])
            heartrate_valid = [h if h is not None else 0 for h in heartrate_data]
            heartrate_array = np.array(heartrate_valid)

            power_norm = power_array - np.mean(power_array)
            heartrate_norm = heartrate_array - np.mean(heartrate_array)

            correlation = np.correlate(power_norm, heartrate_norm, mode='full')

            # 找到最大相关点对应的滞后时间
            lag_max = np.argmax(correlation) - (len(power_array) - 1)

            # 如果最佳相关系数太低，认为没有明显的滞后关系
            max_corr = np.max(correlation)
            if max_corr < 0.3 * len(power_array):  # 调整阈值
                return None

            return int(abs(lag_max))
        except Exception as e:
            print(f"计算心率滞后时出错: {str(e)}")
            return None
    

    def _calculate_coasting_time(stream_data: Dict[str, Any]) -> int:
        try:
            speed_data = stream_data.get("velocity_smooth").get("data", [])
            watts_stream = stream_data.get("watts")
            power_data = watts_stream.get("data", []) if watts_stream else []

            speed_data = [s if s is not None else 0.0 for s in speed_data]
            power_data = [p if p is not None else 0.0 for p in power_data]

            coasting_seconds = 0
            for i in range(len(speed_data)):

                if speed_data[i] < 0.27778 or (power_data is not None and power_data[i] < 10):
                    coasting_seconds += 1

            return coasting_seconds
        except Exception:
            return 0

    @staticmethod
    def _calculate_normalized_power(powers: list) -> int:

        window_size = 30
        rolling_averages = []

        for i in range(len(powers)): 
            start_idx = max(0, i - window_size + 1)
            window_powers = powers[start_idx : i + 1]
            avg_power = sum(window_powers) / len(window_powers)
            rolling_averages.append(avg_power)

        fourth_powers = [avg**4 for avg in rolling_averages]
        mean_fourth_power = sum(fourth_powers) / len(fourth_powers)
        normalized_power = mean_fourth_power**0.25
        return int(normalized_power)

    @staticmethod
    def _calculate_work_above_ftp(powers: list, ftp: float) -> int:

        work_above_ftp = 0
        for power in powers:
            if power > ftp:
                work_above_ftp += power - ftp  # (W - FTP) * 时间（假设1秒）

        work_above_ftp_kj = work_above_ftp / 1000  # 转换为千焦
        return int(work_above_ftp_kj)

    @staticmethod
    def _calculate_total_descent(stream_data: Dict[str, Any]) -> int:
        try:
            altitude_stream = stream_data.get("altitude", {})
            altitude_data = altitude_stream.get("data", [])
            altitude_data = [a if a is not None else 0 for a in altitude_data]

            total_descent = 0
            descending = False
            start_altitude = altitude_data[0]
            min_altitude = altitude_data[0]

            for i in range(1, len(altitude_data)):
                prev = altitude_data[i - 1]
                curr = altitude_data[i]
                if curr < prev:
                    # 下降中
                    if not descending:
                        # 新的下降段开始
                        descending = True
                        start_altitude = prev
                        min_altitude = curr
                    else:
                        # 继续下降，更新最低点
                        if curr < min_altitude:
                            min_altitude = curr
                else:
                    # 上升或持平，下降段结束
                    if descending:
                        # 结束下降段，累加
                        total_descent += start_altitude - min_altitude
                        descending = False
            # 如果最后是下降段结尾
            if descending:
                total_descent += start_altitude - min_altitude

            return int(total_descent)
        except Exception as e:
            print(f"计算总下降时出错: {str(e)}")
            return None

    @staticmethod
    def _calculate_uphill_downhill_distance(
        stream_data: Dict[str, Any]
    ) -> (float, float):
        try:
            altitude_stream = stream_data.get("altitude", {})
            distance_stream = stream_data.get("distance", {})
            altitude_data = altitude_stream.get("data", [])
            distance_data = distance_stream.get("data", [])

            if not altitude_data or not distance_data or len(altitude_data) != len(distance_data):
                return 0.0, 0.0

            uphill_distance = 0.0
            downhill_distance = 0.0
            
            # 使用间隔更多的点计算上下坡距离，提高数据准确性
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
                    
                    # 如果是下坡（海拔减少）且距离间隔合理，累加下坡距离
                    elif altitude_diff < -1 and distance_diff > min_distance_interval:
                        downhill_distance += distance_diff

            # 转换为千米并保留两位小数
            return round(uphill_distance / 1000, 2), round(downhill_distance / 1000, 2)
        except Exception as e:
            print(f"计算上坡/下坡距离时出错: {str(e)}")
            return 0.0, 0.0
        
    @staticmethod
    def _calculate_w_balance_decline(
        w_balance_data: list
    ) -> Optional[float]:
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

    @staticmethod
    def _calculate_w_balance_array(
        power_data: list, 
        athlete_info: TbAthlete
    ) -> list:
        try:
            W_prime = athlete_info.w_balance
            CP = int(athlete_info.ftp)

            dt = 1.0  
            tau = 546.0  # 恢复时间常数（秒），约9分钟
            balance = W_prime  # 初始储备
            w_balance = []
            for p in power_data:
                if p is None:
                    p = 0
                if p > CP * 1.05:  
                    balance -= (p - CP) * dt
                elif p < CP * 0.95:  
                    recovery = (W_prime - balance) * (dt / tau)
                    balance += recovery
                balance = max(0.0, min(W_prime, balance))  # 限定范围
                w_balance.append(round(balance / 1000, 1))  # 转换为千焦，保留一位小数
            return w_balance
        except Exception as e:
            print(f"计算 W' 平衡数组时出错: {str(e)}")
            return []

    @staticmethod
    def _calculate_decoupling_rate(
        stream_data: Dict[str, Any]
    ) -> Optional[str]:
        if "watts" not in stream_data:
            return None
        try:
            
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])

            heartrate_stream = stream_data.get("heartrate", {})
            heartrate_data = heartrate_stream.get("data", [])

            heartrate_valid = [h if h is not None else 0 for h in heartrate_data]
            power_valid = [p if p is not None else 0 for p in power_data]

            # 将数据分为前半部分和后半部分
            mid_point = len(power_data) // 2

            first_half_powers = power_valid[:mid_point]
            first_half_hr = heartrate_valid[:mid_point]
            second_half_powers = power_valid[mid_point:]
            second_half_hr = heartrate_valid[mid_point:]

            r1 = (sum(first_half_powers) / len(first_half_powers)) / (sum(first_half_hr) / len(first_half_hr))
            r2 = (sum(second_half_powers) / len(second_half_powers)) / (sum(second_half_hr) / len(second_half_hr))
            decoupling_rate = r1 - r2
            decoupling_percentage = (decoupling_rate / r1) * 100
            
            # 如果解耦率超过±30%，返回None
            if abs(decoupling_percentage) > 30:
                return None
                
            return f"{round(decoupling_percentage, 1)}%"

        except Exception as e:
            return None

    @staticmethod
    def _get_activity_athlete_by_external_id(
        db: Session, external_id: int
    ) -> Optional[Tuple[TbActivity, TbAthlete]]:
        try:
            activity = db.query(TbActivity).filter(TbActivity.external_id == external_id).first()
            if not activity:
                print(f"未找到 external_id 为 {external_id} 的活动")
                return None
                
            # 检查athlete_id是否存在
            if not hasattr(activity, 'athlete_id') or activity.athlete_id is None:
                print(f"活动 {external_id} 的athlete_id为空")
                return None
                
            athlete = (
                db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
            )
            if not athlete:
                print(f"未找到 athlete_id 为 {activity.athlete_id} 的运动员")
                return None

            return activity, athlete
        except Exception as e:
            print(f"根据 external_id 查询活动和运动员信息时出错: {str(e)}")
            return None

    @staticmethod
    def _calculate_training_load(
        stream_data: Dict[str, Any], 
        external_id: int, 
        db: Session
    ) -> Optional[int]:
        power_stream = stream_data.get("watts", {})
        if not power_stream:
            return None
        try:
            power_data = power_stream.get("data", [])
            power_data = [p if p is not None else 0 for p in power_data]
            activity, athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            ftp = int(athlete.ftp)

            np = StravaAnalyzer._calculate_normalized_power(power_data)
            intensity_factor = np / ftp
            tss = (len(power_data) * np * intensity_factor) / (ftp * 3600) * 100
            return int(round(tss, 0))
        except Exception as e:
            print(f"计算训练负荷时出错: {str(e)}")
            return None

    @staticmethod
    def _get_tss_and_update(
        stream_data: Dict[str, Any],
        external_id: int,   
        db: Session
    ) -> Optional[int]:
        if "watts" not in stream_data:
            return None
        try:
            activity, athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            if not activity or not athlete:
                return None
            if activity.tss_updated == 0:
                tss = StravaAnalyzer._calculate_training_load(stream_data, external_id, db)
                update_database_field(db, TbActivity, activity.id, "tss", tss)
                ctl = athlete.ctl
                atl = athlete.atl
                new_ctl = ctl + (tss - ctl) / 42
                new_atl = atl + (tss - atl) / 7
                update_database_field(db, TbAthlete, activity.athlete_id, "ctl", round(new_ctl, 0))
                update_database_field(db, TbAthlete, activity.athlete_id, "atl", round(new_atl, 0))
                update_database_field(db, TbActivity, activity.id, "tss_updated", 1)
                update_database_field(db, TbAthlete, activity.athlete_id, "tsb", round(new_atl - new_ctl, 0))
                return tss
            else:
                return activity.tss

        except Exception as e:
            print(f"更新TSS时出错: {str(e)}")
            return None

    @staticmethod
    def _get_status(
        external_id: int,
        db: Session
    ) -> Optional[int]:
        try:
            activity, athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            if not activity or not athlete:
                return None
            return athlete.tsb
        except Exception as e:
            print(f"获取状态时出错: {str(e)}")
            return None

    @staticmethod
    def _get_status_from_crud(
        external_id: int,
        db: Session
    ) -> Optional[int]:
        try:
            # 根据 external_id 获取 activity 对象
            activity, _ = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            if not activity:
                return None
            
            # 导入并调用 crud.py 中的 get_status 函数
            from .crud import get_status
            status = get_status(db, activity.id)
            print(status)
            if status:
                return status['ctl'] - status['atl']
            else:
                return None
                
        except Exception as e:
            print(f"从 crud 获取状态时出错: {str(e)}")
            return None

    @staticmethod
    def _calculate_aerobic_effect(
        power_data: list,
        ftp: int
    ) -> float:
        try:
            np = StravaAnalyzer._calculate_normalized_power(power_data)
            intensity_factor = np / ftp
            return round(min(5.0, intensity_factor * len(power_data) / 3600 + 0.5), 1)
        except Exception as e:
            print(f"计算有氧效果时出错: {str(e)}")
            return 0.0

    @staticmethod
    def _calculate_anaerobic_effect(
        power_data: list,
        ftp: int
    ) -> float:
        try:
            peak_power_30s = max([sum(power_data[i:i + 30]) / 30 for i in range(len(power_data) - 30)])
            anaerobic_capacity = sum([max(0, p - ftp) for p in power_data if p > ftp]) / 1000
            anaerobic_effect = min(4.0, 0.1 * (peak_power_30s / ftp) + 0.05 * anaerobic_capacity)
            return round(anaerobic_effect, 1)
        except Exception as e:
            print(f"计算无氧效果时出错: {str(e)}")
            return 0.0
        

    @staticmethod
    def _get_power_zone_percentages(
        power_data: list,
        ftp: int
    ) -> list:
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

    @staticmethod
    def _get_power_zone_time(
        power_data: list,
        ftp: int
    ) -> list:
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

    @staticmethod
    def _get_primary_training_benefit(
        zone_distribution: list,
        zone_times: list,
        duration_min: int,
        aerobic_effect: float,
        anaerobic_effect: float,
        ftp: int,
        max_power: int,
    ) -> Dict[str, Any]:
        if duration_min < 5:
            return "时间过短, 无法判断"

        ae_to_ne_ratio = aerobic_effect / (anaerobic_effect + 0.001)
        zone_distribution = [0.0] + zone_distribution
        zone_times = [0] + zone_times
        intensity_ratio = max_power / ftp

        rules = [
            {
                "name": "Recovery",
                "conditions": [
                    zone_distribution[1] > 85,
                    aerobic_effect < 1.5,
                    anaerobic_effect < 0.5,
                    duration_min < 90,
                ],
                "required_matches": 3
            },
            {
                "name": "Endurance (LSD)",
                "conditions": [
                    zone_distribution[2] > 60,
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
                    zone_distribution[3] > 40,
                    zone_distribution[4] < 30,
                    aerobic_effect > 2.0,
                    anaerobic_effect < 1.5,
                    ae_to_ne_ratio > 1.5
                ],
                "required_matches": 4
            },
            {
                "name": "Threshold",
                "conditions": [
                    zone_distribution[4] > 35,
                    zone_distribution[5] < 25,
                    aerobic_effect > 3.0,
                    anaerobic_effect > 1.0,
                    1.0 < ae_to_ne_ratio < 2.5
                ],
                "required_matches": 4
            },
            {
                "name": "VO2Max Intervals",
                "conditions": [
                    zone_distribution[5] > 25,
                    zone_times[5] > 8 * 60,  # 至少8分钟在Z5
                    anaerobic_effect > 2.5,
                    intensity_ratio > 1.3,
                    ae_to_ne_ratio < 1.5
                ],
                "required_matches": 4
            },
            {
                "name": "Anaerobic Intervals",
                "conditions": [
                    zone_distribution[6] > 15,
                    anaerobic_effect > 3.0,
                    intensity_ratio > 1.5,
                    ae_to_ne_ratio < 1.0,
                    zone_times[6] > 3 * 60  # 至少3分钟在Z6
                ],
                "required_matches": 4
            },
            {
                "name": "Sprint Training",
                "conditions": [
                    zone_distribution[7] > 8,
                    anaerobic_effect > 3.5,
                    intensity_ratio > 1.8,
                    zone_times[7] > 60,  # 至少1分钟在Z7
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

    @staticmethod
    def _extract_stream_data(
        stream_data: Dict[str, Any],
        keys: List[str],
        external_id: int,
        db: Session,
        resolution: str = "high",
    ) -> Optional[List[Dict[str, Any]]]:
        if not stream_data or not keys:
            return None
        result = []
        
        # 直接使用 Strava API 字段名
        for field in keys:
            if field == 'velocity_smooth': # ! 特别处理一下这里
                stream_item = stream_data['velocity_smooth']
                if isinstance(stream_item, dict) and 'data' in stream_item:
                    raw_data = stream_item['data']
                    speed_data = [round(v * 3.6, 1) if v is not None else 0 for v in raw_data]
                    # 根据 resolution 重新采样
                    resampled_data = StravaAnalyzer._resample_strava_data(speed_data, resolution)
                    result.append({
                        'type': 'speed',
                        'data': resampled_data,
                        'series_type': stream_item.get('series_type', 'time'),
                        'original_size': len(speed_data),
                        'resolution': resolution
                    })
                continue
            if field in stream_data:
                stream_item = stream_data[field]
                if isinstance(stream_item, dict) and 'data' in stream_item:
                    raw_data = stream_item['data']
                    # 根据 resolution 重新采样
                    resampled_data = StravaAnalyzer._resample_strava_data(raw_data, resolution)
                    # 返回新的数组格式
                    result.append({
                        'type': field,
                        'data': resampled_data,
                        'series_type': stream_item.get('series_type', 'time'),
                        'original_size': stream_item.get('original_size', len(raw_data)),
                        'resolution': resolution
                    })
            elif field in ['latitude', 'longitude'] and 'latlng' in stream_data:
                # 对于经纬度，需要从 latlng 数组中提取对应的值
                stream_item = stream_data['latlng']
                if isinstance(stream_item, dict) and 'data' in stream_item:
                    latlng_data = stream_item['data']
                    if field == 'latitude':
                        extracted_data = [point[0] if point and len(point) >= 2 else None for point in latlng_data]
                    else:  # longitude
                        extracted_data = [point[1] if point and len(point) >= 2 else None for point in latlng_data]
                    
                    # 根据 resolution 重新采样
                    resampled_data = StravaAnalyzer._resample_strava_data(extracted_data, resolution)
                    result.append({
                        'type': field,
                        'data': resampled_data,
                        'series_type': stream_item.get('series_type', 'time'),
                        'original_size': stream_item.get('original_size', len(extracted_data)),
                        'resolution': resolution
                    })
            elif field == 'best_power':
                # 计算最佳功率数据
                if 'watts' in stream_data:
                    watts_data = stream_data['watts'].get('data', [])
                    if watts_data:
                        best_powers = StravaAnalyzer._calculate_best_powers_from_stream(watts_data)
                        # 根据 resolution 重新采样
                        resampled_data = StravaAnalyzer._resample_strava_data(best_powers, resolution)
                        result.append({
                            'type': field,
                            'data': resampled_data,
                            'series_type': 'time',
                            'original_size': len(best_powers),
                            'resolution': resolution
                        })
            elif field == 'torque':
                # 计算扭矩数据（功率/踏频）
                if 'watts' in stream_data and 'cadence' in stream_data:
                    watts_data = stream_data['watts'].get('data', [])
                    cadence_data = stream_data['cadence'].get('data', [])
                    if watts_data and cadence_data:
                        torque_data = []
                        for i in range(min(len(watts_data), len(cadence_data))):
                            if watts_data[i] is not None and cadence_data[i] is not None and cadence_data[i] > 0:
                                torque = watts_data[i] / (cadence_data[i] * 2 * 3.1415926 / 60)
                                torque_data.append(round(torque, 2))
                            else:
                                torque_data.append(None)
                        # 根据 resolution 重新采样
                        resampled_data = StravaAnalyzer._resample_strava_data(torque_data, resolution)
                        result.append({
                            'type': field,
                            'data': resampled_data,
                            'series_type': 'distance',
                            'original_size': len(torque_data),
                            'resolution': resolution
                        })
            elif field == 'spi':
                # 计算 SPI (Speed Power Index) - 速度功率指数（功率/踏频）
                if 'watts' in stream_data and 'cadence' in stream_data:
                    watts_data = stream_data['watts'].get('data', [])
                    cadence_data = stream_data['cadence'].get('data', [])
                    if watts_data and cadence_data:
                        spi_data = []
                        for i in range(min(len(watts_data), len(cadence_data))):
                            if watts_data[i] is not None and cadence_data[i] is not None and cadence_data[i] > 0:
                                spi = watts_data[i] / cadence_data[i]
                                spi_data.append(round(spi, 2))
                            else:
                                spi_data.append(None)
                        # 根据 resolution 重新采样
                        resampled_data = StravaAnalyzer._resample_strava_data(spi_data, resolution)
                        result.append({
                            'type': field,
                            'data': resampled_data,
                            'series_type': 'distance',
                            'original_size': len(spi_data),
                            'resolution': resolution
                        })
            elif field == 'power_hr_ratio':
                # 计算功率心率比
                if 'watts' in stream_data and 'heartrate' in stream_data:
                    watts_data = stream_data['watts'].get('data', [])
                    hr_data = stream_data['heartrate'].get('data', [])
                    if watts_data and hr_data:
                        ratio_data = []
                        for i in range(min(len(watts_data), len(hr_data))):
                            if watts_data[i] is not None and hr_data[i] is not None and hr_data[i] > 0:
                                ratio = watts_data[i] / hr_data[i]
                                ratio_data.append(round(ratio, 2))
                            else:
                                ratio_data.append(None)
                        # 根据 resolution 重新采样
                        resampled_data = StravaAnalyzer._resample_strava_data(ratio_data, resolution)
                        result.append({
                            'type': field,
                            'data': resampled_data,
                            'series_type': 'time',
                            'original_size': len(ratio_data),
                            'resolution': resolution
                        })
            elif field == 'w_balance':
                # 计算 W平衡数据
                if 'watts' in stream_data:
                    watts_data = stream_data['watts'].get('data', [])
                    if watts_data:
                        try:
                            _, athlete_info = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
                            w_balance_data = StravaAnalyzer._calculate_w_balance_array(watts_data, athlete_info)
                            # 根据 resolution 重新采样
                            resampled_data = StravaAnalyzer._resample_strava_data(w_balance_data, resolution)
                            result.append({
                                'type': field,
                                'data': resampled_data,
                                'series_type': 'time',
                                'original_size': len(w_balance_data),
                                'resolution': resolution
                            })
                        except Exception:
                            pass
            elif field == 'vam': # ! VAM的计算还是不太准
                # 计算 VAM (Vertical Ascent in Meters per hour) - 垂直爬升速度
                if 'altitude' in stream_data and 'time' in stream_data:
                    altitude_data = stream_data['altitude'].get('data', [])
                    time_data = stream_data['time'].get('data', [])
                    if altitude_data and time_data and len(altitude_data) > 1 and len(time_data) > 1:
                        vam = []
                        window_seconds = 50  # 50秒滑动窗口
                        
                        for i in range(len(time_data)):
                            try:
                                # 找到窗口起点
                                t_end = time_data[i]
                                t_start = t_end - window_seconds
                                
                                # 找到窗口内的起始点
                                idx_start = None
                                for j in range(i, -1, -1):
                                    if time_data[j] <= t_start:
                                        idx_start = j
                                        break
                                
                                # 计算VAM
                                if idx_start is None:
                                    # 对于数据不足的点，使用从开始到当前点的数据
                                    if i >= window_seconds:
                                        delta_alt = altitude_data[i] - altitude_data[i-window_seconds]
                                        delta_time = time_data[i] - time_data[i-window_seconds]
                                        if delta_time >= window_seconds * 0.7:  # 至少70%的时间窗口
                                            vam_value = delta_alt / (delta_time / 3600.0)
                                        else:
                                            vam_value = 0.0
                                    else:
                                        vam_value = 0.0
                                elif idx_start == i:
                                    vam_value = 0.0
                                else:
                                    delta_alt = altitude_data[i] - altitude_data[idx_start]
                                    delta_time = time_data[i] - time_data[idx_start]
                                    if delta_time >= window_seconds * 0.5:  # 至少50%的时间窗口
                                        vam_value = delta_alt / (delta_time / 3600.0)
                                    else:
                                        vam_value = 0.0
                                
                                vam.append(int(round(vam_value * 1.4)))  # 保留到整数，乘以1.4是经验值
                            except Exception as e:
                                vam.append(0)
                        
                        # 过滤VAM异常值，超过5000或低于-5000的设为0
                        vam = [v if -5000 <= v <= 5000 else 0 for v in vam]
                        
                        # 根据 resolution 重新采样
                        resampled_data = StravaAnalyzer._resample_strava_data(vam, resolution)
                        result.append({
                            'type': field,
                            'data': resampled_data,
                            'series_type': 'distance',
                            'original_size': len(vam),
                            'resolution': resolution
                        })
        
        return result if result else None

    @staticmethod
    def _resample_strava_data(
        data: List[Union[int, float, None]], 
        resolution: str
    ) -> List[Union[int, float, None]]:
        """
        根据 resolution 参数重新采样 Strava API 返回的高分辨率数据
        
        Args:
            data: 原始高分辨率数据
            resolution: 目标分辨率 ('low', 'medium', 'high')
            
        Returns:
            重新采样后的数据
        """
        if not data:
            return []
        
        original_size = len(data)
        
        if resolution == "high":
            return data
        elif resolution == "medium":
            # 中等分辨率：保留25%的数据点
            target_size = max(1, int(original_size * 0.25))
            step = max(1, original_size // target_size)
            result = data[::step]
            return result[:target_size]
        elif resolution == "low":
            # 低分辨率：保留5%的数据点
            target_size = max(1, int(original_size * 0.05))
            step = max(1, original_size // target_size)
            result = data[::step]
            return result[:target_size]
        else:
            # 默认返回高分辨率
            return data

    @staticmethod
    def _calculate_best_powers_from_stream(
        watts_data: List[Union[float, int]]
    ) -> List[Union[float, int]]:
        if not watts_data:
            return []
        
        # 过滤掉 None 值
        valid_watts = [w if w is not None else 0 for w in watts_data]
        n = len(valid_watts)
        if n == 0:
            return []
        
        best_powers = []
        for window in range(1, n + 1):
            max_avg = 0
            if n >= window:
                # 计算第一个窗口的和
                window_sum = sum(valid_watts[:window])
                max_avg = window_sum / window
                for i in range(1, n - window + 1):
                    window_sum = window_sum - valid_watts[i - 1] + valid_watts[i + window - 1]
                    avg = window_sum / window
                    if avg > max_avg:
                        max_avg = avg
            best_powers.append(int(round(max_avg)))
        return best_powers