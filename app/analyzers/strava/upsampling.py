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

