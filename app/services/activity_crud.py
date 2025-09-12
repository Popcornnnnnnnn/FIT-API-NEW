"""
Slim CRUD helpers moved from app/activities/crud.py
"""

from typing import Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
import requests
from fitparse import FitFile
from io import BytesIO

from ..db.models import TbActivity, TbAthlete
from ..repositories.activity_repo import update_field as repo_update_field, get_activity_athlete as repo_get_activity_athlete
from ..infrastructure.data_manager import activity_data_manager


def update_database_field(db: Session, table_class, record_id: int, field_name: str, value: Any) -> bool:
    return repo_update_field(db, table_class, record_id, field_name, value)


def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    return repo_get_activity_athlete(db, activity_id)


def get_session_data(fit_url: str) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(fit_url)
        if response.status_code != 200:
            return None
        fit_data = response.content
        fitfile = FitFile(BytesIO(fit_data))
        for message in fitfile.get_messages('session'):
            session_data: Dict[str, Any] = {}
            fields = [
                'total_distance', 'total_elapsed_time', 'total_timer_time',
                'avg_power', 'max_power', 'avg_heart_rate', 'max_heart_rate',
                'total_calories', 'total_ascent', 'total_descent',
                'avg_cadence', 'max_cadence', 'left_right_balance',
                'left_torque_effectiveness', 'right_torque_effectiveness',
                'left_pedal_smoothness', 'right_pedal_smoothness',
                'avg_speed', 'max_speed', 'avg_temperature', 'max_temperature', 'min_temperature',
                'normalized_power', 'training_stress_score', 'intensity_factor'
            ]
            for field in fields:
                value = message.get_value(field)
                if value is not None:
                    session_data[field] = value
            return session_data
        return None
    except Exception:
        return None


def get_status(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    try:
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return None
        athlete_id = activity.athlete_id
        from datetime import datetime, timedelta
        from sqlalchemy import func
        forty_two_days_ago = datetime.now() - timedelta(days=42)
        seven_days_ago = datetime.now() - timedelta(days=7)
        avg_tss_42_days = db.query(func.avg(TbActivity.tss)).filter(
            TbActivity.athlete_id == athlete_id,
            TbActivity.start_date >= forty_two_days_ago,
            TbActivity.tss.isnot(None),
            TbActivity.tss > 0,
        ).scalar()
        avg_tss_7_days = db.query(func.avg(TbActivity.tss)).filter(
            TbActivity.athlete_id == athlete_id,
            TbActivity.start_date >= seven_days_ago,
            TbActivity.tss.isnot(None),
            TbActivity.tss > 0,
        ).scalar()
        avg_tss_42_days = round(avg_tss_42_days, 0) if avg_tss_42_days is not None else 0
        avg_tss_7_days = round(avg_tss_7_days, 0) if avg_tss_7_days is not None else 0
        return {"athlete_id": athlete_id, "ctl": avg_tss_42_days, "atl": avg_tss_7_days}
    except Exception:
        return None


def get_activity_best_power_info(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    try:
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None
        best_powers_data = stream_data.get('best_power', [])
        if not best_powers_data:
            return None
        time_intervals = {
            '5s': 5,
            '30s': 30,
            '1min': 60,
            '5min': 300,
            '8min': 480,
            '20min': 1200,
            '30min': 1800,
            '1h': 3600,
        }
        best_powers: Dict[str, int] = {}
        for name, sec in time_intervals.items():
            if len(best_powers_data) >= sec:
                best_powers[name] = best_powers_data[sec - 1]
        return {"best_powers": best_powers}
    except Exception:
        return None

