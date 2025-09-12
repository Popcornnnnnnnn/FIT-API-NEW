"""本地流踏频指标装配（平均/最大/总踏频）。"""
from typing import Dict, Any, Optional


def compute_cadence_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    cadence = stream_data.get('cadence', [])
    if not cadence:
        return None
    res: Dict[str, Any] = {}
    if session_data and 'avg_cadence' in session_data:
        res['avg_cadence'] = int(session_data['avg_cadence'])
    else:
        res['avg_cadence'] = int(sum(cadence) / len(cadence)) if cadence else None
    if session_data and 'max_cadence' in session_data:
        res['max_cadence'] = int(session_data['max_cadence'])
    else:
        res['max_cadence'] = int(max(cadence)) if cadence else None
    res['left_right_balance'] = None
    res['left_torque_effectiveness'] = None
    res['right_torque_effectiveness'] = None
    res['left_pedal_smoothness'] = None
    res['right_pedal_smoothness'] = None
    res['total_strokes'] = int(sum(c/60 for c in cadence if c is not None))
    return res
