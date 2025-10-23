"""
基于历史最佳功率曲线的 FTP 估算工具。

设计说明（来自产品规格）：
----------------------------------------
- 每位运动员对应的功率曲线存储在 ``data/best_power/<athlete_id>.json``。
  其中 ``best_curve[t-1]`` 代表时长 ``t`` 秒的最大平均功率（MMP）。
- 综合三种互补估计器：
    * FTP_A：P20 快速估算法（20 分钟功率的 95%）。
    * FTP_B：基于时间-做功双参数模型的临界功率（CP）斜率。
    * FTP_C：长时段锚点，优先使用 ≥40/60 分钟覆盖，若缺失则退回 CP 预测。
- 根据覆盖度启发式分配权重：覆盖时长越长，FTP_C 权重越高；不足 20 分钟时加大 CP 权重。
- 通过可信度标签提示下游使用方当前数据的可靠程度。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BEST_POWER_DIR = Path("data/best_power")
_DURATION_GRID = [120, 180, 300, 480, 720, 900, 1200, 1800, 2400, 3600]


@dataclass
class FTPEstimate:
    ftp: Optional[float]
    components: Dict[str, Optional[float]]
    weights: Dict[str, float]
    coverage: Dict[str, bool]
    confidence: str
    notes: Optional[str] = None


def _load_best_curve(athlete_id: int, base_dir: Path = BEST_POWER_DIR) -> Optional[List[float]]:
    path = base_dir / f"{athlete_id}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        curve = payload.get("best_curve") or []
        if not isinstance(curve, list) or not curve:
            return None
        return [float(p) if p is not None else 0.0 for p in curve]
    except (json.JSONDecodeError, OSError, ValueError):
        return None



def _mmp_at(curve: List[float], duration: int) -> Optional[float]:
    if duration <= 0:
        return None
    idx = duration - 1
    if idx < 0 or idx >= len(curve):
        return None
    return float(curve[idx])


def _available_grid(curve: List[float]) -> Tuple[np.ndarray, np.ndarray]:
    points: List[int] = []
    values: List[float] = []
    for sec in _DURATION_GRID:
        val = _mmp_at(curve, sec)
        if val is not None:
            points.append(sec)
            values.append(val)
    return np.asarray(points, dtype=np.float64), np.asarray(values, dtype=np.float64)


def _fit_cp(durations: np.ndarray, powers: np.ndarray) -> Tuple[Optional[float], Optional[float]]:
    if durations.size < 2:
        return None, None
    work = powers * durations
    A = np.vstack([durations, np.ones_like(durations)]).T
    try:
        coeffs, *_ = np.linalg.lstsq(A, work, rcond=None)
        cp, w_prime = coeffs[0], coeffs[1]
        # 简单的离群点剔除：残差大于 2 个标准差的点被丢弃后重新拟合一次。
        predicted = cp * durations + w_prime
        residuals = work - predicted
        std = np.std(residuals)
        if std > 0:
            mask = np.abs(residuals) <= (2.0 * std)
            if mask.sum() >= 2 and mask.sum() != durations.size:
                A_refit = A[mask]
                work_refit = work[mask]
                coeffs_refit, *_ = np.linalg.lstsq(A_refit, work_refit, rcond=None)
                cp, w_prime = coeffs_refit[0], coeffs_refit[1]
        return float(cp), float(w_prime)
    except np.linalg.LinAlgError:
        return None, None


def _estimate_long_duration_component(
    curve: List[float],
    cp: Optional[float],
    w_prime: Optional[float],
) -> Optional[float]:
    # Prefer actual long-duration observations, working backwards from 60 mins.
    target_windows = [
        (3600, 1.00),
        (3000, 0.97),
        (2700, 0.965),
        (2400, 0.96),
        (2100, 0.955),
        (1800, 0.95),
    ]
    for duration, factor in target_windows:
        mmp = _mmp_at(curve, duration)
        if mmp:
            return float(mmp * factor)
    if cp is not None and w_prime is not None:
        # 若无长时段观测，则投影 CP 模型至 60 分钟。
        long_duration = 3600.0
        projected_power = (cp * long_duration + w_prime) / long_duration
        return float(projected_power)
    return cp


def _confidence_label(curve: List[float]) -> str:
    max_duration = len(curve)
    if max_duration >= 1800:
        return "reliable"
    if max_duration >= 900:
        return "medium"
    return "low"


def estimate_ftp_from_best_curve(
    athlete_id: int,
    base_dir: Path = BEST_POWER_DIR,
) -> FTPEstimate:
    """
    读取历史最佳功率曲线并估算 FTP。

    返回值为 FTPEstimate 数据类，包含综合 FTP、各子估计结果、覆盖标记、权重以及可信度。
    """
    curve = _load_best_curve(athlete_id, base_dir=base_dir)
    if not curve:
        return FTPEstimate(
            ftp=None,
            components={"FTP_A": None, "FTP_B": None, "FTP_C": None},
            weights={"FTP_A": 0.0, "FTP_B": 0.0, "FTP_C": 0.0},
            coverage={"cov20": False, "cov40": False, "cov60": False},
            confidence="none",
            notes="best power curve not found",
        )

    cov20 = len(curve) >= 1200
    cov40 = len(curve) >= 2400
    cov60 = len(curve) >= 3600
    coverage = {"cov20": cov20, "cov40": cov40, "cov60": cov60}

    p20 = _mmp_at(curve, 1200)
    ftp_a = float(p20 * 0.95) if p20 is not None else None

    durations, powers = _available_grid(curve)
    cp, w_prime = _fit_cp(durations, powers)
    ftp_b = cp

    ftp_c = _estimate_long_duration_component(curve, cp, w_prime)

    weights = {"FTP_A": 0.0, "FTP_B": 0.0, "FTP_C": 0.0}
    if cov40 or cov60:
        weights.update({"FTP_A": 0.1, "FTP_B": 0.4, "FTP_C": 0.5})
    elif cov20:
        weights.update({"FTP_A": 0.3, "FTP_B": 0.5, "FTP_C": 0.2})
    else:
        weights.update({"FTP_A": 0.4, "FTP_B": 0.6, "FTP_C": 0.0})

    components = {"FTP_A": ftp_a, "FTP_B": ftp_b, "FTP_C": ftp_c}
    valid_keys = [k for k, v in components.items() if v is not None]
    blended_ftp: Optional[float]
    if not valid_keys:
        blended_ftp = None
        norm_weights = {k: 0.0 for k in weights}
    else:
        total_weight = sum(weights[k] for k in valid_keys)
        if total_weight <= 0:
            total_weight = float(len(valid_keys))
            base_weight = 1.0 / total_weight
            norm_weights = {k: (base_weight if k in valid_keys else 0.0) for k in weights}
        else:
            norm_weights = {k: (weights[k] / total_weight if k in valid_keys else 0.0) for k in weights}
        blended_ftp = float(sum(components[k] * norm_weights[k] for k in valid_keys))

    confidence = _confidence_label(curve)
    notes_parts = []
    if cov60:
        notes_parts.append(">=60min coverage")
    elif cov40:
        notes_parts.append(">=40min coverage")
    elif cov20:
        notes_parts.append(">=20min coverage only")
    else:
        notes_parts.append("shorter than 20min curve")
    if ftp_b is None:
        notes_parts.append("CP fit unavailable")
    estimation_notes = "; ".join(notes_parts)

    return FTPEstimate(
        ftp=blended_ftp,
        components=components,
        weights=norm_weights,
        coverage=coverage,
        confidence=confidence,
        notes=estimation_notes or None,
    )


__all__ = ["estimate_ftp_from_best_curve", "FTPEstimate"]
