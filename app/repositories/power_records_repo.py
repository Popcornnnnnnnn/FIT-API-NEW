"""运动员最佳功率纪录写库仓库（Repository）。"""
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..db.models import TbAthletePowerRecords


INTERVAL_FIELD_MAP: Dict[str, str] = {
    '5s': '5s', '15s': '15s', '30s': '30s', '1m': '1m', '2m': '2m', '3m': '3m',
    '5m': '5m', '10m': '10m', '15m': '15m', '20m': '20m', '30m': '30m', '45m': '45m', '60m': '60m'
}


def get_or_create_records(db: Session, athlete_id: int) -> TbAthletePowerRecords:
    """按 athlete_id 获取或创建功率纪录行。"""
    rec = db.query(TbAthletePowerRecords).filter(TbAthletePowerRecords.athlete_id == athlete_id).first()
    if not rec:
        rec = TbAthletePowerRecords(athlete_id=athlete_id)
        db.add(rec)
        db.commit()
        db.refresh(rec)
    return rec


def _field_names(interval_key: str) -> Tuple[str, str, str, str, str, str]:
    """将时间窗键转为 ORM 字段名（Top3）。"""
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
    """按给定 best_powers 更新某运动员各时间窗的 Top3。

    返回：包含以下键的字典列表：
        segment_name/current_value/rank/activity_id/record_type/unit/previous_record/improvement
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
        cur1a = getattr(rec, f1a)
        cur2a = getattr(rec, f2a)
        cur3a = getattr(rec, f3a)

        rank = 0
        prev = None

        # 若该活动已在该时间窗的任一排名中，占位，则跳过该时间窗，避免重复请求将同一活动写入多个名次
        if cur1a == activity_id_for_record or cur2a == activity_id_for_record or cur3a == activity_id_for_record:
            continue

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


def _update_top3_single_metric(
    db: Session,
    rec: TbAthletePowerRecords,
    base_field: str,
    value: int,
    activity_id_for_record: int,
    record_type: str,
    unit: str,
    segment_name: str,
) -> Optional[Dict[str, object]]:
    """通用的单指标 Top3 更新：如最长骑行、最大爬升。

    返回发生更新时的 segment_record 字典；否则返回 None。
    """
    f1 = f"{base_field}_1st"
    f1a = f"{base_field}_1st_activity_id"
    f2 = f"{base_field}_2nd"
    f2a = f"{base_field}_2nd_activity_id"
    f3 = f"{base_field}_3rd"
    f3a = f"{base_field}_3rd_activity_id"

    cur1 = getattr(rec, f1)
    cur2 = getattr(rec, f2)
    cur3 = getattr(rec, f3)

    rank = 0
    prev = None

    if cur1 is None or value > (cur1 or 0):
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
        return {
            'segment_name': segment_name,
            'current_value': value,
            'rank': rank,
            'activity_id': activity_id_for_record,
            'record_type': record_type,
            'unit': unit,
            'previous_record': prev,
            'improvement': improvement,
        }
    return None


def update_longest_ride(
    db: Session,
    athlete_id: int,
    distance_m: int,
    activity_id_for_record: int,
) -> Optional[Dict[str, object]]:
    """更新最长骑行距离 Top3（单位：公里，四舍五入到整数公里）。"""
    rec = get_or_create_records(db, athlete_id)
    km = int(round((distance_m or 0) / 1000.0))
    sr = _update_top3_single_metric(
        db, rec, 'longest_ride', km, activity_id_for_record, 'distance', 'km', 'longest_ride'
    )
    db.commit()
    return sr


def update_max_elevation_gain(
    db: Session,
    athlete_id: int,
    elevation_gain_m: int,
    activity_id_for_record: int,
) -> Optional[Dict[str, object]]:
    """更新最大累计爬升 Top3（单位：米）。"""
    rec = get_or_create_records(db, athlete_id)
    meters = int(elevation_gain_m or 0)
    sr = _update_top3_single_metric(
        db, rec, 'max_elevation', meters, activity_id_for_record, 'elevation', 'm', 'max_elevation_gain'
    )
    db.commit()
    return sr
