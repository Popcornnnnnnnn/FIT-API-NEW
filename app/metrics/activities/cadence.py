"""本地流踏频指标装配（平均/最大/总踏频、左右相关指标）。"""
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def compute_cadence_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None, is_running: bool = False) -> Optional[Dict[str, Any]]:
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
    if is_running:
        cadence = [c * 2 for c in cadence]

    res: Dict[str, Any] = {}

    # 平均/最大踏频（优先使用 session_data）
    if session_data and 'avg_cadence' in session_data and session_data['avg_cadence'] is not None:
        avg_cad = int(session_data['avg_cadence'])
        # 如果是跑步活动，session_data 中的值也需要乘以2
        if is_running:
            avg_cad = int(avg_cad * 2)
        res['avg_cadence'] = avg_cad
    else:
        res['avg_cadence'] = int(sum(cadence) / len(cadence)) if cadence else None

    if session_data and 'max_cadence' in session_data and session_data['max_cadence'] is not None:
        max_cad = int(session_data['max_cadence'])
        # 如果是跑步活动，session_data 中的值也需要乘以2
        if is_running:
            max_cad = int(max_cad * 2)
        res['max_cadence'] = max_cad
    else:
        res['max_cadence'] = int(max(cadence)) if cadence else None

    logger.debug(
        "[cadence] avg=%s max=%s len=%d is_running=%s",
        res.get('avg_cadence'), res.get('max_cadence'), len(cadence), is_running
    )

    return res
