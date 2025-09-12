from typing import Optional, Tuple, Any, Type
from sqlalchemy.orm import Session

from ..db.models import TbActivity, TbAthlete


def get_activity_by_id(db: Session, activity_id: int) -> Optional[TbActivity]:
    return db.query(TbActivity).filter(TbActivity.id == activity_id).first()


def get_athlete_by_id(db: Session, athlete_id: int) -> Optional[TbAthlete]:
    return db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first()


def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    activity = get_activity_by_id(db, activity_id)
    if not activity:
        return None
    athlete = get_athlete_by_id(db, activity.athlete_id)
    if not athlete:
        return None
    return activity, athlete


def update_field(db: Session, table_class: Type[Any], record_id: int, field_name: str, value: Any) -> bool:
    try:
        record = db.query(table_class).filter(table_class.id == record_id).first()
        if not record or not hasattr(record, field_name):
            return False
        setattr(record, field_name, value)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False

