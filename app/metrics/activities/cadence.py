"""本地流踏频指标装配（平均/最大/总踏频、左右相关指标）。"""
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def compute_cadence_info(stream_data: Dict[str, Any], session_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """计算踏频相关信息：平均/最大/总踏频、左右平衡、TE/PS。

    - total_strokes: 优先使用 `time` 流进行积分；缺失时回退为 sum(cadence)/60。
    - 左右相关：基于各自流求平均，left_right_balance 解析编码值。
    """
    cadence_raw = stream_data.get('cadence', [])
    cadence = [c for c in cadence_raw if c is not None]
    if not cadence:
        logger.debug("[cadence] no cadence stream; return None")
        return None

    time_stream = stream_data.get('time')
    res: Dict[str, Any] = {}

    # 平均/最大踏频（优先使用 session_data）
    if session_data and 'avg_cadence' in session_data and session_data['avg_cadence'] is not None:
        res['avg_cadence'] = int(session_data['avg_cadence'])
    else:
        res['avg_cadence'] = int(sum(cadence) / len(cadence)) if cadence else None

    if session_data and 'max_cadence' in session_data and session_data['max_cadence'] is not None:
        res['max_cadence'] = int(session_data['max_cadence'])
    else:
        res['max_cadence'] = int(max(cadence)) if cadence else None

    logger.debug(
        "[cadence] avg=%s max=%s len=%d",
        res.get('avg_cadence'), res.get('max_cadence'), len(cadence)
    )

    # Torque Effectiveness 平均值
    left_te_list = [v for v in stream_data.get('left_torque_effectiveness', []) if v is not None]
    right_te_list = [v for v in stream_data.get('right_torque_effectiveness', []) if v is not None]
    if left_te_list and right_te_list:
        res['left_torque_effectiveness'] = round(sum(left_te_list) / len(left_te_list), 2)
        res['right_torque_effectiveness'] = round(sum(right_te_list) / len(right_te_list), 2)
    else:
        res['left_torque_effectiveness'] = None
        res['right_torque_effectiveness'] = None
    logger.debug(
        "[cadence] TE L(count=%d)->%s R(count=%d)->%s",
        len(left_te_list), res['left_torque_effectiveness'], len(right_te_list), res['right_torque_effectiveness']
    )

    # Pedal Smoothness 平均值
    left_ps_list = [v for v in stream_data.get('left_pedal_smoothness', []) if v is not None]
    right_ps_list = [v for v in stream_data.get('right_pedal_smoothness', []) if v is not None]
    if left_ps_list and right_ps_list:
        res['left_pedal_smoothness'] = round(sum(left_ps_list) / len(left_ps_list), 2)
        res['right_pedal_smoothness'] = round(sum(right_ps_list) / len(right_ps_list), 2)
    else:
        res['left_pedal_smoothness'] = None
        res['right_pedal_smoothness'] = None
    logger.debug(
        "[cadence] PS L(count=%d)->%s R(count=%d)->%s",
        len(left_ps_list), res['left_pedal_smoothness'], len(right_ps_list), res['right_pedal_smoothness']
    )

    # 左右平衡解析
    def get_left_right_balance() -> Optional[Dict[str, int]]:
        def parse_left_right(value: float) -> Optional[Tuple[int, int]]:
            """解析左右平衡值。
            低位1bit标识侧别，其余为百分比：
            - side_flag=1 表示右侧为百分比；否则左侧为百分比。
            """
            try:
                int_value = int(value)
                side_flag = int_value & 0x01
                percent = int_value >> 1
                if side_flag == 1:
                    right = percent
                    left = 100 - percent
                else:
                    left = percent
                    right = 100 - percent
                return left, right
            except (ValueError, TypeError):
                return None

        lr_raw = stream_data.get('left_right_balance', [])
        if not lr_raw:
            return None

        parsed_values: list[Tuple[int, int]] = []
        for value in lr_raw:
            parsed = parse_left_right(value)
            if parsed:
                parsed_values.append(parsed)

        if parsed_values:
            left_values = [lr[0] for lr in parsed_values]
            right_values = [lr[1] for lr in parsed_values]
            avg_left = int(round(sum(left_values) / len(left_values)))
            avg_right = int(round(sum(right_values) / len(right_values)))
            return {"left": avg_left, "right": avg_right}
        return None

    res['left_right_balance'] = get_left_right_balance()
    logger.debug("[cadence] LR balance -> %s", res['left_right_balance'])

    # 总踏频（积分）
    total_strokes: int
    if isinstance(time_stream, list) and len(time_stream) == len(cadence):
        strokes = 0.0
        # 使用梯形积分法，更稳定
        for i in range(1, len(cadence)):
            t0 = time_stream[i - 1]
            t1 = time_stream[i]
            try:
                dt = float(t1) - float(t0)
            except (TypeError, ValueError):
                dt = 0.0
            if dt <= 0:
                continue
            rpm0 = float(cadence[i - 1])
            rpm1 = float(cadence[i])
            rpm_avg = (rpm0 + rpm1) / 2.0
            strokes += rpm_avg / 60.0 * dt
        total_strokes = int(strokes)
        logger.debug("[cadence] total_strokes (integral with time) = %d", total_strokes)
    else:
        # 无时间流：退化估计
        total_strokes = int(sum(cadence) / 60.0)
        logger.debug(
            "[cadence] total_strokes (fallback) = %d; len(cadence)=%d has_time=%s",
            total_strokes, len(cadence), isinstance(time_stream, list)
        )

    res['total_strokes'] = total_strokes
    return res
