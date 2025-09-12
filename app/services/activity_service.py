"""
Activity service: orchestrates data retrieval (Strava or local) and analytics,
returning response models defined in activities.schemas.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
import logging

from ..clients.strava_client import StravaClient, StravaApiError
from ..activities.schemas import AllActivityDataResponse, ZoneData
from ..activities.crud import (
    get_activity_overall_info,
    get_activity_power_info,
    get_activity_heartrate_info,
    get_activity_cadence_info,
    get_activity_speed_info,
    get_activity_altitude_info,
    get_activity_temperature_info,
    get_activity_training_effect_info,
    get_activity_best_power_info,
    get_activity_power_zones,
    get_activity_heartrate_zones,
)
from ..streams.crud import stream_crud
from ..streams.models import Resolution
from ..activities.data_manager import activity_data_manager
from ..activities.strava_analyzer import StravaAnalyzer


logger = logging.getLogger(__name__)


class ActivityService:
    def get_all_data(
        self,
        db: Session,
        activity_id: int,
        access_token: Optional[str],
        keys: Optional[str],
        resolution: str,
    ) -> AllActivityDataResponse:
        if access_token:
            # Strava path
            client = StravaClient(access_token)
            keys_list_all = [
                'time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
                'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth'
            ]
            full = client.fetch_full(activity_id, keys=keys_list_all, resolution=None)
            activity_data = full['activity']
            stream_data = full['streams']
            athlete_data = full['athlete']

            if keys:
                keys_list = [k.strip() for k in keys.split(',') if k.strip()]
            else:
                keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']

            return StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)

        # Local DB path
        response_data = {}
        info_funcs = [
            ("overall", get_activity_overall_info),
            ("power", get_activity_power_info),
            ("heartrate", get_activity_heartrate_info),
            ("cadence", get_activity_cadence_info),
            ("speed", get_activity_speed_info),
            ("training_effect", get_activity_training_effect_info),
            ("altitude", get_activity_altitude_info),
            ("temp", get_activity_temperature_info),
        ]
        for key_name, func in info_funcs:
            try:
                info = func(db, activity_id)
                response_data[key_name] = info
            except Exception:
                response_data[key_name] = None

        # zones
        zones_data = []
        try:
            pz = get_activity_power_zones(db, activity_id)
            if pz:
                zones_data.append(ZoneData(**pz))
        except Exception:
            pass
        try:
            hz = get_activity_heartrate_zones(db, activity_id)
            if hz:
                zones_data.append(ZoneData(**hz))
        except Exception:
            pass
        response_data["zones"] = zones_data if zones_data else None

        # streams
        try:
            available_result = stream_crud.get_available_streams(db, activity_id)
            if available_result["status"] == "success":
                available_streams = [
                    s for s in available_result["available_streams"]
                    if s not in ("left_right_balance", "position_lat", "position_long")
                ]
                res_enum = Resolution.HIGH if resolution == 'high' else Resolution.MEDIUM if resolution == 'medium' else Resolution.LOW
                streams_data = activity_data_manager.get_activity_streams(db, activity_id, available_streams, res_enum)
                for stream in streams_data or []:
                    if stream["type"] == "temperature":
                        stream["type"] = "temp"
                    if stream["type"] == "heart_rate":
                        stream["type"] = "heartrate"
                    if stream["type"] == "power":
                        stream["type"] = "watts"
                    if stream["type"] == "timestamp":
                        stream["type"] = "time"
                response_data["streams"] = streams_data
            else:
                response_data["streams"] = None
        except Exception as e:
            logger.error(f"streams error: {e}")
            response_data["streams"] = None

        return AllActivityDataResponse(**response_data)

    # Individual metric endpoints (local DB path)
    def get_overall(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.overall import compute_overall_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        result = compute_overall_info(stream_data, session_data, athlete)
        # add status
        try:
            from ..activities.crud import get_status
            status = get_status(db, activity_id)
            if status:
                result['status'] = round(status['ctl'] - status['atl'], 0)
        except Exception:
            pass
        return result

    def get_power(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.power import compute_power_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_power_info(stream_data, int(athlete.ftp), session_data)

    def get_heartrate(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.heartrate import compute_heartrate_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_heartrate_info(stream_data, bool(stream_data.get('power')), session_data)

    def get_speed(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.speed import compute_speed_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, _athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_speed_info(stream_data, session_data)

    def get_altitude(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.altitude import compute_altitude_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, _athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_altitude_info(stream_data, session_data)

    def get_temperature(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..activities.metrics.temperature import compute_temperature_info
        from ..activities.data_manager import activity_data_manager
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        return compute_temperature_info(stream_data)

    def get_training_effect(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..repositories.activity_repo import get_activity_athlete
        from ..activities.data_manager import activity_data_manager
        from ..core.analytics.training import (
            aerobic_effect, anaerobic_effect, power_zone_percentages,
            power_zone_times, calculate_training_load
        )
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        power = stream_data.get('power', [])
        if not power:
            return None
        ftp = int(athlete.ftp)
        ae = aerobic_effect(power, ftp)
        ne = anaerobic_effect(power, ftp)
        zd = power_zone_percentages(power, ftp)
        zt = power_zone_times(power, ftp)
        # primary benefit
        from ..core.analytics.training import primary_training_benefit
        pb, _ = primary_training_benefit(zd, zt, round(len(power)/60, 0), ae, ne, ftp, max(power))
        avg_power = int(sum(power)/len(power)) if power else 0
        tss = calculate_training_load(avg_power, ftp, len(power))
        return {
            'primary_training_benefit': pb,
            'aerobic_effect': ae,
            'anaerobic_effect': ne,
            'training_load': tss,
            'carbohydrate_consumption': None,
        }


activity_service = ActivityService()
