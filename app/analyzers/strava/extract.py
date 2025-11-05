"""
Strava 流数据抽取模块

功能：
- 将 Strava API 返回的流（key_by_type=true）转换为内部统一格式；
- 支持将 velocity_smooth 转换为 speed（KM/H）；
- 支持生成 best_power 曲线（时间窗最大均值）；
- 为缺失的衍生指标（VAM、torque、spi、power_hr_ratio、w_balance）补齐数据。

返回格式约定：
    [{ 'type': 字段名, 'data': 列表, 'series_type': 'time'|'distance', 'original_size': N, 'resolution': 'high' }]
"""

from typing import Dict, Any, List, Optional
import math
import logging
import numpy as np

logger = logging.getLogger(__name__)


def _best_power_curve(vals: List[int]) -> List[int]:
    """计算 1..N 每个窗口长度下的最佳平均功率曲线。

    备注：
        - 旧实现使用两层 Python 循环，复杂度 O(n^2) 且运行在解释器里，数据量稍大就会卡顿。
        - 这里改用 numpy 前缀和，将「长度为 w 的窗口和」改写为向量化减法，
          每个窗口长度仍需 O(n) 次运算，但都在 C 层完成，显著降低 Python 端开销。
    """
    if not vals:
        return []

    arr = np.asarray(vals, dtype=np.float64)
    n = arr.size
    prefix = np.concatenate(([0.0], arr.cumsum()))
    best = np.empty(n, dtype=np.int32)

    for window in range(1, n + 1):
        window_sums = prefix[window:] - prefix[:-window]
        best[window - 1] = int(round(window_sums.max() / window))

    return best.tolist()


def _calculate_power_hr_ratio(powers: List[Optional[int]], heart_rates: List[Optional[int]]) -> List[float]:
    result: List[float] = []
    size = min(len(powers), len(heart_rates))
    for idx in range(size):
        p = powers[idx] or 0
        hr = heart_rates[idx] or 0
        ratio = round(p / hr, 2) if p > 0 and hr > 0 else 0.0
        result.append(ratio)
    return result


def _calculate_spi(powers: List[Optional[int]], cadence: List[Optional[int]]) -> List[float]:
    result: List[float] = []
    size = min(len(powers), len(cadence))
    for idx in range(size):
        p = powers[idx] or 0
        cad = cadence[idx] or 0
        spi = round(p / cad, 2) if p > 0 and cad > 0 else 0.0
        result.append(spi)
    return result


def _calculate_torque(powers: List[Optional[int]], cadence: List[Optional[int]]) -> List[int]:
    result: List[int] = []
    size = min(len(powers), len(cadence))
    for idx in range(size):
        p = powers[idx] or 0
        cad = cadence[idx] or 0
        if p > 0 and cad > 0:
            torque = p / (cad * 2 * math.pi / 60.0)
            result.append(int(round(torque)))
        else:
            result.append(0)
    return result


def _calculate_vam(timestamps: List[Optional[int]], altitudes: List[Optional[float]], window_seconds: int = 50) -> List[int]:
    if not timestamps or not altitudes:
        return []
    size = min(len(timestamps), len(altitudes))
    vam: List[int] = []
    for i in range(size):
        try:
            t_end = timestamps[i] or 0
            t_start = t_end - window_seconds
            idx_start = i
            while idx_start > 0 and (timestamps[idx_start] or 0) > t_start:
                idx_start -= 1
            if idx_start == i:
                vam.append(0)
                continue
            delta_alt = (altitudes[i] or 0.0) - (altitudes[idx_start] or 0.0)
            delta_time = (timestamps[i] or 0) - (timestamps[idx_start] or 0)
            if delta_time <= 0:
                vam.append(0)
                continue
            vam_value = delta_alt / (delta_time / 3600.0)
            vam.append(int(round(vam_value * 1.4)))
        except Exception:
            vam.append(0)
    return [v if -5000 <= v <= 5000 else 0 for v in vam]


def _calculate_w_balance(
    powers: List[Optional[int]],
    ftp: Optional[int],
    w_prime: Optional[int],
) -> List[float]:
    if not powers:
        return []
    if not ftp or ftp <= 0 or not w_prime or w_prime <= 0:
        return [0.0] * len(powers)
    balance = float(w_prime)
    series: List[float] = []
    tau = 546.0
    cp = float(ftp)
    for p in powers:
        power_val = float(p or 0)
        if power_val > cp * 1.05:
            balance -= (power_val - cp)
        elif power_val < cp * 0.95:
            balance += (w_prime - balance) / tau
        balance = max(0.0, min(float(w_prime), balance))
        series.append(round(balance / 1000.0, 1))
    return series


