"""Strava 分项分析（整体/功率/心率/速度/海拔/温度/区间/训练效果）。"""
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from ...core.analytics.time_utils import format_time as _fmt
from ...core.analytics.power import normalized_power as _np, work_above_ftp as _work_above_ftp, w_balance_decline as _w_decline
from ...core.analytics.hr import recovery_rate as _hr_recovery
from ...core.analytics.altitude import total_descent as _total_descent, uphill_downhill_distance_km as _updown
from ...core.analytics.training import (
    aerobic_effect as _aerobic,
    anaerobic_effect as _anaerobic,
    power_zone_percentages as _zone_percentages,
    power_zone_times as _zone_times,
    primary_training_benefit as _primary_benefit,
    calculate_training_load as _tl,
    calculate_running_training_load as _rtl,
)
from ...core.analytics.pace import (
    parse_pace_string
)
from ...db.models import TbActivity, TbAthlete
from ...core.analytics import zones as _zones


def _get_activity_athlete_by_external_id(db: Session, external_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    activity = db.query(TbActivity).filter(TbActivity.external_id == external_id).first()
    if not activity or not getattr(activity, 'athlete_id', None):
        return None
    athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
    if not athlete:
        return None
    return activity, athlete


def analyze_overall(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """分析整体信息，支持骑行和跑步活动的训练负荷计算"""
    try:
        # 判断活动类型：从activity_data的sport_type获取
        sport_type = activity_data.get('sport_type', '').lower() if activity_data else ''
        is_running = sport_type in ['run', 'trail_run', 'virtual_run']
        
        result = {
            'distance'      : round(activity_data.get('distance') / 1000, 2),
            'moving_time'   : _fmt(int(activity_data.get('moving_time'))),
            'average_speed' : round(activity_data.get('average_speed') * 3.6, 1),
            'elevation_gain': int(activity_data.get('total_elevation_gain')),
            'avg_power'     : int(activity_data.get('average_watts')) if activity_data.get('average_watts') else None,
            'calories'      : int(activity_data.get('calories')),
            'training_load' : None,  # 将在下面计算
            'status'        : None,
            'avg_heartrate' : int(activity_data.get('average_heartrate')) if activity_data.get('average_heartrate') else None,
            'max_altitude'  : int(activity_data.get('elev_high')),
        }
        
        # 计算训练负荷
        aa = _get_activity_athlete_by_external_id(db, external_id)
        if aa:
            _, athlete = aa
            moving_time = int(activity_data.get('moving_time') or 0)
            
            if is_running:
                # 跑步活动：使用 rTSS
                ft_pace = None
                if hasattr(athlete, 'FTPace') and athlete.FTPace:
                    try:
                        pace_val = athlete.FTPace
                        if isinstance(pace_val, str):
                            ft_pace = parse_pace_string(pace_val)
                        else:
                            # 如果不是字符串，直接转换为整数（假设已经是秒/公里）
                            ft_pace = int(pace_val)
                    except (ValueError, AttributeError, TypeError):
                        pass
                
                if ft_pace and ft_pace > 0 and moving_time:
                    # 直接使用原始平均速度计算配速
                    avg_speed_ms = None
                    # 优先使用activity_data中的average_speed（单位是 m/s）
                    if activity_data and 'average_speed' in activity_data:
                        avg_speed_ms = float(activity_data.get('average_speed', 0))
                    else:
                        # 从流数据计算平均速度
                        velocity_stream = stream_data.get('velocity_smooth', stream_data.get('velocity', {}))
                        speeds = velocity_stream.get('data', []) if isinstance(velocity_stream, dict) else velocity_stream
                        if speeds:
                            valid_speeds = [float(s) for s in speeds if s is not None and s > 0]
                            if valid_speeds:
                                avg_speed_ms = sum(valid_speeds) / len(valid_speeds)
                    
                    if avg_speed_ms and avg_speed_ms > 0:
                        # 计算原始配速（秒/公里）
                        raw_pace = 1000.0 / avg_speed_ms  # 配速 = 1000米 / 速度(m/s)
                        # 使用原始配速计算训练负荷
                        result['training_load'] = _rtl(raw_pace, ft_pace, moving_time)
            else:
                # 骑行活动：使用 TSS
                if result.get('avg_power') and moving_time:
                    try:
                        ftp = int(athlete.ftp) if getattr(athlete, 'ftp', None) else 0
                        if ftp and ftp > 0:
                            result['training_load'] = _tl(result['avg_power'], ftp, moving_time)
                    except Exception:
                        pass
        
        return result
    except Exception:
        return None


def analyze_power(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[Dict[str, Any]]:
    if 'watts' not in stream_data:
        return None
    try:
        power_stream = stream_data.get('watts', {})
        power = [p if p is not None else 0 for p in power_stream.get('data', [])]
        aa = _get_activity_athlete_by_external_id(db, external_id)
        if not aa:
            return None
        _, athlete = aa
        ftp = int(athlete.ftp)
        # 若无 w_balance 流，基于功率与 W' 粗略估算
        wbal = stream_data.get('w_balance', {}).get('data', []) if isinstance(stream_data.get('w_balance'), dict) else stream_data.get('w_balance', [])
        if (not wbal) and power and getattr(athlete, 'w_balance', None):
            wbal = _compute_w_balance_series(power, ftp, int(athlete.w_balance))
        return {
            'avg_power' : int(activity_data.get('average_watts')) if activity_data.get('average_watts') else (int(sum(power)/len(power)) if power else None),
            'max_power' : int(activity_data.get('max_watts')) if activity_data.get('max_watts') else (int(max(power)) if power else None),
            'total_work': round(sum(power)/1000, 0),
        }
    except Exception:
        return None


def analyze_heartrate(
    activity_data: Dict[str, Any], 
    stream_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
    if 'heartrate' not in stream_data:
        return None
    try:
        hr = [h if h is not None else 0 for h in stream_data.get('heartrate', {}).get('data', [])]
        return {
            'avg_heartrate'          : int(activity_data.get('average_heartrate')) if activity_data.get('average_heartrate') else (int(sum(hr)/len(hr)) if hr else None),
            'max_heartrate'          : int(activity_data.get('max_heartrate')) if activity_data.get('max_heartrate') else (int(max(hr)) if hr else None),
            'heartrate_recovery_rate': _hr_recovery(hr),
        }
    except Exception:
        return None


def analyze_cadence(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """踏频指标（Strava 数据）。

    仅使用 cadence 流计算平均和最大踏频；其他高级指标保留为空。
    
    对于跑步活动，踏频数据需要乘以2（因为设备记录的是单侧步频，需要转换为总步频）。
    """
    if 'cadence' not in stream_data:
        return None
    try:
        cad = [c if c is not None else 0 for c in stream_data.get('cadence', {}).get('data', [])]
        if not cad:
            return None
        
        # 判断是否为跑步活动
        sport_type = activity_data.get('sport_type', '').lower() if activity_data else ''
        is_running = sport_type in ['run', 'trail_run', 'virtual_run']
        
        # 如果是跑步活动，踏频需要乘以2（单侧步频 -> 总步频）
        if is_running:
            cad = [c * 2 for c in cad]
        
        return {
            'avg_cadence': int(sum(cad)/len(cad)) if cad else None,
            'max_cadence': int(max(cad)) if cad else None,
        }
    except Exception:
        return None


def analyze_speed(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        # compute coasting_time from velocity_smooth and watts if available
        vel = stream_data.get('velocity_smooth', {}).get('data', [])
        watts = stream_data.get('watts', {}).get('data', []) if 'watts' in stream_data else []
        coasting = 0
        if vel:
            for i in range(len(vel)):
                v = vel[i] or 0.0
                p = (watts[i] if i < len(watts) else 0) or 0.0
                if v < 0.27778 or p < 10:
                    coasting += 1
        return {
            'avg_speed'    : round(activity_data.get('average_speed') * 3.6, 1),
            'max_speed'    : round(activity_data.get('max_speed') * 3.6, 1),
            'moving_time'  : _fmt(int(activity_data.get('moving_time'))),
            'total_time'   : _fmt(int(activity_data.get('elapsed_time'))),
            'pause_time'   : _fmt(int(activity_data.get('elapsed_time')) - int(activity_data.get('moving_time'))),
            'coasting_time': _fmt(coasting),
        }
    except Exception:
        return None


def analyze_training_effect(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """分析训练效果，支持骑行（功率）和跑步（配速）活动"""
    try:
        # 判断活动类型：从activity_data的sport_type获取
        sport_type = activity_data.get('sport_type', '').lower() if activity_data else ''
        is_running = sport_type in ['run', 'trail_run', 'virtual_run']
        
        aa = _get_activity_athlete_by_external_id(db, external_id)
        if not aa:
            return None
        _, athlete = aa
        
        moving_time = int(activity_data.get('moving_time') or 0)
        
        if is_running:
            # 跑步活动：基于配速计算训练负荷
            ft_pace = None
            if hasattr(athlete, 'FTPace') and athlete.FTPace:
                try:
                    pace_val = athlete.FTPace
                    if isinstance(pace_val, str):
                        ft_pace = parse_pace_string(pace_val)
                    else:
                        # 如果不是字符串，直接转换为整数（假设已经是秒/公里）
                        ft_pace = int(pace_val)
                except (ValueError, AttributeError, TypeError):
                    pass
            
            if ft_pace and ft_pace > 0 and moving_time:
                # 直接使用原始平均速度计算配速
                avg_speed_ms = None
                # 优先使用activity_data中的average_speed（单位是 m/s）
                if activity_data and 'average_speed' in activity_data:
                    avg_speed_ms = float(activity_data.get('average_speed', 0))
                else:
                    # 从流数据计算平均速度
                    velocity_stream = stream_data.get('velocity_smooth', stream_data.get('velocity', {}))
                    speeds = velocity_stream.get('data', []) if isinstance(velocity_stream, dict) else velocity_stream
                    if speeds:
                        valid_speeds = [float(s) for s in speeds if s is not None and s > 0]
                        if valid_speeds:
                            avg_speed_ms = sum(valid_speeds) / len(valid_speeds)
                
                if avg_speed_ms and avg_speed_ms > 0:
                    # 计算原始配速（秒/公里）
                    raw_pace = 1000.0 / avg_speed_ms  # 配速 = 1000米 / 速度(m/s)
                    # 使用原始配速计算训练负荷
                    training_load = _rtl(raw_pace, ft_pace, moving_time)
                else:
                    training_load = None
            else:
                training_load = None
            
            return {
                'primary_training_benefit': None,
                'aerobic_effect': None,
                'anaerobic_effect': None,
                'training_load': training_load,
                'carbohydrate_consumption': int(activity_data.get('calories', 0) / 4.138),
            }
        else:
            # 骑行活动：基于功率计算
            if not has_watts:
                return None
            
            power = [p if p is not None else 0 for p in stream_data.get('watts', {}).get('data', [])]
            if not power:
                return None
            
            ftp = int(athlete.ftp) if getattr(athlete, 'ftp', None) else 0
            if not ftp or ftp <= 0:
                return None
            
            ae = _aerobic(power, ftp)
            ne = _anaerobic(power, ftp)
            zd = _zone_percentages(power, ftp)
            zt = _zone_times(power, ftp)
            pb, _ = _primary_benefit(zd, zt, round(len(power)/60, 0), ae, ne, ftp, int(activity_data.get('max_watts') or 0))
            avg_power = int(activity_data.get('average_watts') or (sum(power)/len(power) if power else 0))
            
            if not moving_time:
                moving_time = len(power)
            
            training_load = _tl(avg_power, ftp, moving_time) if (avg_power and ftp and moving_time) else None
            
            return {
                'primary_training_benefit': pb,
                'aerobic_effect': ae,
                'anaerobic_effect': ne,
                'training_load': training_load,
                'carbohydrate_consumption': int(activity_data.get('calories', 0) / 4.138),
            }
    except Exception:
        return None


def analyze_altitude(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if 'altitude' not in stream_data:
        return None
    try:
        grades = stream_data.get('grade_smooth', {}).get('data', [])
        return {
            'elevation_gain': int(activity_data.get('total_elevation_gain')),
            'max_altitude': int(activity_data.get('elev_high')),
            'max_grade': round(max(grades) if grades else 0, 1),
            'total_descent': _total_descent(stream_data.get('altitude', {}).get('data', [])),
            'min_altitude': int(activity_data.get('elev_low')),
            'uphill_distance': _updown(stream_data.get('altitude', {}).get('data', []), stream_data.get('distance', {}).get('data', []))[0],
            'downhill_distance': _updown(stream_data.get('altitude', {}).get('data', []), stream_data.get('distance', {}).get('data', []))[1],
        }
    except Exception:
        return None


def analyze_temperature(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if 'temp' not in stream_data:
        return None
    try:
        temps = stream_data.get('temp', {}).get('data', [])
        return {
            'min_temp': int(min(temps)) if temps else None,
            'max_temp': int(max(temps)) if temps else None,
            'avg_temp': int(sum(temps)/len(temps)) if temps else None,
        }
    except Exception:
        return None


def analyze_zones(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: int, db: Session) -> Optional[List[Dict[str, Any]]]:
    try:
        aa = _get_activity_athlete_by_external_id(db, external_id)
        if not aa:
            return None
        _, athlete = aa
        zones_data = []
        if 'watts' in stream_data and int(athlete.ftp) > 0:
            ftp = int(athlete.ftp)
            pd = [p if p is not None else 0 for p in stream_data.get('watts', {}).get('data', [])]
            buckets = _zones.analyze_power_zones(pd, ftp)
            if buckets:
                zones_data.append({'distribution_buckets': buckets, 'type': 'power'})
        if 'heartrate' in stream_data:
            # 选择心率分区基准：若启用阈值且存在阈值且>0，则采用 LTHR 分区（7个区间），否则用最大心率分区（5个区间）
            try:
                use_threshold = int(getattr(athlete, 'is_threshold_active', 0) or 0) == 1
            except Exception:
                use_threshold = False
            lthr = None
            max_hr = None
            if use_threshold and getattr(athlete, 'threshold_heartrate', None):
                try:
                    lthr = int(athlete.threshold_heartrate)
                    if lthr <= 0:
                        lthr = None
                except Exception:
                    lthr = None
            if getattr(athlete, 'max_heartrate', None):
                try:
                    max_hr = int(athlete.max_heartrate)
                except Exception:
                    max_hr = None
            hd = [h if h is not None else 0 for h in stream_data.get('heartrate', {}).get('data', [])]
            if use_threshold and lthr and lthr > 0:
                # 使用阈值心率分区，返回7个区间
                buckets = _zones.analyze_heartrate_zones_lthr(hd, lthr, max_hr)
            else:
                # 使用最大心率分区，返回5个区间
                buckets = _zones.analyze_heartrate_zones(hd, max_hr or 0)
            if buckets:
                zones_data.append({'distribution_buckets': buckets, 'type': 'heartrate'})
        return zones_data or None
    except Exception:
        return None


def _compute_w_balance_series(power: List[int], ftp: int, w_prime: int) -> List[float]:
    """根据功率与 W'（w_prime）与 FTP 估算 w_balance 曲线（与 FIT 路径一致的简化模型）。"""
    try:
        if not power or not ftp or not w_prime:
            return []
        tau = 546.0
        balance = float(w_prime)
        out: List[float] = []
        for p in power:
            p = p or 0
            if p > ftp * 1.05:
                balance -= (p - ftp)
            elif p < ftp * 0.95:
                recovery = (w_prime - balance) / tau
                balance += recovery
            balance = max(0.0, min(float(w_prime), balance))
            out.append(round(balance / 1000.0, 1))
        return out
    except Exception:
        return []
