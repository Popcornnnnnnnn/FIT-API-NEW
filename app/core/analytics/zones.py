from typing import List, Dict, Any
from collections import defaultdict
from .time_utils import format_time


def _percentage(time_in_zone: int, total_time: int) -> str:
    if total_time == 0:
        return "0.0%"
    return f"{(time_in_zone / total_time) * 100:.1f}%"


def analyze_power_zones(power_data: List[int], ftp: int) -> List[Dict[str, Any]]:
    if not power_data or ftp <= 0:
        return []
    zones = [
        (0, int(ftp * 0.55)),
        (int(ftp * 0.55), int(ftp * 0.75)),
        (int(ftp * 0.75), int(ftp * 0.90)),
        (int(ftp * 0.90), int(ftp * 1.05)),
        (int(ftp * 1.05), int(ftp * 1.20)),
        (int(ftp * 1.20), int(ftp * 1.50)),
        (int(ftp * 1.50), float('inf')),
    ]
    zone_times = defaultdict(int)
    valid = 0
    for p in power_data:
        if p is None or p <= 0:
            continue
        valid += 1
        for i, (mn, mx) in enumerate(zones):
            if mn <= p < mx:
                zone_times[i] += 1
                break
        else:
            if p >= zones[-1][1]:
                zone_times[len(zones) - 1] += 1
    out = []
    for i, (mn, mx) in enumerate(zones):
        t = zone_times[i]
        out.append({
            'min': mn,
            'max': -1 if mx == float('inf') else mx,
            'time': format_time(t),
            'percentage': _percentage(t, valid),
        })
    return out


def analyze_heartrate_zones(hr_data: List[int], max_hr: int) -> List[Dict[str, Any]]:
    if not hr_data or max_hr <= 0:
        return []
    zones = [
        (0, int(max_hr * 0.60)),
        (int(max_hr * 0.60), int(max_hr * 0.70)),
        (int(max_hr * 0.70), int(max_hr * 0.80)),
        (int(max_hr * 0.80), int(max_hr * 0.90)),
        (int(max_hr * 0.90), max_hr),
    ]
    zone_times = defaultdict(int)
    valid = 0
    for h in hr_data:
        if h is None or h <= 0:
            continue
        valid += 1
        for i, (mn, mx) in enumerate(zones):
            if mn <= h < mx:
                zone_times[i] += 1
                break
        else:
            if h >= zones[-1][1]:
                zone_times[len(zones) - 1] += 1
    out = []
    for i, (mn, mx) in enumerate(zones):
        t = zone_times[i]
        out.append({
            'min': mn,
            'max': mx,
            'time': format_time(t),
            'percentage': _percentage(t, valid),
        })
    return out

