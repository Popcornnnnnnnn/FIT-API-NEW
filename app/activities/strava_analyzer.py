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
    ZoneData
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
    def analyze_activity_data(activity_data: Dict[str, Any], stream_data: Dict[str, Any], athlete_data: Dict[str, Any], external_id: int, db: Session) -> AllActivityDataResponse:
        """
        分析 Strava 活动数据和流数据
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            athlete_data: Strava API 返回的运动员数据
            external_id: Strava 的 external_id（用于在数据库中查找对应的活动）
            db: 数据库会话
            
        Returns:
            AllActivityDataResponse: 分析后的活动数据响应
        """
        # 设置 FTP 信息
        StravaAnalyzer._set_ftp(athlete_data)
        
        result = AllActivityDataResponse(
            overall=StravaAnalyzer.analyze_overall(activity_data),
            power=StravaAnalyzer.analyze_power(activity_data, stream_data, external_id, db),
            heartrate=StravaAnalyzer.analyze_heartrate(activity_data, stream_data),
            cadence=StravaAnalyzer.analyze_cadence(activity_data, stream_data),
            speed=StravaAnalyzer.analyze_speed(activity_data, stream_data),
            training_effect=StravaAnalyzer.analyze_training_effect(activity_data),
            altitude=StravaAnalyzer.analyze_altitude(activity_data, stream_data),
            temp=StravaAnalyzer.analyze_temperature(activity_data, stream_data),
            zones=StravaAnalyzer.analyze_zones(activity_data, stream_data),
            best_powers=StravaAnalyzer.analyze_best_powers(activity_data, stream_data),
        )
        
        return result

    @staticmethod
    def analyze_overall(activity_data: Dict[str, Any]) -> Optional[OverallResponse]:
        """
        分析总体信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            
        Returns:
            Optional[OverallResponse]: 总体信息响应
        """
        try:
            
            distance = round(activity_data.get("distance", 0) / 1000, 2)
            moving_time = ZoneAnalyzer.format_time(int(activity_data.get("moving_time", 0)))
            average_speed = round(activity_data.get("average_speed", 0) * 3.6, 1)
            elevation_gain = int(activity_data.get("total_elevation_gain", 0))
            avg_power = activity_data.get("average_watts")
            if avg_power is not None:
                avg_power = int(avg_power)
            calories = int(activity_data.get("calories", 0))
            training_load = 0
            status = None
            avg_heartrate = activity_data.get("average_heartrate")
            if avg_heartrate is not None:
                avg_heartrate = int(avg_heartrate)
            
            max_altitude = activity_data.get("elev_high")
            if max_altitude is not None:
                max_altitude = int(max_altitude)
            
            
            result = OverallResponse(
                distance=distance,
                moving_time=moving_time,
                average_speed=average_speed,
                elevation_gain=elevation_gain,
                avg_power=avg_power,
                calories=calories,
                training_load=training_load,
                status=status,
                avg_heartrate=avg_heartrate,
                max_altitude=max_altitude
            )
            
            return result
            
        except Exception as e:
            # 如果处理过程中出现错误，返回 None
            print(f"分析总体信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_power(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[PowerResponse]:
        """
        分析功率信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            external_id: Strava 的 external_id
            db: 数据库会话
            
        Returns:
            Optional[PowerResponse]: 功率信息响应
        """
        # 先检查是否有功率数据，没有就直接返回 None
        if not stream_data or 'watts' not in stream_data:
            return None
            
        power_stream = stream_data.get('watts', {})
        power_data = power_stream.get('data', []) if power_stream else []
        # print(type(power_data))
        if not power_data:
            return None
            
        try:
            
            avg_power = activity_data.get("average_watts")
            max_power = activity_data.get("max_watts")
            normalized_power = StravaAnalyzer._calculate_normalized_power(power_data)
            total_work = activity_data.get("kilojoules")
            weighted_average_power = activity_data.get("weighted_average_watts")
            # 获取 FTP 并计算强度因子
            ftp = StravaAnalyzer._get_ftp()
            intensity_factor = None
            if ftp and ftp > 0 and normalized_power:
                intensity_factor = round(normalized_power / ftp, 2)
            
            
            # 计算变异性指数
            variability_index = None
            if avg_power and avg_power > 0 and normalized_power:
                variability_index = round(normalized_power / avg_power, 2)
        
                     
            # 计算高于FTP的做功
            work_above_ftp = None
            if ftp and ftp > 0:
                work_above_ftp = StravaAnalyzer._calculate_work_above_ftp(power_data, ftp)
            
            
            
            # 计算W平衡下降（需要从数据库获取无氧储备信息）
            w_balance_decline = StravaAnalyzer._calculate_w_balance_decline_from_strava(stream_data, external_id, db)
            # print(w_balance_decline)

            result = PowerResponse(
                avg_power=int(avg_power),
                max_power=int(max_power),
                normalized_power=int(normalized_power),
                total_work=round(total_work, 0),
                intensity_factor=intensity_factor,
                variability_index=variability_index,
                weighted_average_power=weighted_average_power,
                work_above_ftp=work_above_ftp,
                eftp=None,  # 需要复杂算法
                w_balance_decline=w_balance_decline # ! 这个接口还没有测试过
            )
            
            return result
            
        except Exception as e:
            print(f"分析功率信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_heartrate(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[HeartrateResponse]:
        """
        分析心率信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[HeartrateResponse]: 心率信息响应
        """
        # 先检查是否有心率数据，没有就直接返回 None
        if not stream_data or 'heartrate' not in stream_data:
            return None
            
        heartrate_stream = stream_data.get('heartrate', {})
        heartrate_data = heartrate_stream.get('data', []) if heartrate_stream else []
        
        if not heartrate_data:
            return None
            
            
        try:
            
            # 基础心率统计
            avg_heartrate = activity_data.get("average_heartrate")
            max_heartrate = activity_data.get("max_heartrate")
            
            # 计算效率指数（复用 crud.py 中的算法）
            efficiency_index = StravaAnalyzer._calculate_efficiency_index(stream_data)
            
            # 计算解耦率（复用 crud.py 中的算法）
            decoupling_rate = StravaAnalyzer._calculate_decoupling_rate(stream_data)
            
            # 基础响应数据
            result = HeartrateResponse(
                avg_heartrate=int(avg_heartrate),
                max_heartrate=int(max_heartrate),
                heartrate_recovery_rate=None,  # 需要特殊算法
                heartrate_lag=None,  # 需要特殊算法
                efficiency_index=efficiency_index,
                decoupling_rate=decoupling_rate
            )
            
            return result
            
        except Exception as e:
            print(f"分析心率信息时出错: {str(e)}")
            return None

    @staticmethod
    def analyze_cadence(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[CadenceResponse]:
        """
        分析踏频信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[CadenceResponse]: 踏频信息响应
        """
        # TODO: 实现踏频信息分析逻辑
        return None

    @staticmethod
    def analyze_speed(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[SpeedResponse]:
        """
        分析速度信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[SpeedResponse]: 速度信息响应
        """
        # TODO: 实现速度信息分析逻辑
        return None

    @staticmethod
    def analyze_training_effect(activity_data: Dict[str, Any]) -> Optional[TrainingEffectResponse]:
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
    def analyze_altitude(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[AltitudeResponse]:
        """
        分析海拔信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[AltitudeResponse]: 海拔信息响应
        """
        # TODO: 实现海拔信息分析逻辑
        return None

    @staticmethod
    def analyze_temperature(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[TemperatureResponse]:
        """
        分析温度信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[TemperatureResponse]: 温度信息响应
        """
        # TODO: 实现温度信息分析逻辑
        return None

    @staticmethod
    def analyze_zones(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[List[ZoneData]]:
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
    def analyze_best_powers(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """
        分析最佳功率信息
        
        Args:
            activity_data: Strava API 返回的活动数据
            stream_data: Strava API 返回的流数据
            
        Returns:
            Optional[Dict[str, int]]: 最佳功率信息响应
        """
        # TODO: 实现最佳功率信息分析逻辑
        return None 
    
    # 辅助方法（复用 activities/crud.py 中的算法）
    
    @staticmethod
    def _calculate_normalized_power(powers: list) -> int:
        """
        计算标准化功率（复用 activities/crud.py 中的算法）
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
    
    @staticmethod
    def _calculate_total_work(powers: list) -> int:
        """
        计算总做功（千焦）
        """
        if not powers:
            return 0
        
        # 假设每秒一个数据点，总做功 = 平均功率 * 时间（秒）/ 1000
        avg_power = sum(powers) / len(powers)
        total_seconds = len(powers)
        total_work = (avg_power * total_seconds) / 1000  # 转换为千焦
        
        return int(total_work)
    
    @staticmethod
    def _calculate_work_above_ftp(powers: list, ftp: float) -> int:
        """
        计算高于FTP的做功（复用 activities/crud.py 中的算法）
        
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
    
    @staticmethod
    def _calculate_w_balance_decline_from_strava(stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[float]:
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

            power_stream = stream_data.get('watts', {}) if stream_data else {}
            power_data = power_stream.get('data', []) if power_stream else []
            
            if not power_data:
                return None
            
            # 从数据库获取运动员信息
            # 注意：这里的 external_id 是 Strava 的 external_id
            activity_athlete = StravaAnalyzer._get_activity_athlete_by_external_id(db, external_id)
            
            if not activity_athlete:
                return None
                
            activity, athlete = activity_athlete
            if not athlete or not athlete.ftp or not athlete.w_balance:
                return None
            
            # 准备运动员信息
            athlete_info = {
                'ftp': int(athlete.ftp),
                'wj': athlete.w_balance  # 无氧储备（焦耳）
            }
            
            # 计算 W' 平衡数组（参考 fit_parser.py 的算法）
            w_balance_array = StravaAnalyzer._calculate_w_balance_array(power_data, athlete_info)
            
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
    def _calculate_w_balance_array(power_data: list, athlete_info: Dict[str, Any]) -> list:
        """
        计算 W' 平衡数组（复用 fit_parser.py 中的算法）
        
        Args:
            power_data: 功率数据列表
            athlete_info: 运动员信息，包含 ftp 和 wj 字段
            
        Returns:
            list: W' 平衡数组（千焦，保留一位小数）
        """
        try:
            if not power_data or not athlete_info.get('ftp') or not athlete_info.get('wj'):
                return []
            
            W_prime = athlete_info['wj']  # 无氧储备（焦耳）
            CP = int(athlete_info['ftp'])  # 功能阈值功率
            
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
    def _calculate_efficiency_index(stream_data: Dict[str, Any]) -> float:
        """
        计算效率指数（复用 activities/crud.py 中的算法）
        """
        try:
            # 获取功率和心率数据
            power_stream = stream_data.get('watts', {})
            power_data = power_stream.get('data', []) if power_stream else []
            
            heartrate_stream = stream_data.get('heartrate', {})
            heartrate_data = heartrate_stream.get('data', []) if heartrate_stream else []
            
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
    
    @staticmethod
    def _calculate_decoupling_rate(stream_data: Dict[str, Any]) -> str:
        """
        计算解耦率（复用 activities/crud.py 中的算法）
        """
        try:
            # 获取功率和心率数据
            power_stream = stream_data.get('watts', {})
            power_data = power_stream.get('data', []) if power_stream else []
            
            heartrate_stream = stream_data.get('heartrate', {})
            heartrate_data = heartrate_stream.get('data', []) if heartrate_stream else []
            
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
        """
        获取当前设置的 FTP 值
        
        Returns:
            Optional[int]: FTP 值，如果未设置则返回 None
        """
        return cls._ftp
    
    @staticmethod
    def _get_activity_athlete_by_external_id(db: Session, external_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
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
            athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
            if not athlete:
                print(f"未找到 athlete_id 为 {activity.athlete_id} 的运动员")
                return None
                
            return activity, athlete
            
        except Exception as e:
            print(f"根据 external_id 查询活动和运动员信息时出错: {str(e)}")
            return None
