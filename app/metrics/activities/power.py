"""本地流 Power 指标装配（平均/最大/NP/IF/WA/W′ 等）。"""
from typing import Dict, Any, List, Optional
from ...core.analytics.power import normalized_power, work_above_ftp, w_balance_decline


def compute_power_info(stream_data: Dict[str, Any], ftp: int, session_data: Optional[Dict[str, Any]] = None, activity_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    power_data = stream_data.get('power', [])
    valid_powers = [int(p) for p in power_data if p is not None and p > 0]
    if not valid_powers:
        return None

    result: Dict[str, Any] = {}

    result['avg_power'] = int(session_data['avg_power']) if session_data and 'avg_power' in session_data else int(sum(valid_powers) / len(valid_powers))
    result['max_power'] = int(session_data['max_power']) if session_data and 'max_power' in session_data else int(max(valid_powers))
    result['total_work'] = round(sum(valid_powers) / 1000, 0)
    
    if activity_type in ["ride", "virtualride", "ebikeride"]:
        result['normalized_power']       = int(normalized_power(valid_powers))
        result['intensity_factor']       = round(result['normalized_power'] / ftp, 2) if ftp else None
        result['variability_index']      = round(result['normalized_power'] / result['avg_power'], 2) if result['avg_power'] > 0 else None
        result['weighted_average_power'] = None
        result['work_above_ftp']         = None
        result['eftp']                   = None
        w_balance                        = stream_data.get('w_balance', [])
        result['w_balance_decline']      = w_balance_decline(w_balance) if w_balance else None
        return result
    
    else:
        result['normalized_power']       = None
        result['intensity_factor']       = None
        result['variability_index']      = None
        result['weighted_average_power'] = None
        result['work_above_ftp']         = None
        result['eftp']                   = None
        result['w_balance_decline']      = None
        return result

