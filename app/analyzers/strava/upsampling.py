"""
Strava 低精度流数据补齐模块

功能：
- is_low_resolution：检测 Strava 流是否为低精度（时间间隔较大，可能触发 10k 限制）
- prepare_for_upsampling：在每个流项中注入时间参考，便于后续补齐
- upsample_low_resolution：将低精度流补齐到 1Hz（按 moving_time 推断目标长度）

说明：
- 本模块不追求高精度数值插值，仅使用“重复采样/就近取值”，避免引入额外噪声；
- 适用于需要统一粒度进行分析的场景（比如功率曲线、节奏分析等）。
"""

from typing import Dict, Any


def is_low_resolution(stream_data: Dict[str, Any]) -> bool:
    if not stream_data or 'time' not in stream_data:
        return False
    time_data = stream_data['time'].get('data', [])
    if len(time_data) <= 1:
        return False
    intervals = []
    for i in range(1, min(len(time_data), 5)):
        if time_data[i] is not None and time_data[i-1] is not None:
            delta = time_data[i] - time_data[i-1]
            if delta > 0:
                intervals.append(delta)
    if not intervals:
        return False
    avg = sum(intervals) / len(intervals)
    return avg > 5.0


def prepare_for_upsampling(stream_data: Dict[str, Any]) -> Dict[str, Any]:
    if not stream_data or 'time' not in stream_data:
        return stream_data
    time_data = stream_data['time'].get('data', [])
    if not time_data:
        return stream_data
    prepared = dict(stream_data)
    for k, v in prepared.items():
        if k != 'time' and isinstance(v, dict) and 'data' in v:
            v['_time_reference'] = {'time': time_data}
    return prepared


def _upsample_series(data: list, target_size: int) -> list:
    if not data:
        return []
    if len(data) >= target_size:
        return data
    upsampled = []
    step = len(data) / target_size
    for i in range(target_size):
        idx = min(int(i * step), len(data) - 1)
        upsampled.append(data[idx])
    return upsampled


def upsample_low_resolution(stream_data: Dict[str, Any], moving_time_seconds: int) -> Dict[str, Any]:
    if not moving_time_seconds or moving_time_seconds <= 0:
        return stream_data
    target_size = moving_time_seconds + 1
    result = {}
    for key, item in stream_data.items():
        if not isinstance(item, dict) or 'data' not in item:
            result[key] = item
            continue
        data = item['data']
        if key == 'latlng':
            up = _upsample_series(data, target_size)
            result[key] = dict(item, data=up, original_size=len(data), upsampled_size=len(up))
        else:
            up = _upsample_series(data, target_size)
            result[key] = dict(item, data=up, original_size=len(data), upsampled_size=len(up))
    return result
