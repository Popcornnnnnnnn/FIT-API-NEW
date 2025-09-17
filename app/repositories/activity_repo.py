from typing import Optional, Tuple, Any, Type
from sqlalchemy.orm import Session
import logging

from ..db.models import TbActivity, TbAthlete

logger = logging.getLogger(__name__)


def get_activity_by_id(db: Session, activity_id: int) -> Optional[TbActivity]:
    try:
        return db.query(TbActivity).filter(TbActivity.id == activity_id).first()
    except Exception as e:
        logger.error("[db-error][activity-select] activity_id=%s err=%s", activity_id, e)
        return None


def get_athlete_by_id(db: Session, athlete_id: int) -> Optional[TbAthlete]:
    try:
        return db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first()
    except Exception as e:
        logger.error("[db-error][athlete-select] athlete_id=%s err=%s", athlete_id, e)
        return None


def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    try:
        activity = get_activity_by_id(db, activity_id)
        if not activity:
            logger.info("[db-error][activity-athlete] activity not found activity_id=%s", activity_id)
            return None
        athlete = get_athlete_by_id(db, activity.athlete_id)
        if not athlete:
            logger.info("[db-error][activity-athlete] athlete not found activity_id=%s athlete_id=%s", activity_id, getattr(activity, 'athlete_id', None))
            return None
        return activity, athlete
    except Exception as e:
        logger.error("[db-error][activity-athlete] activity_id=%s err=%s", activity_id, e)
        return None


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
