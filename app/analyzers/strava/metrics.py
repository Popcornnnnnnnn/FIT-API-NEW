"""Strava 分项分析（整体/功率/心率/速度/海拔/温度/区间/训练效果）。"""
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from ...core.analytics.time_utils import format_time as _fmt
from ...core.analytics.power import normalized_power as _np, work_above_ftp as _work_above_ftp, w_balance_decline as _w_decline
from ...core.analytics.hr import recovery_rate as _hr_recovery, hr_lag_seconds as _hr_lag, decoupling_rate as _decouple
from ...core.analytics.altitude import total_descent as _total_descent, uphill_downhill_distance_km as _updown
from ...core.analytics.training import (
    aerobic_effect as _aerobic,
    anaerobic_effect as _anaerobic,
    power_zone_percentages as _zone_percentages,
    power_zone_times as _zone_times,
    primary_training_benefit as _primary_benefit,
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
    try:
        return {
            'distance'      : round(activity_data.get('distance') / 1000, 2),
            'moving_time'   : _fmt(int(activity_data.get('moving_time'))),
            'average_speed' : round(activity_data.get('average_speed') * 3.6, 1),
            'elevation_gain': int(activity_data.get('total_elevation_gain')),
            'avg_power'     : int(activity_data.get('average_watts')) if activity_data.get('average_watts') else None,
            'calories'      : int(activity_data.get('calories')),
            'training_load' : None,                                                                                            # filled by caller if needed
            'status'        : None,                                                                                            # filled by caller if needed
            'avg_heartrate' : int(activity_data.get('average_heartrate')) if activity_data.get('average_heartrate') else None,
            'max_altitude'  : int(activity_data.get('elev_high')),
        }
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
            'avg_power'             : int(activity_data.get('average_watts')) if activity_data.get('average_watts') else (int(sum(power)/len(power)) if power else None),
            'max_power'             : int(activity_data.get('max_watts')) if activity_data.get('max_watts') else (int(max(power)) if power else None),
            'normalized_power'      : int(_np(power)),
            'intensity_factor'      : round(_np(power)/ftp, 2) if ftp else None,
            'total_work'            : round(sum(power)/1000, 0),
            'variability_index'     : round(_np(power)/(int(activity_data.get('average_watts')) or (sum(power)/len(power) if power else 1)), 2) if power else None,
            'weighted_average_power': int(activity_data.get('weighted_average_watts')) if activity_data.get('weighted_average_watts') else None,
            'work_above_ftp'        : _work_above_ftp(power, ftp),
            'eftp'                  : None,
            'w_balance_decline'     : _w_decline(wbal) if (isinstance(wbal, list) and len(wbal) > 0) else None,
        }
    except Exception:
        return None


def analyze_heartrate(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if 'heartrate' not in stream_data:
        return None
    try:
        hr = [h if h is not None else 0 for h in stream_data.get('heartrate', {}).get('data', [])]
        pw = [p if p is not None else 0 for p in stream_data.get('watts', {}).get('data', [])] if 'watts' in stream_data else []
        ei = _np([p for p in pw if p > 0]) / (sum(hr)/len(hr)) if pw and hr and any(hr) else None
        return {
            'avg_heartrate'          : int(activity_data.get('average_heartrate')) if activity_data.get('average_heartrate') else (int(sum(hr)/len(hr)) if hr else None),
            'max_heartrate'          : int(activity_data.get('max_heartrate')) if activity_data.get('max_heartrate') else (int(max(hr)) if hr else None),
            'heartrate_recovery_rate': _hr_recovery(hr),
            'heartrate_lag'          : _hr_lag(pw, hr) if pw else None,
            'efficiency_index'       : round(ei, 2) if ei else None,
            'decoupling_rate'        : _decouple(pw, hr) if pw else None,
        }
    except Exception:
        return None


def analyze_cadence(activity_data: Dict[str, Any], stream_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """踏频指标（Strava 数据）。

    仅使用 cadence 流计算平均和最大踏频；其他高级指标保留为空。
    """
    if 'cadence' not in stream_data:
        return None
    try:
        cad = [c if c is not None else 0 for c in stream_data.get('cadence', {}).get('data', [])]
        if not cad:
            return None
        # 估算总踏频（转数）：基于 time 流积分 cadence（rpm）
        total_strokes = None
        try:
            t = stream_data.get('time', {}).get('data', [])
            if t and len(t) == len(cad):
                acc = 0.0
                prev = t[0]
                for i in range(1, len(t)):
                    dt = max(0, (t[i] or 0) - (prev or 0))
                    acc += (cad[i] or 0) * (dt / 60.0)
                    prev = t[i]
                total_strokes = int(round(acc))
            else:
                total_strokes = int(round(sum(cad) / 60.0))
        except Exception:
            total_strokes = None
        return {
            'avg_cadence'               : int(sum(cad)/len(cad)) if cad else None,
            'max_cadence'               : int(max(cad)) if cad else None,
            'left_right_balance'        : None,
            'left_torque_effectiveness' : None,
            'right_torque_effectiveness': None,
            'left_pedal_smoothness'     : None,
            'right_pedal_smoothness'    : None,
            'total_strokes'             : total_strokes,
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
    if 'watts' not in stream_data:
        return None
    try:
        power = [p if p is not None else 0 for p in stream_data.get('watts', {}).get('data', [])]
        aa = _get_activity_athlete_by_external_id(db, external_id)
        if not aa:
            return None
        _, athlete = aa
        ftp = int(athlete.ftp)
        ae = _aerobic(power, ftp)
        ne = _anaerobic(power, ftp)
        zd = _zone_percentages(power, ftp)
        zt = _zone_times(power, ftp)
        pb, _ = _primary_benefit(zd, zt, round(len(power)/60, 0), ae, ne, ftp, int(activity_data.get('max_watts') or 0))
        avg_power = int(activity_data.get('average_watts') or (sum(power)/len(power) if power else 0))
        # 直接计算训练负荷
        from ...core.analytics.training import calculate_training_load as _tl
        moving_time = int(activity_data.get('moving_time') or len(power))
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
        if 'heartrate' in stream_data and getattr(athlete, 'max_heartrate', None):
            mhr = int(athlete.max_heartrate)
            hd = [h if h is not None else 0 for h in stream_data.get('heartrate', {}).get('data', [])]
            buckets = _zones.analyze_heartrate_zones(hd, mhr)
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
