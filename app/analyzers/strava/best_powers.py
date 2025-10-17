from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from time import perf_counter
import logging
import numpy as np
from ...db.models import TbActivity, TbAthlete, TbAthletePowerRecords
from ...repositories.power_records_repo import (
    update_best_powers as repo_update_best_powers,
    update_longest_ride as repo_update_longest_ride,
    update_max_elevation_gain as repo_update_max_elevation_gain,
)
from ...repositories.best_power_file_repo import update_with_activity_curve as repo_update_best_power_file
from ...schemas.activities import SegmentRecord

logger = logging.getLogger(__name__)


def _get_activity_athlete_by_external_id(db: Session, external_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    activity = db.query(TbActivity).filter(TbActivity.external_id == external_id).first()
    if not activity or not getattr(activity, 'athlete_id', None):
        return None
    athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
    if not athlete:
        return None
    return activity, athlete


def _best_avg_over_window(vals: List[int], window: int) -> int:
    if not vals or len(vals) < window:
        return 0
    s = sum(vals[:window])
    m = s
    for i in range(1, len(vals)-window+1):
        s = s - vals[i-1] + vals[i+window-1]
        if s > m:
            m = s
    return int(round(m/window))


def _best_power_curve(vals: List[int]) -> List[int]:
    """计算 1..N 每个窗口长度下的最佳平均功率曲线。

    备注：
        - 旧实现使用两层 Python 循环，复杂度 O(n^2) 且运行在解释器里，数据量稍大就会卡顿。
        - 这里改用 numpy 前缀和，将「长度为 w 的窗口和」改写为向量化减法，
          每个窗口长度仍需 O(n) 次运算，但都在 C 层完成，显著降低 Python 端开销。
    """
    if not vals:
        return []

    arr = np.asarray(vals, dtype=np.float64)
    n = arr.size
    prefix = np.concatenate(([0.0], arr.cumsum()))
    best = np.empty(n, dtype=np.int32)

    for window in range(1, n + 1):
        window_sums = prefix[window:] - prefix[:-window]
        best[window - 1] = int(round(window_sums.max() / window))

    return best.tolist()


def analyze_best_powers(
    activity_data: Dict[str, Any], 
    stream_data: Dict[str, Any], 
    external_id: Optional[int], 
    db: Optional[Session], 
    athlete_entry: Optional[int],
    activity_entry: Optional[Any] = None,
    ) -> Tuple[Optional[Dict[str, int]], Optional[List[SegmentRecord]]]:
    perf_marks: List[Tuple[str, float]] = [("start", perf_counter())]
    if 'watts' not in stream_data:
        perf_marks.append(("no_watts", perf_counter()))
        # _log_perf(external_id or 0, perf_marks)
        return None, None
    try:
        vals = [int(p or 0) for p in stream_data.get('watts', {}).get('data', [])]
        perf_marks.append(("power_extract", perf_counter()))
        intervals = {
            '5s': 5, '15s': 15, '30s': 30, '1m': 60, '2m': 120, '3m': 180, '5m': 300, '10m': 600, '15m': 900, '20m': 1200, '30m': 1800, '45m': 2700, '60m': 3600
        }
        best_powers: Dict[str, int] = {}
        for k, sec in intervals.items():
            best_powers[k] = _best_avg_over_window(vals, sec)
        perf_marks.append(("interval_windows", perf_counter()))
        # 计算完整最佳曲线，用于文件持久化
        best_curve = _best_power_curve(vals) # ! SLOW
        perf_marks.append(("best_curve", perf_counter()))

        # Optionally update athlete records and produce segment records
        segment_records: List[SegmentRecord] = []
        if db is not None: # ! SLOW
            sr_dicts = repo_update_best_powers(db, athlete_entry.id, best_powers, activity_entry.id)
            for sd in sr_dicts:
                segment_records.append(SegmentRecord(**sd))

            perf_marks.append(("db_power_records", perf_counter())) 

            dist_m = int(activity_data.get('distance') or 0)
            elev_gain = int(activity_data.get('total_elevation_gain') or 0)

            if dist_m > 0:
                try:
                    sr = repo_update_longest_ride(db, athlete_entry.id, dist_m, activity_entry.id)
                    if sr:
                        segment_records.append(SegmentRecord(**sr))
                except Exception:
                    pass
            if elev_gain > 0:
                try:
                    sr = repo_update_max_elevation_gain(db, athlete_entry.id, elev_gain, activity_entry.id)
                    if sr:
                        segment_records.append(SegmentRecord(**sr))
                except Exception:
                    pass
            perf_marks.append(("db_longest_elev", perf_counter()))

            # 文件持久化：更新该运动员的全局最佳功率曲线（按秒）
            try:
                if best_curve:
                    repo_update_best_power_file(athlete_entry.id, best_curve)
            except Exception:
                pass
            perf_marks.append(("file_persist", perf_counter()))
        return best_powers, segment_records or None
    except Exception:
        return None, None
    finally:
        perf_marks.append(("end", perf_counter()))
        # _log_perf(external_id or 0, perf_marks)


def _log_perf(activity_id: int, marks: List[Tuple[str, float]]) -> None:
    if not marks or len(marks) < 2:
        return
    segments = []
    prev = marks[0][1]
    for label, ts in marks[1:]:
        segments.append(f"{label}={(ts - prev) * 1000:.1f}ms")
        prev = ts
    total = (marks[-1][1] - marks[0][1]) * 1000
    logger.info(
        "[perf][best_powers.analyze] activity_id=%s total=%.1fms %s\n",
        activity_id,
        total,
        " | ".join(segments),
    )
