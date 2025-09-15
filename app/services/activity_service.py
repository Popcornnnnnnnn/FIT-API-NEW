"""Activity Service（活动服务编排层）

职责：
- 统一编排数据来源（Strava 或 本地数据流）与分析逻辑（metrics/core）；
- 组合多种单项结果，返回 AllActivityDataResponse（对外响应模型）；
- 暴露 get_overall/get_power/... 单项装配方法，便于路由端直接复用。
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from ..clients.strava_client import StravaClient
from ..schemas.activities import AllActivityDataResponse, ZoneData
from ..streams.crud import stream_crud
from ..streams.models import Resolution
from ..infrastructure.data_manager import activity_data_manager
from ..analyzers.strava_analyzer import StravaAnalyzer
from ..core.analytics import zones as ZoneAnalyzer


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

            result = StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)
            # 计算 training_load，更新该活动的 TSS，并据此刷新 athlete 的 TSB（status）
            try:
                from ..core.analytics.training import calculate_training_load
                moving_time = int(activity_data.get('moving_time') or 0)
                avg_power = None
                if activity_data.get('average_watts'):
                    try:
                        avg_power = int(activity_data.get('average_watts'))
                    except Exception:
                        avg_power = None
                if avg_power is None and 'watts' in stream_data:
                    try:
                        pw = [p or 0 for p in stream_data.get('watts', {}).get('data', [])]
                        avg_power = int(sum(pw)/len(pw)) if pw else None
                    except Exception:
                        avg_power = None

                # 解析 Strava 活动开始时间，用于补齐本地 activity.start_date 便于窗口统计
                start_dt = None
                try:
                    raw = activity_data.get('start_date') or activity_data.get('start_date_local')
                    if isinstance(raw, str) and raw:
                        # 支持 2025-09-13T12:34:56Z 或 2025-09-13T12:34:56+00:00
                        iso = raw.replace('Z', '+00:00')
                        start_dt = datetime.fromisoformat(iso).replace(tzinfo=None)
                except Exception:
                    start_dt = None

                athlete_id = self._upsert_activity_tss(db, activity_id, avg_power, moving_time, start_dt)
                tsb = self._update_athlete_status(db, athlete_id, start_dt) if athlete_id else None
                tl = None
                if athlete_id:
                    try:
                        from ..db.models import TbAthlete
                        ftp = int(db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first().ftp)
                    except Exception:
                        ftp = 0
                    tl = calculate_training_load(avg_power, ftp, moving_time) if (avg_power and ftp and moving_time) else None
                if result and getattr(result, 'overall', None):
                    if result.overall is not None:
                        result.overall.status = tsb
                        result.overall.training_load = tl
            except Exception:
                pass
            return result

        # Local DB path: compose using service methods and metrics
        response_data = {}
        try:
            response_data["overall"] = self.get_overall(db, activity_id)
        except Exception:
            response_data["overall"] = None
        try:
            response_data["power"] = self.get_power(db, activity_id)
        except Exception:
            response_data["power"] = None
        try:
            response_data["heartrate"] = self.get_heartrate(db, activity_id)
        except Exception:
            response_data["heartrate"] = None
        try:
            response_data["cadence"] = self.get_cadence(db, activity_id)
        except Exception:
            response_data["cadence"] = None
        try:
            response_data["speed"] = self.get_speed(db, activity_id)
        except Exception:
            response_data["speed"] = None
        try:
            response_data["training_effect"] = self.get_training_effect(db, activity_id)
        except Exception:
            response_data["training_effect"] = None
        try:
            response_data["altitude"] = self.get_altitude(db, activity_id)
        except Exception:
            response_data["altitude"] = None
        try:
            response_data["temp"] = self.get_temperature(db, activity_id)
        except Exception:
            response_data["temp"] = None

        # zones
        zones_data: List[ZoneData] = []
        try:
            pz = self._compute_power_zones(db, activity_id)
            if pz:
                zones_data.append(ZoneData(**pz))
        except Exception:
            pass
        try:
            hz = self._compute_heartrate_zones(db, activity_id)
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

        # best powers (local path)
        try:
            stream_raw = activity_data_manager.get_activity_stream_data(db, activity_id)
            bp = self._extract_best_powers_from_stream(stream_raw)
            response_data["best_powers"] = bp if bp else None
        except Exception:
            response_data["best_powers"] = None

        return AllActivityDataResponse(**response_data)

    # ---- helpers ----
    def _compute_power_zones(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..repositories.activity_repo import get_activity_athlete
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        power_data = stream_data.get('power', [])
        if not power_data:
            return None
        ftp = int(athlete.ftp)
        buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
        return {"distribution_buckets": buckets, "type": "power"}

    def _compute_heartrate_zones(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..repositories.activity_repo import get_activity_athlete
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        hr = stream_data.get('heart_rate', [])
        buckets = ZoneAnalyzer.analyze_heartrate_zones(hr, athlete.max_heartrate)
        return {"distribution_buckets": buckets, "type": "heartrate"}

    def _upsert_activity_tss(
        self,
        db: Session,
        activity_id_or_external: int,
        avg_power: Optional[int],
        moving_time: Optional[int],
        start_date: Optional[datetime] = None,
    ) -> Optional[int]:
        """根据活动主键或 external_id 更新当前活动的 TSS，返回 athlete_id。

        当本地库中找不到活动主键时，回退通过 external_id 匹配。
        """
        try:
            from ..db.models import TbActivity, TbAthlete
            from ..core.analytics.training import calculate_training_load

            # 1) 按主键匹配
            activity = db.query(TbActivity).filter(TbActivity.id == activity_id_or_external).first()
            # 2) 回退 external_id
            if not activity:
                activity = db.query(TbActivity).filter(TbActivity.external_id == str(activity_id_or_external)).first()
            if not activity:
                return None

            athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
            if not athlete:
                return None

            # 若本地活动缺少开始时间，则补齐，便于 7/42 天窗口统计
            if start_date and getattr(activity, 'start_date', None) is None:
                try:
                    activity.start_date = start_date
                    db.commit()
                except Exception:
                    db.rollback()

            ftp = int(getattr(athlete, 'ftp', 0) or 0)
            ap = int(avg_power or 0)
            mt = int(moving_time or 0)
            tss_val = int(calculate_training_load(ap, ftp, mt)) if (ap and ftp and mt) else 0
            if tss_val > 0:
                activity.tss = tss_val
                activity.tss_updated = 1
                db.commit()
            return int(athlete.id)
        except Exception:
            db.rollback()
            return None

    def _update_athlete_status(self, db: Session, athlete_id: int, ref_date: Optional[datetime] = None) -> Optional[int]:
        """计算并更新 Athlete 的 ctl/atl/tsb，返回 tsb（atl - ctl）。

        窗口基准时间：默认使用当前时间；若提供 ref_date，则以该时间为基准计算“过去7/42天”。
        适用于以“活动发生日期”为窗口参考的场景。
        """
        try:
            from sqlalchemy import func
            from datetime import datetime, timedelta
            from ..db.models import TbActivity, TbAthlete

            now = ref_date or datetime.now()
            seven_days_ago = now - timedelta(days=7)
            forty_two_days_ago = now - timedelta(days=42)

            sum_tss_7 = db.query(func.sum(TbActivity.tss)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= seven_days_ago,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            sum_tss_42 = db.query(func.sum(TbActivity.tss)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= forty_two_days_ago,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            # 计数信息（便于确认窗口内是否有数据被统计）
            cnt_7 = db.query(func.count(TbActivity.id)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= seven_days_ago,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            cnt_42 = db.query(func.count(TbActivity.id)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= forty_two_days_ago,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            logger.debug(
                "[status-calc-debug] sum_tss_7=%s, sum_tss_42=%s, cnt_7=%s, cnt_42=%s",
                sum_tss_7, sum_tss_42, cnt_7, cnt_42
            )
            # 转为 float 再做除法，避免 Decimal 与 float 混算报错
            sum7 = float(sum_tss_7 or 0)
            sum42 = float(sum_tss_42 or 0)
            atl = int(round(sum7 / 7.0, 0))
            ctl = int(round(sum42 / 42.0, 0))
            tsb = atl - ctl
            
            # Debug 输出，帮助定位为何为 0
            try:
                logger.info(
                    "[status-calc-debug] athlete_id=%s, 7d_since=%s, 42d_since=%s, sum7=%s, sum42=%s, cnt7=%s, cnt42=%s, atl=%s, ctl=%s, tsb=%s",
                    athlete_id,
                    seven_days_ago.isoformat(sep=' ', timespec='seconds'),
                    forty_two_days_ago.isoformat(sep=' ', timespec='seconds'),
                    int(sum7),
                    int(sum42),
                    int(cnt_7 or 0),
                    int(cnt_42 or 0),
                    atl,
                    ctl,
                    tsb,
                )
            except Exception:
                pass

            athlete = db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first()
            if athlete:
                athlete.atl = atl
                athlete.ctl = ctl
                athlete.tsb = tsb
                db.commit()
                logger.info(
                    "[status-write] athlete_id=%s, atl=%s, ctl=%s, tsb=%s (已写库)",
                    athlete_id, atl, ctl, tsb
                )
            else:
                logger.warning("[status-calc] 未找到运动员记录 athlete_id=%s，跳过写库", athlete_id)
            return tsb
        except Exception:
            db.rollback()
            logger.exception("[status-calc] 计算/写入 atl/ctl/tsb 失败 athlete_id=%s", athlete_id)
            return None

    def _extract_best_powers_from_stream(self, stream_data: Dict[str, Any]) -> Optional[Dict[str, int]]:
        try:
            if not stream_data:
                return None
            best_curve = stream_data.get('best_power', [])
            if not best_curve:
                # fallback: compute from power if available
                power = stream_data.get('power', [])
                if not power:
                    return None
                best_curve = self._compute_best_power_curve(power)
            intervals = {
                '5s': 5,
                '15s': 15,
                '30s': 30,
                '1min': 60,
                '5min': 300,
                '8min': 480,
                '10min': 600,
                '15min': 900,
                '20min': 1200,
                '30min': 1800,
                '45min': 2700,
                '1h': 3600,
            }
            out: Dict[str, int] = {}
            n = len(best_curve)
            for name, sec in intervals.items():
                if n >= sec:
                    out[name] = int(best_curve[sec - 1])
            return out or None
        except Exception:
            return None

    def _compute_best_power_curve(self, powers: List[int]) -> List[int]:
        try:
            n = len(powers)
            if n == 0:
                return []
            best = [0] * n
            for w in range(1, n + 1):
                s = sum(powers[:w])
                m = s
                for i in range(1, n - w + 1):
                    s = s - powers[i - 1] + powers[i + w - 1]
                    if s > m:
                        m = s
                best[w - 1] = int(round(m / w))
            return best
        except Exception:
            return []

    # Individual metric endpoints (local DB path)
    def get_overall(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.overall import compute_overall_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        # 先装配 overall，写回当前活动 TSS，再刷新并注入 TSB
        result = compute_overall_info(stream_data, session_data, athlete)
        try:
            tl = result.get('training_load') if isinstance(result, dict) else getattr(result, 'training_load', None)
        except Exception:
            tl = None
        if tl is not None:
            try:
                # 本地路径按主键更新 TSS
                from ..db.models import TbActivity
                self._upsert_activity_tss(db, activity_id, None, None)  # 确保活动存在
                act = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
                if act and tl > 0:
                    act.tss = int(tl)
                    act.tss_updated = 1
                    db.commit()
            except Exception:
                db.rollback()
        tsb_val = self._update_athlete_status(db, athlete.id, activity.start_date)
        if isinstance(result, dict):
            result['status'] = tsb_val
        else:
            try:
                result['status'] = tsb_val
            except Exception:
                pass
        return result

    def get_power(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.power import compute_power_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_power_info(stream_data, int(athlete.ftp), session_data)

    def get_heartrate(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.heartrate import compute_heartrate_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_heartrate_info(stream_data, bool(stream_data.get('power')), session_data)

    def get_speed(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.speed import compute_speed_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, _athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_speed_info(stream_data, session_data)

    def get_cadence(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.cadence import compute_cadence_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, _athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_cadence_info(stream_data, session_data)

    def get_altitude(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.altitude import compute_altitude_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, _athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_altitude_info(stream_data, session_data)

    def get_temperature(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..metrics.activities.temperature import compute_temperature_info
        from ..infrastructure.data_manager import activity_data_manager
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        return compute_temperature_info(stream_data)

    def get_training_effect(self, db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        from ..core.analytics.training import (
            aerobic_effect, anaerobic_effect, power_zone_percentages,
            power_zone_times, calculate_training_load, estimate_calories_with_power, estimate_calories_with_heartrate
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
        # 计算碳水消耗（约），优先用功率估算，如无功率则尝试心率
        calories = None
        try:
            if avg_power and len(power) > 0:
                calories = estimate_calories_with_power(avg_power, len(power), getattr(athlete, 'weight', 70) or 70)
            else:
                hr = stream_data.get('heart_rate', [])
                if hr and any(hr):
                    avg_hr = int(sum(hr)/len(hr))
                    calories = estimate_calories_with_heartrate(avg_hr, len(power), getattr(athlete, 'weight', 70) or 70)
        except Exception:
            calories = None
        carbohydrate = int(calories / 4.138) if calories else None
        return {
            'primary_training_benefit': pb,
            'aerobic_effect': ae,
            'anaerobic_effect': ne,
            'training_load': tss,
            'carbohydrate_consumption': carbohydrate,
        }


activity_service = ActivityService()
