from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..db.models import TbAthletePowerRecords


INTERVAL_FIELD_MAP: Dict[str, str] = {
    '5s': '5s', '15s': '15s', '30s': '30s', '1m': '1m', '2m': '2m', '3m': '3m',
    '5m': '5m', '10m': '10m', '15m': '15m', '20m': '20m', '30m': '30m', '45m': '45m', '60m': '60m'
}


def get_or_create_records(db: Session, athlete_id: int) -> TbAthletePowerRecords:
    rec = db.query(TbAthletePowerRecords).filter(TbAthletePowerRecords.athlete_id == athlete_id).first()
    if not rec:
        rec = TbAthletePowerRecords(athlete_id=athlete_id)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def _field_names(interval_key: str) -> Tuple[str, str, str, str, str, str]:
    suf = INTERVAL_FIELD_MAP.get(interval_key)
    if not suf:
        raise ValueError(f"Unsupported interval: {interval_key}")
    f1 = f"power_{suf}_1st"
    f1a = f"power_{suf}_1st_activity_id"
    f2 = f"power_{suf}_2nd"
    f2a = f"power_{suf}_2nd_activity_id"
    f3 = f"power_{suf}_3rd"
    f3a = f"power_{suf}_3rd_activity_id"
    return f1, f1a, f2, f2a, f3, f3a


def update_best_powers(
    db: Session,
    athlete_id: int,
    best_powers: Dict[str, int],
    activity_id_for_record: int,
) -> List[Dict[str, object]]:
    """Update athlete best powers top-3 for provided intervals.

    Returns a list of segment record dicts with fields:
      segment_name, current_value, rank, activity_id, record_type, unit, previous_record, improvement
    """
    rec = get_or_create_records(db, athlete_id)
    segment_records: List[Dict[str, object]] = []

    for interval, value in best_powers.items():
        try:
            f1, f1a, f2, f2a, f3, f3a = _field_names(interval)
        except ValueError:
            continue

        cur1 = getattr(rec, f1)
        cur2 = getattr(rec, f2)
        cur3 = getattr(rec, f3)

        rank = 0
        prev = None

        if cur1 is None or value > (cur1 or 0):
            # shift down 1->2, 2->3
            setattr(rec, f3, cur2)
            setattr(rec, f3a, getattr(rec, f2a))
            setattr(rec, f2, cur1)
            setattr(rec, f2a, getattr(rec, f1a))
            prev = cur1
            setattr(rec, f1, value)
            setattr(rec, f1a, activity_id_for_record)
            rank = 1
        elif cur2 is None or value > (cur2 or 0):
            setattr(rec, f3, cur2)
            setattr(rec, f3a, getattr(rec, f2a))
            prev = cur2
            setattr(rec, f2, value)
            setattr(rec, f2a, activity_id_for_record)
            rank = 2
        elif cur3 is None or value > (cur3 or 0):
            prev = cur3
            setattr(rec, f3, value)
            setattr(rec, f3a, activity_id_for_record)
            rank = 3

        if rank > 0:
            improvement = (value - prev) if prev is not None else value
            segment_records.append({
                'segment_name': f"best_power_{interval}",
                'current_value': value,
                'rank': rank,
                'activity_id': activity_id_for_record,
                'record_type': 'power',
                'unit': 'W',
                'previous_record': prev,
                'improvement': improvement,
            })

    db.commit()
    return segment_records

