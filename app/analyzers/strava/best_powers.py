from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from ...db.models import TbActivity, TbAthlete, TbAthletePowerRecords
from ...repositories.power_records_repo import update_best_powers as repo_update_best_powers
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
                    sr_dicts = repo_update_best_powers(db, athlete_id, best_powers, activity_data.get('activity_id') or external_id or 0)
                    for sd in sr_dicts:
                        segment_records.append(SegmentRecord(**sd))
                except Exception:
                    pass
        return best_powers, segment_records or None
    except Exception:
        return None, None
