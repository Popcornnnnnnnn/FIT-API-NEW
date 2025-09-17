from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from ...db.models import TbActivity, TbAthlete, TbAthletePowerRecords
from ...repositories.power_records_repo import (
    update_best_powers as repo_update_best_powers,
    update_longest_ride as repo_update_longest_ride,
    update_max_elevation_gain as repo_update_max_elevation_gain,
)
from ...repositories.best_power_file_repo import update_with_activity_curve as repo_update_best_power_file
from ...schemas.activities import SegmentRecord


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
    """计算 1..N 每个窗口长度下的最佳平均功率曲线（朴素算法）。"""
    try:
        n = len(vals)
        if n == 0:
            return []
        out = [0] * n
        for w in range(1, n + 1):
            s = sum(vals[:w])
            m = s
            for i in range(1, n - w + 1):
                s = s - vals[i - 1] + vals[i + w - 1]
                if s > m:
                    m = s
            out[w - 1] = int(round(m / w))
        return out
    except Exception:
        return []


def analyze_best_powers(activity_data: Dict[str, Any], stream_data: Dict[str, Any], external_id: Optional[int], db: Optional[Session], athlete_id: Optional[int]) -> Tuple[Optional[Dict[str, int]], Optional[List[SegmentRecord]]]:
    if 'watts' not in stream_data:
        return None, None
    try:
        vals = [int(p or 0) for p in stream_data.get('watts', {}).get('data', [])]
        intervals = {
            '5s': 5, '15s': 15, '30s': 30, '1m': 60, '2m': 120, '3m': 180, '5m': 300, '10m': 600, '15m': 900, '20m': 1200, '30m': 1800, '45m': 2700, '60m': 3600
        }
        best_powers: Dict[str, int] = {}
        for k, sec in intervals.items():
            best_powers[k] = _best_avg_over_window(vals, sec)
        # 计算完整最佳曲线，用于文件持久化
        best_curve = _best_power_curve(vals)
        # Optionally update athlete records and produce segment records
        segment_records: List[SegmentRecord] = []
        if db is not None:
            # Determine athlete_id if not provided
            if athlete_id is None and external_id is not None:
                pair = db.query(TbActivity).filter(TbActivity.external_id == external_id).first()
                if pair:
                    athlete_id = pair.athlete_id
            if athlete_id is not None:
                try:
                    activity_id_for_record = int(activity_data.get('activity_id') or external_id or 0)
                except Exception:
                    activity_id_for_record = int(external_id or 0)

                try:
                    sr_dicts = repo_update_best_powers(db, athlete_id, best_powers, activity_id_for_record)
                    for sd in sr_dicts:
                        segment_records.append(SegmentRecord(**sd))
                except Exception:
                    pass

                # 更新最长骑行和最大累计爬升（如果提供）
                try:
                    dist_m = int(activity_data.get('distance') or 0)
                except Exception:
                    dist_m = 0
                try:
                    elev_gain = int(activity_data.get('total_elevation_gain') or 0)
                except Exception:
                    elev_gain = 0

                if dist_m > 0:
                    try:
                        sr = repo_update_longest_ride(db, athlete_id, dist_m, activity_id_for_record)
                        if sr:
                            segment_records.append(SegmentRecord(**sr))
                    except Exception:
                        pass
                if elev_gain > 0:
                    try:
                        sr = repo_update_max_elevation_gain(db, athlete_id, elev_gain, activity_id_for_record)
                        if sr:
                            segment_records.append(SegmentRecord(**sr))
                    except Exception:
                        pass

                # 文件持久化：更新该运动员的全局最佳功率曲线（按秒）
                try:
                    if best_curve:
                        repo_update_best_power_file(athlete_id, best_curve)
                except Exception:
                    pass
        return best_powers, segment_records or None
    except Exception:
        return None, None
