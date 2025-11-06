from collections import deque
from typing import List, Optional


def normalized_power(powers: List[int], window: int = 30) -> int: # ! 用numpy实现
    """Compute normalized power using an O(n) rolling average and 4th-power mean.

    Args:
        powers: sequence of power values (assumed 1Hz sampling)
        window: rolling average window length in seconds (default 30)
    """
    if not powers:
        return 0
    q = deque()
    s = 0.0
    rolling = []
    for p in powers:
        v = float(p or 0)
        q.append(v)
        s += v
        if len(q) > window:
            s -= q.popleft()
        rolling.append(s / len(q))
    if not rolling:
        return 0
    fourth_powers = [x ** 4 for x in rolling]
    mean_fourth = sum(fourth_powers) / len(fourth_powers)
    return int(round(mean_fourth ** 0.25))


def work_above_ftp(powers: List[int], ftp: float) -> int:
    if not powers or not ftp or ftp <= 0:
        return 0
    surplus = 0.0
    for p in powers:
        v = float(p or 0)
        if v > ftp:
            surplus += (v - ftp)
    return int(surplus / 1000.0)


def w_balance_decline(w_balance: List[Optional[float]]) -> Optional[float]:
    if not w_balance:
        return None
    vals = [w for w in w_balance if w is not None]
    if not vals:
        return None
    decline = vals[0] - min(vals)
    return round(float(decline), 1)

