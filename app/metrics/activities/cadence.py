"""本地流踏频指标装配（平均/最大/总踏频、左右相关指标）。"""
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def compute_cadence_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None, activity_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """计算踏频相关信息：平均/最大踏频。

    对于跑步活动，踏频数据需要乘以2（因为设备记录的是单侧步频，需要转换为总步频）。
    
    参数：
        stream_data: 流数据
        session_data: 会话数据（可选）
        is_running: 是否为跑步活动（默认False）
    """
    cadence_raw = stream_data.get('cadence', [])
    cadence = [c for c in cadence_raw if c is not None]
    if not cadence:
        logger.debug("[cadence] no cadence stream; return None")
        return None

    # 如果是跑步活动，踏频需要乘以2（单侧步频 -> 总步频）
    if activity_type in ["run", "trail_run", "virtual_run"]:
        cadence = [c * 2 for c in cadence]

    res: Dict[str, Any] = {}

    # 平均/最大踏频（优先使用 session_data）
    if session_data and 'avg_cadence' in session_data and session_data['avg_cadence'] is not None:
        avg_cad = int(session_data['avg_cadence'])
        # 如果是跑步活动，session_data 中的值也需要乘以2
        if activity_type in ["run", "trail_run", "virtual_run"]:
            avg_cad = int(avg_cad * 2)
        res['avg_cadence'] = avg_cad
    else:
        res['avg_cadence'] = int(sum(cadence) / len(cadence)) if cadence else None

    if session_data and 'max_cadence' in session_data and session_data['max_cadence'] is not None:
        max_cad = int(session_data['max_cadence'])
        # 如果是跑步活动，session_data 中的值也需要乘以2
        if activity_type in ["run", "trail_run", "virtual_run"]:
            max_cad = int(max_cad * 2)
        res['max_cadence'] = max_cad
    else:
        res['max_cadence'] = int(max(cadence)) if cadence else None

    # 对于骑行活动，计算左右平衡、扭矩效率、踏板平顺度等指标
    if activity_type in ["ride", "virtualride", "ebikeride"]:
        # 左右平衡
        lrb = stream_data.get('left_right_balance', [])
        if lrb:
            valid_lrb = [v for v in lrb if v is not None and v >= 0]
            if valid_lrb:
                avg_lrb = sum(valid_lrb) / len(valid_lrb)
                # left_right_balance 通常是百分比（0-100），需要转换为左右值
                # 假设值是左脚的百分比
                left_pct = int(round(avg_lrb))
                right_pct = 100 - left_pct
                res['left_right_balance'] = {'left': left_pct, 'right': right_pct}
            else:
                res['left_right_balance'] = None
        else:
            res['left_right_balance'] = None
        
        # 扭矩效率
        lte = stream_data.get('left_torque_effectiveness', [])
        rte = stream_data.get('right_torque_effectiveness', [])
        if lte:
            valid_lte = [v for v in lte if v is not None and v >= 0]
            res['left_torque_effectiveness'] = round(sum(valid_lte) / len(valid_lte), 2) if valid_lte else None
        else:
            res['left_torque_effectiveness'] = None
        if rte:
            valid_rte = [v for v in rte if v is not None and v >= 0]
            res['right_torque_effectiveness'] = round(sum(valid_rte) / len(valid_rte), 2) if valid_rte else None
        else:
            res['right_torque_effectiveness'] = None
        
        # 踏板平顺度
        lps = stream_data.get('left_pedal_smoothness', [])
        rps = stream_data.get('right_pedal_smoothness', [])
        if lps:
            valid_lps = [v for v in lps if v is not None and v >= 0]
            res['left_pedal_smoothness'] = round(sum(valid_lps) / len(valid_lps), 2) if valid_lps else None
        else:
            res['left_pedal_smoothness'] = None
        if rps:
            valid_rps = [v for v in rps if v is not None and v >= 0]
            res['right_pedal_smoothness'] = round(sum(valid_rps) / len(valid_rps), 2) if valid_rps else None
        else:
            res['right_pedal_smoothness'] = None
        
        # 总踏频（转数）
        try:
            elapsed_time = stream_data.get('elapsed_time', [])
            if elapsed_time and len(elapsed_time) == len(cadence):
                acc = 0.0
                prev = elapsed_time[0] if elapsed_time else 0
                for i in range(1, len(cadence)):
                    dt = max(0, (elapsed_time[i] if i < len(elapsed_time) else elapsed_time[-1]) - prev)
                    acc += (cadence[i] or 0) * (dt / 60.0)
                    prev = elapsed_time[i] if i < len(elapsed_time) else elapsed_time[-1]
                res['total_strokes'] = int(round(acc))
            else:
                # 如果没有时间数据，使用简单的估算
                res['total_strokes'] = int(round(sum(cadence) / 60.0))
        except Exception:
            res['total_strokes'] = None
    else:
        # 非骑行活动，返回 null
        res['left_right_balance'] = None
        res['left_torque_effectiveness'] = None
        res['right_torque_effectiveness'] = None
        res['left_pedal_smoothness'] = None
        res['right_pedal_smoothness'] = None
        res['total_strokes'] = None


    return res
