"""本地流 Power 指标装配（平均/最大/NP/IF/WA/W′ 等）。"""
from typing import Dict, Any, List, Optional
from ...core.analytics.power import normalized_power, work_above_ftp, w_balance_decline


def compute_power_info(stream_data: Dict[str, Any], ftp: int, session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    power_data = stream_data.get('power', [])
    if not power_data:
        return None

    valid_powers = [int(p) for p in power_data if p is not None and p > 0]
    if not valid_powers:
        return None

    result: Dict[str, Any] = {}

    if session_data and 'avg_power' in session_data:
        result['avg_power'] = int(session_data['avg_power'])
    else:
        result['avg_power'] = int(sum(valid_powers) / len(valid_powers))

    if session_data and 'max_power' in session_data:
        result['max_power'] = int(session_data['max_power'])
    else:
        result['max_power'] = int(max(valid_powers))

    result['total_work'] = round(sum(valid_powers) / 1000, 0)

    return result