def enrich_with_derived_streams(
    stream_data: Dict[str, Any],
    activity_data: Optional[Dict[str, Any]] = None,
    athlete_entry: Optional[Any] = None,
) -> Dict[str, Any]:
    if not isinstance(stream_data, dict):
        return stream_data

    # 防止原数据被意外修改，浅拷贝一份字典引用
    enriched = dict(stream_data)

    time_stream = enriched.get('time', {})
    altitude_stream = enriched.get('altitude') or enriched.get('altitude_smooth')
    power_stream = enriched.get('watts') or enriched.get('power')
    heartrate_stream = enriched.get('heartrate')
    cadence_stream = enriched.get('cadence')

    time_data = list(time_stream.get('data', [])) if isinstance(time_stream, dict) else []
    altitude_data = list(altitude_stream.get('data', [])) if isinstance(altitude_stream, dict) else []
    power_data = [int(p) if p is not None else 0 for p in (power_stream.get('data', []) if isinstance(power_stream, dict) else [])]
    heartrate_data = [int(h) if h is not None else 0 for h in (heartrate_stream.get('data', []) if isinstance(heartrate_stream, dict) else [])]
    cadence_data = [int(c) if c is not None else 0 for c in (cadence_stream.get('data', []) if isinstance(cadence_stream, dict) else [])]

    if 'power_hr_ratio' not in enriched and power_data and heartrate_data:
        arr = _calculate_power_hr_ratio(power_data, heartrate_data)
        if arr:
            enriched['power_hr_ratio'] = {
                'data': arr,
                'series_type': 'time',
                'original_size': len(arr),
                'resolution': 'high',
            }

    if 'spi' not in enriched and power_data and cadence_data:
        arr = _calculate_spi(power_data, cadence_data)
        if arr:
            enriched['spi'] = {
                'data': arr,
                'series_type': 'time',
                'original_size': len(arr),
                'resolution': 'high',
            }

    if 'torque' not in enriched and power_data and cadence_data:
        arr = _calculate_torque(power_data, cadence_data)
        if arr:
            enriched['torque'] = {
                'data': arr,
                'series_type': 'time',
                'original_size': len(arr),
                'resolution': 'high',
            }

    if 'vam' not in enriched and time_data and altitude_data:
        arr = _calculate_vam(time_data, altitude_data)
        if arr:
            enriched['vam'] = {
                'data': arr,
                'series_type': 'time',
                'original_size': len(arr),
                'resolution': 'high',
            }

    if 'w_balance' not in enriched and power_data:
        arr = _calculate_w_balance(power_data, athlete_entry.ftp, athlete_entry.w_balance)
        if arr:
            enriched['w_balance'] = {
                'data': arr,
                'series_type': 'time',
                'original_size': len(arr),
                'resolution': 'high',
            }
    return enriched


def extract_stream_data(stream_data: Dict[str, Any], keys: List[str], resolution: str = 'high', activity_data: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, Any]]]:
    if not stream_data or not keys:
        return None
    result: List[Dict[str, Any]] = []
    
    # 判断是否为跑步活动
    is_running = False
    if activity_data:
        sport_type = activity_data.get('sport_type', '').lower()
        is_running = sport_type in ['run', 'trail_run', 'virtual_run']
    
    try:
        for field in keys:
            if field == 'velocity_smooth' and 'velocity_smooth' in stream_data:
                item = stream_data['velocity_smooth']
                raw = item.get('data', [])
                speed = [round((v or 0) * 3.6, 1) for v in raw]
                result.append({
                    'type': 'speed',
                    'data': speed,
                    'series_type': item.get('series_type', 'time'),
                    'original_size': len(speed),
                    'resolution': 'high'
                })
                continue
            if field in stream_data:
                item = stream_data[field]
                if isinstance(item, dict) and 'data' in item:
                    data = item['data']
                    # 如果是跑步活动的 cadence stream，需要乘以2
                    if field == 'cadence' and is_running:
                        data = [int((d or 0) * 2) if d is not None else None for d in data]
                    
                    result.append({
                        'type': field,
                        'data': data,
                        'series_type': item.get('series_type', 'time'),
                        'original_size': item.get('original_size', len(item['data'])),
                        'resolution': 'high'
                    })
                    continue
            if field in ['latitude', 'longitude'] and 'latlng' in stream_data:
                latlng = stream_data['latlng']
                data = latlng.get('data', [])
                if field == 'latitude':
                    extracted = [p[0] if p and len(p) >= 2 else None for p in data]
                else:
                    extracted = [p[1] if p and len(p) >= 2 else None for p in data]
                result.append({
                    'type': field,
                    'data': extracted,
                    'series_type': latlng.get('series_type', 'time'),
                    'original_size': latlng.get('original_size', len(extracted)),
                    'resolution': 'high'
                })
                continue
            if field == 'best_power' and 'watts' in stream_data:
                watts = stream_data['watts']
                powers = watts.get('data', [])
                curve = _best_power_curve(powers or []) # ! SLOW
                result.append({
                    'type': 'best_power',
                    'data': curve,
                    'series_type': 'time',
                    'original_size': len(curve),
                    'resolution': 'high'
                })
                continue
        return result
    except Exception:
        return None
