"""基于文件的运动员最佳功率曲线仓库。

数据位置：data/best_power/{athlete_id}.json
结构：
{
  "athlete_id": 123,
  "updated_at": "2025-09-15T12:34:56Z",
  "best_curve": [int, ...]  # 1秒起始的每秒最佳平均功率
}
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
import os
import json
from datetime import datetime, timezone


BASE_DIR = os.path.join("data", "best_power")


def _ensure_dir() -> None:
    os.makedirs(BASE_DIR, exist_ok=True)


def _file_path(athlete_id: int) -> str:
    return os.path.join(BASE_DIR, f"{athlete_id}.json")


def load_best_curve(athlete_id: int) -> Optional[List[int]]:
    """读取该运动员的最佳功率曲线，若不存在返回 None。"""
    try:
        _ensure_dir()
        fp = _file_path(athlete_id)
        if not os.path.exists(fp):
            return None
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        curve = data.get("best_curve")
        if isinstance(curve, list):
            return [int(x or 0) for x in curve]
        return None
    except Exception:
        return None


def save_best_curve(athlete_id: int, curve: List[int]) -> None:
    """覆盖保存该运动员的最佳功率曲线。"""
    _ensure_dir()
    payload: Dict[str, Any] = {
        "athlete_id": int(athlete_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "best_curve": [int(x or 0) for x in curve],
    }
    with open(_file_path(athlete_id), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def update_with_activity_curve(athlete_id: int, activity_curve: List[int]) -> List[int]:
    """用某次活动的曲线更新全局最佳曲线（逐秒取最大）。返回更新后的曲线。"""
    existing = load_best_curve(athlete_id) or []
    m = max(len(existing), len(activity_curve))
    merged: List[int] = [0] * m
    for i in range(m):
        a = existing[i] if i < len(existing) else 0
        b = activity_curve[i] if i < len(activity_curve) else 0
        merged[i] = int(a) if a >= b else int(b)
    save_best_curve(athlete_id, merged)
    return merged

