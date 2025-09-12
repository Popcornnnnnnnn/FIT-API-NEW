from typing import List, Optional
import numpy as np
from .power import normalized_power


def filter_hr_smooth(heartrate_data: List[Optional[int]]) -> List[int]:
    filtered = []
    for hr in heartrate_data:
        if hr is None:
            continue
        if hr <= 0 or hr < 30:
            continue
        if hr > 220:
            continue
        if filtered and abs(hr - filtered[-1]) > 50:
            continue
        filtered.append(int(hr))
    return filtered


def efficiency_index(power_data: List[int], hr_data: List[int]) -> Optional[float]:
    try:
        valid_power = [p for p in power_data if p is not None and p > 0]
        if not valid_power:
            return None
        NP = normalized_power(valid_power)
        valid_hr = filter_hr_smooth(hr_data)
        if not valid_hr:
            return None
        avg_hr = sum(valid_hr) / len(valid_hr)
        return round(NP / avg_hr, 2) if avg_hr > 0 else None
    except Exception:
        return None


def recovery_rate(hr_data: List[int], window: int = 60) -> int:
    try:
        valid = filter_hr_smooth(hr_data)
        if len(valid) < window + 1:
            return 0
        max_drop = 0
        n = len(valid)
        for i in range(n - window):
            drop = valid[i] - valid[i + window]
            if drop > max_drop:
                max_drop = drop
        return int(max_drop) if max_drop > 0 else 0
    except Exception:
        return 0


def decoupling_rate(power_data: List[int], hr_data: List[int]) -> Optional[str]:
    try:
        m = min(len(power_data), len(hr_data))
        if m < 10:
            return None
        p = power_data[:m]
        h = hr_data[:m]
        mid = m // 2
        fh_p, sh_p = p[:mid], p[mid:]
        fh_h, sh_h = h[:mid], h[mid:]
        def ratio(pp, hh):
            if not hh:
                return 0.0
            avg_p = sum(pp) / len(pp) if pp else 0
            avg_h = sum(hh) / len(hh) if hh else 0
            return (avg_p / avg_h) if avg_h > 0 else 0.0
        r1 = ratio(fh_p, fh_h)
        r2 = ratio(sh_p, sh_h)
        if r1 > 0 and r2 > 0:
            dec = (r1 - r2) / r1 * 100.0
            if abs(dec) > 30:
                return None
            return f"{round(dec, 1)}%"
        return None
    except Exception:
        return None


def hr_lag_seconds(power_data: List[int], hr_data: List[int]) -> Optional[int]:
    try:
        if not power_data or not hr_data:
            return None
        m = min(len(power_data), len(hr_data))
        pa = np.array([p or 0 for p in power_data[:m]], dtype=float)
        ha = np.array([h or 0 for h in hr_data[:m]], dtype=float)
        pa -= pa.mean()
        ha -= ha.mean()
        corr = np.correlate(pa, ha, mode='full')
        lag_max = int(np.argmax(corr) - (len(pa) - 1))
        max_corr = float(np.max(corr))
        if max_corr < 0.3 * len(pa):
            return None
        return abs(lag_max)
    except Exception:
        return None

