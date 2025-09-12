"""训练效果与区间分析核心算法

说明：
- 本模块提供训练负荷（TSS 类似指标）、卡路里估算、有氧/无氧效果、功率区间统计等通用算法；
- 这些算法既可用于 Strava 流，也可用于本地 FIT 解析后的流，输入为简单的列表/标量；
- 不依赖数据库或网络，便于单元测试与复用。
"""

from typing import Optional, List, Dict, Any, Tuple
from .power import normalized_power
from .zones import analyze_power_zones
from .time_utils import parse_time_str


def calculate_training_load(avg_power: int, ftp: int, duration_seconds: int) -> int:
    """计算训练负荷（类似 TSS 的量纲），简化实现。

    参数：
        avg_power: 平均功率（W）
        ftp: 功能阈值功率（W）
        duration_seconds: 训练时长（秒）

    返回：
        训练负荷整数值，若输入不合法返回 0
    """
    if not ftp or ftp <= 0 or not avg_power or avg_power <= 0 or duration_seconds <= 0:
        return 0
    intensity_factor = avg_power / ftp
    duration_hours = duration_seconds / 3600.0
    training_load = (intensity_factor ** 2) * duration_hours
    return int(training_load * 100)


def estimate_calories_with_power(avg_power: int, duration_seconds: int, weight_kg: int) -> Optional[int]:
    """使用功率估算卡路里（简化）：功率做功 + 轻量 BMR 贡献。

    注意：此估算非常粗略，仅用于近似展示。
    """
    try:
        # Simplified: power (W) over time + small BMR component
        power_calories = avg_power * duration_seconds / 3600  # Wh approx to kcal (roughly comparable)
        bmr_per_minute = 1.2
        bmr_calories = bmr_per_minute * duration_seconds / 60
        total = power_calories + bmr_calories
        return int(total)
    except Exception:
        return None


def estimate_calories_with_heartrate(avg_heartrate: int, duration_seconds: int, weight_kg: int) -> Optional[int]:
    """使用心率估算卡路里（简化版 Keytel 近似）。"""
    try:
        # Keytel-like rough estimate for moderate intensity (male, approximated constants)
        return round((duration_seconds / 60) * (0.6309 * avg_heartrate + 0.1988 * weight_kg + 6 - 55.0969) / 4.184, 0)
    except Exception:
        return None


def aerobic_effect(power_data: List[int], ftp: int) -> float:
    """有氧效果（AE）：基于 NP 与训练时长的简化刻画（0.0~5.0）。"""
    try:
        np = normalized_power(power_data)
        if not ftp:
            return 0.0
        intensity_factor = np / ftp
        return round(min(5.0, intensity_factor * len(power_data) / 3600 + 0.5), 1)
    except Exception:
        return 0.0


def anaerobic_effect(power_data: List[int], ftp: int) -> float:
    """无氧效果（NE）：结合 30s 峰值与高于 FTP 的做功量（0.0~4.0）。"""
    try:
        if not power_data or not ftp:
            return 0.0
        n = len(power_data)
        if n < 30:
            return 0.0
        # 30s peak power
        window = 30
        window_sum = sum(power_data[:window])
        max_avg = window_sum / window
        for i in range(1, n - window + 1):
            window_sum = window_sum - power_data[i - 1] + power_data[i + window - 1]
            avg = window_sum / window
            if avg > max_avg:
                max_avg = avg
        anaerobic_capacity = sum(max(0, p - ftp) for p in power_data if p is not None) / 1000.0
        anaerobic = min(4.0, 0.1 * (max_avg / ftp) + 0.05 * anaerobic_capacity)
        return round(anaerobic, 1)
    except Exception:
        return 0.0


def power_zone_percentages(power_data: List[int], ftp: int) -> List[float]:
    """功率区间百分比（0~6 区间，对应 Z1~Z7）"""
    zones = analyze_power_zones(power_data, ftp)
    out = []
    for z in zones:
        ps = str(z.get('percentage', '0.0%')).replace('%', '')
        try:
            out.append(float(ps))
        except Exception:
            out.append(0.0)
    return out


def power_zone_times(power_data: List[int], ftp: int) -> List[int]:
    """功率区间时长（秒）"""
    zones = analyze_power_zones(power_data, ftp)
    out = []
    for z in zones:
        out.append(parse_time_str(z.get('time', '0s')))
    return out


def primary_training_benefit(
    zone_distribution: List[float],
    zone_times: List[int],
    duration_min: int,
    aerobic_effect_val: float,
    anaerobic_effect_val: float,
    ftp: int,
    max_power: int,
) -> Tuple[str, List[str]]:
    """综合评估主要训练收益类型（返回主/副类型）。

    规则基于区间分布/时长与 AE/NE 的经验条件组合，结果仅供参考。
    """
    if duration_min < 5:
        return "时间过短, 无法判断", []

    ae_to_ne_ratio = aerobic_effect_val / (anaerobic_effect_val + 0.001)
    # Align indexing with previous logic
    zd = [0.0] + zone_distribution
    zt = [0] + zone_times
    intensity_ratio = (max_power / ftp) if ftp else 0

    rules = [
        {
            "name": "Recovery",
            "conditions": [
                zd[1] > 85,
                aerobic_effect_val < 1.5,
                anaerobic_effect_val < 0.5,
                duration_min < 90,
            ],
            "required": 3,
        },
        {
            "name": "Endurance (LSD)",
            "conditions": [
                zd[2] > 60,
                aerobic_effect_val > 2.5,
                anaerobic_effect_val < 1.0,
                duration_min >= 90,
                ae_to_ne_ratio > 3.0,
            ],
            "required": 4,
        },
        {
            "name": "Tempo",
            "conditions": [
                zd[3] > 40,
                zd[4] < 30,
                aerobic_effect_val > 2.0,
                anaerobic_effect_val < 1.5,
                ae_to_ne_ratio > 1.5,
            ],
            "required": 4,
        },
        {
            "name": "Threshold",
            "conditions": [
                zd[4] > 35,
                zd[5] < 25,
                aerobic_effect_val > 3.0,
                anaerobic_effect_val > 1.0,
                1.0 < ae_to_ne_ratio < 2.5,
            ],
            "required": 4,
        },
        {
            "name": "VO2Max Intervals",
            "conditions": [
                zd[5] > 25,
                zt[5] > 8 * 60,
                anaerobic_effect_val > 2.5,
                intensity_ratio > 1.3,
                ae_to_ne_ratio < 1.5,
            ],
            "required": 4,
        },
        {
            "name": "Anaerobic Intervals",
            "conditions": [
                zd[6] > 15,
                anaerobic_effect_val > 3.0,
                intensity_ratio > 1.5,
                ae_to_ne_ratio < 1.0,
                zt[6] > 3 * 60,
            ],
            "required": 4,
        },
        {
            "name": "Sprint Training",
            "conditions": [
                zd[7] > 8,
                anaerobic_effect_val > 3.5,
                intensity_ratio > 1.8,
                zt[7] > 60,
                ae_to_ne_ratio < 0.5,
            ],
            "required": 4,
        },
    ]

    matched = []
    for r in rules:
        matches = sum(1 for c in r["conditions"] if c)
        if matches >= r["required"]:
            matched.append(r["name"])
    if not matched:
        return "Mixed", []
    return matched[0], matched[1:]
