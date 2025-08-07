"""
Strava 数据分析器

处理从 Strava API 获取的活动数据和流数据，转换为应用内部的数据结构。
"""

from typing import Dict, Any, Optional, List, Tuple
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
from .crud import get_activity_athlete
from ..streams.models import TbActivity, TbAthlete


class StravaAnalyzer:
    """Strava 数据分析器"""

    # 类级别变量存储 FTP 信息
    _ftp: Optional[int] = None

    @staticmethod
    def analyze_activity_data(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        athlete_data: Dict[str, Any],
        external_id: int,
        db: Session,
    ) -> AllActivityDataResponse:
        StravaAnalyzer._set_ftp(athlete_data)

        return AllActivityDataResponse(
            overall         = StravaAnalyzer.analyze_overall(activity_data),
            power           = StravaAnalyzer.analyze_power(activity_data, stream_data),
            heartrate       = StravaAnalyzer.analyze_heartrate(activity_data, stream_data),
            cadence         = StravaAnalyzer.analyze_cadence(activity_data, stream_data),
            speed           = StravaAnalyzer.analyze_speed(activity_data, stream_data),
            training_effect = StravaAnalyzer.analyze_training_effect(activity_data),
            altitude        = StravaAnalyzer.analyze_altitude(activity_data, stream_data),
            temp            = StravaAnalyzer.analyze_temperature(activity_data, stream_data),
            zones           = StravaAnalyzer.analyze_zones(activity_data, stream_data),
            best_powers     = StravaAnalyzer.analyze_best_powers(activity_data, stream_data),
        )


    @staticmethod
    def analyze_overall(
        activity_data: Dict[str, Any]
        ) -> Optional[OverallResponse]:
        try:
            return OverallResponse(
                distance       = round(activity_data.get("distance") / 1000, 2),
                moving_time    = ZoneAnalyzer.format_time(int(activity_data.get("moving_time"))),
                average_speed  = round(activity_data.get("average_speed") * 3.6, 1),
                elevation_gain = int(activity_data.get("total_elevation_gain")),
                avg_power      = int(activity_data.get("average_watts", 0)),
                calories       = int(activity_data.get("calories", 0)),
                training_load  = 0,
                status         = None,
                avg_heartrate  = int(activity_data.get("average_heartrate", 0)),
                max_altitude   = int(activity_data.get("elev_high", 0)),
            )
        except Exception as e:
            print(f"分析总体信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_power(
        activity_data: Dict[str, Any], 
        stream_data: Dict[str, Any]
        ) -> Optional[PowerResponse]:
        if not stream_data or "watts" not in stream_data:
            return None
        try:
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])
            power_data = [p if p is not None else 0 for p in power_data]

            ftp               = StravaAnalyzer._get_ftp()
            # w_balance_decline = StravaAnalyzer._calculate_w_balance_decline_from_strava(stream_data, external_id, db)
            NP                = StravaAnalyzer._calculate_normalized_power(power_data)
            
            return PowerResponse(
                avg_power              = int(activity_data.get("average_watts")),
                max_power              = int(activity_data.get("max_watts")),
                normalized_power       = NP,
                total_work             = round(activity_data.get("kilojoules"), 0),
                intensity_factor       = round(NP / ftp, 2),
                variability_index      = round((NP / activity_data.get("average_watts")), 2),
                weighted_average_power = int(activity_data.get("weighted_average_watts")),
                work_above_ftp         = StravaAnalyzer._calculate_work_above_ftp(power_data, ftp),
                eftp                   = None,                                                      
                w_balance_decline      = None,                                         # ! 这个接口还没有测试过
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
            else:
                EF = round(activity_data.get("average_watts") / activity_data.get("average_heartrate"), 2)

            return HeartrateResponse(
                avg_heartrate           = int(activity_data.get("average_heartrate")),
                max_heartrate           = int(activity_data.get("max_heartrate")),
                heartrate_recovery_rate = None,                                                    # 需要特殊算法
                heartrate_lag           = None,                                                    # 需要特殊算法
                efficiency_index        = EF,
                decoupling_rate         = StravaAnalyzer._calculate_decoupling_rate(stream_data),  # ! 没有严格比对
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
        activity_data: Dict[str, Any]
    ) -> Optional[TrainingEffectResponse]:
        """
        分析训练效果信息

        Args:
            activity_data: Strava API 返回的活动数据

        Returns:
            Optional[TrainingEffectResponse]: 训练效果信息响应
        """
        # TODO: 实现训练效果信息分析逻辑
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
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
    ) -> Optional[List[ZoneData]]:
        """
        分析区间信息

        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据

        Returns:
            Optional[List[ZoneData]]: 区间信息响应
        """
        # TODO: 实现区间信息分析逻辑
        return None

    @staticmethod
    def analyze_best_powers(
        activity_data: Dict[str, Any], stream_data: Dict[str, Any]
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

    # 辅助方法（复用 activities/crud.py 中的算法）

    @staticmethod
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
    def _calculate_uphill_downhill_distance(stream_data: Dict[str, Any]) -> (float, float):
        """
        同时计算上升段和下降段的距离（单位：千米）

        Args:
            stream_data: 包含"altitude"和"distance"流的字典

        Returns:
            (float, float): (上升段距离, 下降段距离)，单位为千米，均保留两位小数
        """
        try:
            altitude_stream = stream_data.get("altitude", {})
            distance_stream = stream_data.get("distance", {})
            altitude_data = altitude_stream.get("data", [])
            distance_data = distance_stream.get("data", [])

            if not altitude_data or not distance_data or len(altitude_data) != len(distance_data):
                return 0.0, 0.0

            uphill_distance = 0.0
            downhill_distance = 0.0
            in_uphill = False
            in_downhill = False
            start_uphill_distance = 0.0
            start_downhill_distance = 0.0

            for i in range(1, len(altitude_data)):
                prev_alt = altitude_data[i - 1] if altitude_data[i - 1] is not None else 0
                curr_alt = altitude_data[i] if altitude_data[i] is not None else 0
                prev_dist = distance_data[i - 1] if distance_data[i - 1] is not None else 0
                curr_dist = distance_data[i] if distance_data[i] is not None else 0

                # 上升段逻辑
                if curr_alt > prev_alt:
                    if not in_uphill:
                        in_uphill = True
                        start_uphill_distance = prev_dist
                    # 下降段结束
                    if in_downhill:
                        downhill_distance += prev_dist - start_downhill_distance
                        in_downhill = False
                # 下降段逻辑
                elif curr_alt < prev_alt:
                    if not in_downhill:
                        in_downhill = True
                        start_downhill_distance = prev_dist
                    # 上升段结束
                    if in_uphill:
                        uphill_distance += prev_dist - start_uphill_distance
                        in_uphill = False
                else:
                    # 持平，两个段都结束
                    if in_uphill:
                        uphill_distance += prev_dist - start_uphill_distance
                        in_uphill = False
                    if in_downhill:
                        downhill_distance += prev_dist - start_downhill_distance
                        in_downhill = False

            # 如果最后是上升段结尾
            if in_uphill:
                uphill_distance += distance_data[-1] - start_uphill_distance
            # 如果最后是下降段结尾
            if in_downhill:
                downhill_distance += distance_data[-1] - start_downhill_distance

            return round(uphill_distance / 1000, 1), round(downhill_distance / 1000, 1)
        except Exception as e:
            print(f"计算上坡/下坡距离时出错: {str(e)}")
            return 0.0, 0.0
        




    @staticmethod
    def _calculate_w_balance_decline_from_strava(
        stream_data: Dict[str, Any], external_id: int, db: Session
    ) -> Optional[float]:
        """
        从 Strava 流数据计算 W 平衡下降
        使用功率数据和数据库中的运动员信息计算 W' 平衡数组，然后计算下降值

        Args:
            stream_data: Strava API 返回的流数据
            external_id: Strava 的 external_id
            db: 数据库会话

        Returns:
            Optional[float]: W平衡下降值（保留一位小数），如果无法计算则返回 None
        """
        try:

            power_stream = stream_data.get("watts", {}) if stream_data else {}
            power_data = power_stream.get("data", []) if power_stream else []

            if not power_data:
                return None

            # 从数据库获取运动员信息
            # 注意：这里的 external_id 是 Strava 的 external_id
            activity_athlete = StravaAnalyzer._get_activity_athlete_by_external_id(
                db, external_id
            )

            if not activity_athlete:
                return None

            activity, athlete = activity_athlete
            if not athlete or not athlete.ftp or not athlete.w_balance:
                return None

            # 准备运动员信息
            athlete_info = {
                "ftp": int(athlete.ftp),
                "wj": athlete.w_balance,  # 无氧储备（焦耳）
            }

            # 计算 W' 平衡数组（参考 fit_parser.py 的算法）
            w_balance_array = StravaAnalyzer._calculate_w_balance_array(
                power_data, athlete_info
            )

            if w_balance_array:
                return StravaAnalyzer._calculate_w_balance_decline(w_balance_array)
            else:
                return None

        except Exception as e:
            print(f"计算 W 平衡下降时出错: {str(e)}")
            return None

    @staticmethod
    def _calculate_w_balance_decline(w_balance_data: list) -> Optional[float]:
        """
        计算W平衡下降（复用 activities/crud.py 中的算法）

        Args:
            w_balance_data: W平衡数据列表

        Returns:
            Optional[float]: W平衡下降值（保留一位小数）
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

    @staticmethod
    def _calculate_w_balance_array(
        power_data: list, athlete_info: Dict[str, Any]
    ) -> list:
        """
        计算 W' 平衡数组（复用 fit_parser.py 中的算法）

        Args:
            power_data: 功率数据列表
            athlete_info: 运动员信息，包含 ftp 和 wj 字段

        Returns:
            list: W' 平衡数组（千焦，保留一位小数）
        """
        try:
            if (
                not power_data
                or not athlete_info.get("ftp")
                or not athlete_info.get("wj")
            ):
                return []

            W_prime = athlete_info["wj"]  # 无氧储备（焦耳）
            CP = int(athlete_info["ftp"])  # 功能阈值功率

            dt = 1.0  # 时间间隔（秒）
            # 使用标准的 Skiba 模型参数
            tau = 546.0  # 恢复时间常数（秒），约9分钟

            balance = W_prime  # 初始储备
            w_balance = []

            for p in power_data:
                if p is None:
                    p = 0

                # 简化计算：只有当功率明显高于 FTP 时才消耗 W'
                # 当功率低于 FTP 时，W' 会缓慢恢复
                if p > CP * 1.05:  # 功率超过 FTP 的 105% 时才消耗
                    # 消耗：线性损耗
                    balance -= (p - CP) * dt
                elif p < CP * 0.95:  # 功率低于 FTP 的 95% 时恢复
                    # 恢复：缓慢恢复
                    recovery = (W_prime - balance) * (dt / tau)
                    balance += recovery
                # 在 FTP 附近时，W' 基本保持不变

                balance = max(0.0, min(W_prime, balance))  # 限定范围
                w_balance.append(round(balance / 1000, 1))  # 转换为千焦，保留一位小数

            return w_balance

        except Exception as e:
            print(f"计算 W' 平衡数组时出错: {str(e)}")
            return []

    @staticmethod
    def _calculate_decoupling_rate(stream_data: Dict[str, Any]) -> Optional[str]:
        if "watts" not in stream_data:
            return None
        try:
            
            power_stream = stream_data.get("watts", {})
            power_data = power_stream.get("data", [])

            heartrate_stream = stream_data.get("heartrate", {})
            heartrate_data = heartrate_stream.get("data", [])

            # 将数据分为前半部分和后半部分
            mid_point = len(power_data) // 2

            first_half_powers = power_data[:mid_point]
            first_half_hr = heartrate_data[:mid_point]
            second_half_powers = power_data[mid_point:]
            second_half_hr = heartrate_data[mid_point:]

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
                second_half_avg_power = sum(second_half_powers) / len(
                    second_half_powers
                )
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

    # FTP 相关方法

    @classmethod
    def _set_ftp(cls, athlete_data: Dict[str, Any]) -> None:
        """
        从运动员数据中设置 FTP 值

        Args:
            athlete_data: Strava API 返回的运动员数据
        """
        try:
            ftp = athlete_data.get("ftp")
            if ftp is not None:
                cls._ftp = int(ftp)
            else:
                cls._ftp = None
        except Exception as e:
            print(f"设置 FTP 时出错: {str(e)}")
            cls._ftp = None

    @classmethod
    def _get_ftp(cls) -> Optional[int]:
        return cls._ftp

    @staticmethod
    def _get_activity_athlete_by_external_id(
        db: Session, external_id: int
    ) -> Optional[Tuple[TbActivity, TbAthlete]]:
        """
        根据 external_id 获取活动和运动员信息

        Args:
            db: 数据库会话
            external_id: Strava 的 external_id

        Returns:
            Tuple[TbActivity, TbAthlete]: 活动和运动员的完整数据库行对象，如果不存在则返回None
        """
        try:
            # 根据 external_id 查询活动信息
            # 注意：这里假设 TbActivity 有一个存储 Strava ID 的字段
            # 可能字段名是 external_id, strava_id, 或者就是 id 本身存储的是 Strava ID
            activity = db.query(TbActivity).filter(TbActivity.id == external_id).first()
            if not activity:
                print(f"未找到 external_id 为 {external_id} 的活动")
                return None

            # 查询运动员信息
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
