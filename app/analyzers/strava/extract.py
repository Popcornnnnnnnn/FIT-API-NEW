"""
Strava 流数据抽取模块

功能：
- 将 Strava API 返回的流（key_by_type=true）转换为内部统一格式；
- 支持将 velocity_smooth 转换为 speed（KM/H）；
- 支持生成 best_power 曲线（时间窗最大均值）。

返回格式约定：
    [{ 'type': 字段名, 'data': 列表, 'series_type': 'time'|'distance', 'original_size': N, 'resolution': 'high' }]
"""

from typing import Dict, Any, List, Optional


def _best_power_curve(powers: List[Optional[int]]) -> List[int]:
    n = len(powers)
    out: List[int] = []
    vals = [int(p or 0) for p in powers]
    for window in range(1, n + 1):
        if n < window:
            out.append(0)
            continue
        wsum = sum(vals[:window])
        max_avg = wsum / window
        for i in range(1, n - window + 1):
            wsum = wsum - vals[i - 1] + vals[i + window - 1]
            avg = wsum / window
            if avg > max_avg:
                max_avg = avg
        out.append(int(round(max_avg)))
    return out


def extract_stream_data(stream_data: Dict[str, Any], keys: List[str], resolution: str = 'high') -> Optional[List[Dict[str, Any]]]:
    if not stream_data or not keys:
        return None
    result: List[Dict[str, Any]] = []
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
                result.append({
                    'type': field,
                    'data': item['data'],
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
            curve = _best_power_curve(powers or [])
            result.append({
                'type': 'best_power',
                'data': curve,
                'series_type': 'time',
                'original_size': len(curve),
                'resolution': 'high'
            })
    return result
