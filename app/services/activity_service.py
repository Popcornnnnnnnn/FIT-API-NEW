"""Activity Service（活动服务编排层）

职责：
- 统一编排数据来源（Strava 或 本地数据流）与分析逻辑（metrics/core）；
- 组合多种单项结果，返回 AllActivityDataResponse（对外响应模型）；
- 暴露 get_overall/get_power/... 单项装配方法，便于路由端直接复用。
"""

from typing import Optional, List, Dict, Any, Tuple, Sequence
from datetime import datetime
from sqlalchemy.orm import Session
import logging
from pathlib import Path
from bisect import bisect_left
from app.db.models import TbActivity, TbAthlete

from ..clients.strava_client import StravaClient
from ..schemas.activities import (
    AllActivityDataResponse,
    ZoneData,
    IntervalsResponse,
    SimplifiedIntervalItem,
    IntervalItem,
    ZoneSegmentVisual,
    BestPowerCurveRecord,
)
from ..streams.crud import stream_crud
from ..streams.models import Resolution
from ..infrastructure.data_manager import activity_data_manager
from ..analyzers.strava_analyzer import StravaAnalyzer
from ..core.analytics import zones as ZoneAnalyzer
from ..core.analytics.zone_histogram import (
    render_zone_segments_chart,
    generate_zone_segments_payload,
    build_zone_segment_visuals,
)
from ..core.analytics.interval_detection import (
    detect_intervals,
    render_interval_preview,
    summarize_window,
    IntervalSummary,
)
import numpy as np


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
            client = StravaClient(access_token)
            keys_list_all = [
                'time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
                'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth'
            ]
            try:
                # 优先用主键查活动；查不到再回退到 external_id
                local_obj = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
                if not local_obj:
                    local_obj = db.query(TbActivity).filter(TbActivity.external_id == activity_id).first()

                activity_entry, athlete_entry = self._get_local_activity_pair(db, getattr(local_obj, 'id', None) or activity_id)

                full = client.fetch_full(activity_entry.external_id, keys=keys_list_all, resolution=None)

                activity_data = full['activity']
                stream_data = full['streams']
                athlete_data = full['athlete']

                # 如果本地数据库没有ftp信息，优先使用strava上的ftp信息
                if athlete_entry.ftp is None:
                    athlete_entry.ftp = athlete_data.get('ftp')


                if keys:
                    keys_list = [k.strip() for k in keys.split(',') if k.strip()]
                else:
                    keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']

                result = StravaAnalyzer.analyze_activity_data(
                    activity_data,
                    stream_data,
                    athlete_data,
                    activity_entry.external_id,
                    db,
                    keys_list,
                    resolution,
                    athlete_entry,
                    activity_entry,
                )

                # 生成 intervals 数据并保存到文件（包含预览图生成）
                try:
                    intervals_data = self._generate_and_save_intervals_strava(
                        db,
                        activity_id,
                        activity_entry,
                        stream_data,
                        activity_data,
                        athlete_entry,
                        athlete_data,
                    )
                except Exception:
                    logger.exception("[intervals][save-error-strava] activity_id=%s", activity_id)
                
                if getattr(result, 'heartrate', None) is not None:
                    self._update_activity_efficiency_factor(db, activity_entry, result.heartrate.efficiency_index)

                # 计算 training_load，更新该活动的 TSS，并据此刷新 athlete 的 TSB（status）
                try:
                    moving_time = int(activity_data.get('moving_time') or 0)
                    avg_power = activity_data.get('average_watts') or 0

                    # 在返回中添加tss和tsb，并将相关指标（tss、tsb、ctl、atl、tss_updated）写库
                    raw = activity_data.get('start_date')
                    iso = raw.replace('Z', '+00:00')
                    start_dt = datetime.fromisoformat(iso).replace(tzinfo=None)
                    tss = self._upsert_activity_tss(db, activity_entry, athlete_entry, avg_power, moving_time, start_dt)
                    tsb = self._update_athlete_status(db, athlete_entry, start_dt)
                    result.overall.status = tsb
                    result.overall.training_load = tss

                    # 附加 best_power_record（独立于分辨率）
                    try:
                        from ..repositories.best_power_file_repo import load_best_curve
                        best_power_record = None

                        curve = load_best_curve(athlete_entry.id)
                        if curve:
                            best_power_record = {
                                'athlete_id': athlete_entry.id,
                                'length': len(curve),
                                'best_curve': curve,
                            }
                        result.best_power_record = BestPowerCurveRecord.model_validate(best_power_record)
                    except Exception:
                        result.best_power_record = None
                except Exception:
                    logger.exception(
                        "[training-load][error] activity_id=%s activity_entry=%s athlete_entry=%s",
                        activity_id,
                        getattr(activity_entry, 'id', None),
                        getattr(athlete_entry, 'id', None),
                    )
                return result
            except Exception:
                raise

        # Local DB path: compose using service methods and metrics
        local_pair = self._get_local_activity_pair(db, activity_id)
        local_activity = local_pair[0] if local_pair else None
        # 本地fit文件处理，没有输入ftp的时候，进行ftp估算
        if local_pair[1].ftp is None or local_pair[1].ftp <= 0:
            from app.core.analytics.ftp_estimator import estimate_ftp_from_best_curve, _load_best_curve
            if _load_best_curve(int(local_pair[1].id)) is None: # 防止是第一次活动，没有历史的功率数据
                return
            local_pair[1].ftp = round(estimate_ftp_from_best_curve(local_pair[1].id).ftp)

        raw_stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        session_cache = None
        if local_activity and getattr(local_activity, 'upload_fit_url', None):
            session_cache = activity_data_manager.get_session_data(db, activity_id, local_activity.upload_fit_url)

        response_data = {}
        try:
            response_data["overall"] = self.get_overall(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][overall] activity_id=%s err=%s", activity_id, e)
            response_data["overall"] = None

        try:
            response_data["power"] = self.get_power(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][power] activity_id=%s err=%s", activity_id, e)
            response_data["power"] = None

        try:
            response_data["heartrate"] = self.get_heartrate(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][heartrate] activity_id=%s err=%s", activity_id, e)
            response_data["heartrate"] = None

        try:
            response_data["cadence"] = self.get_cadence(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][cadence] activity_id=%s err=%s", activity_id, e)
            response_data["cadence"] = None

        try:
            response_data["speed"] = self.get_speed(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][speed] activity_id=%s err=%s", activity_id, e)
            response_data["speed"] = None

        try:
            response_data["training_effect"] = self.get_training_effect(db, activity_id, local_pair, raw_stream_data, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][training_effect] activity_id=%s err=%s", activity_id, e)
            response_data["training_effect"] = None

        try:
            response_data["altitude"] = self.get_altitude(db, activity_id, local_pair, raw_stream_data, session_cache, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][altitude] activity_id=%s err=%s", activity_id, e)
            response_data["altitude"] = None

        try:
            response_data["temp"] = self.get_temperature(db, activity_id, raw_stream_data, use_cache=False)
        except Exception as e:
            logger.exception("[section-error][temp] activity_id=%s err=%s", activity_id, e)
            response_data["temp"] = None

        # zones
        zones_data: List[ZoneData] = []
        try:
            pz = self._compute_power_zones(db, activity_id)
            if pz:
                zones_data.append(ZoneData(**pz))
        except Exception as e:
            logger.exception("[section-error][zones-power] activity_id=%s err=%s", activity_id, e)
            pass
        try:
            hz = self._compute_heartrate_zones(db, activity_id)
            if hz:
                zones_data.append(ZoneData(**hz))
        except Exception as e:
            logger.exception("[section-error][zones-hr] activity_id=%s err=%s", activity_id, e)
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
            logger.exception("[section-error][streams] activity_id=%s err=%s", activity_id, e)
            response_data["streams"] = None

        # best powers + segment_records（本地路径，封装到独立方法）
        try:
            stream_raw = raw_stream_data
            bp = self._extract_best_powers_from_stream(stream_raw)
            response_data["best_powers"] = bp if bp else None
            response_data["segment_records"] = self._update_segment_records_from_local(db, activity_id, stream_raw, bp)
        except Exception as e:
            logger.exception("[section-error][segments] activity_id=%s err=%s", activity_id, e)
            response_data["best_powers"] = None
            response_data["segment_records"] = None

        # best_power_record（独立于分辨率，从文件仓库读取）
        try:
            from ..repositories.activity_repo import get_activity_athlete
            from ..repositories.best_power_file_repo import load_best_curve
            pair = get_activity_athlete(db, activity_id)
            if pair:
                _activity, athlete = pair
                curve = load_best_curve(int(athlete.id))
                if curve:
                    response_data["best_power_record"] = {
                        'athlete_id': int(athlete.id),
                        'length': len(curve),
                        'best_curve': curve,
                    }
                else:
                    response_data["best_power_record"] = None
            else:
                response_data["best_power_record"] = None
        except Exception as e:
            logger.exception("[section-error][best_power_record] activity_id=%s err=%s", activity_id, e)
            response_data["best_power_record"] = None

        # 生成并保存 intervals 数据（包含预览图生成）
        try:
            intervals_data = self._generate_and_save_intervals_local(
                db,
                activity_id,
                local_pair,
                raw_stream_data,
            )
        except Exception:
            logger.exception("[intervals][save-error-local] activity_id=%s", activity_id)

        return AllActivityDataResponse(**response_data)

    # ---- helpers ----
    def _get_local_activity_pair(
        self,
        db: Session,
        activity_id: int,
    ) -> Tuple[Optional[Any], Optional[Any]]:
        from ..repositories.activity_repo import get_activity_athlete, get_activity_by_id
        pair = get_activity_athlete(db, activity_id)
        if pair:
            return pair
        activity = get_activity_by_id(db, activity_id)
        return activity, None

    @staticmethod
    def _resolve_strava_id(activity_id: int, local_activity: Optional[Any]) -> int:
        if local_activity and getattr(local_activity, 'external_id', None):
            try:
                resolved = int(str(local_activity.external_id))
                if resolved != activity_id:
                    logger.debug("[strava-id-map] local activity %s -> external_id %s", activity_id, resolved)
                return resolved
            except (TypeError, ValueError):
                logger.debug("[strava-id-map] invalid external_id for activity %s", activity_id)
        return activity_id

    def _update_activity_efficiency_factor(self, db: Session, activity, value: Optional[float]) -> None:
        if not hasattr(activity, 'efficiency_factor'):
            return
        current = getattr(activity, 'efficiency_factor', None)
        if current == value:
            return
        try:
            setattr(activity, 'efficiency_factor', value)
            db.commit()
        except Exception as e:
            logger.exception("[db-error][efficiency-factor] activity_id=%s err=%s", getattr(activity, 'id', None), e)
            db.rollback()

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
        # 根据配置选择心率分区基准：阈值心率优先（is_threshold_active=1 且阈值存在），否则用最大心率
        try:
            use_threshold = int(getattr(athlete, 'is_threshold_active', 0) or 0) == 1
        except Exception:
            use_threshold = False
        lthr = None
        if use_threshold and getattr(athlete, 'threshold_heartrate', None):
            try:
                lthr = int(athlete.threshold_heartrate)
            except Exception:
                lthr = None
        max_hr = None
        if getattr(athlete, 'max_heartrate', None):
            try:
                max_hr = int(athlete.max_heartrate)
            except Exception:
                max_hr = None
        if use_threshold and lthr:
            buckets = ZoneAnalyzer.analyze_heartrate_zones_lthr(hr, lthr, max_hr)
        else:
            buckets = ZoneAnalyzer.analyze_heartrate_zones(hr, max_hr or 0)
        return {"distribution_buckets": buckets, "type": "heartrate"}

    def _update_segment_records_from_local(
        self,
        db: Session,
        activity_id: int,
        stream_raw: Dict[str, Any],
        best_powers: Optional[Dict[str, int]],
    ) -> Optional[List[Dict[str, Any]]]:
        """基于本地 FIT 流与历史纪录（tb_athlete_power_records）刷新分段纪录。

        - 读取运动员在 tb_athlete_power_records 的历史 Top3；
        - 对比 best_powers、最长距离、最大爬升并写库更新；
        - 返回本次进入 Top3 的刷新列表（供 segment_records 返回）。
        """
        try:
            if not best_powers:
                return None
            from ..repositories.activity_repo import get_activity_athlete
            from ..repositories.power_records_repo import (
                update_best_powers as repo_update_best_powers,
                update_longest_ride as repo_update_longest_ride,
                update_max_elevation_gain as repo_update_max_elevation_gain,
                get_or_create_records as repo_get_or_create_records,
            )
            from ..repositories.best_power_file_repo import update_with_activity_curve as repo_update_best_power_file
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
            activity, athlete = pair

            # 归一化时间窗键到 repo 支持的格式
            key_map = {
                '5s': '5s', '15s': '15s', '30s': '30s',
                '1min': '1m', '2min': '2m', '3min': '3m', '5min': '5m',
                '10min': '10m', '15min': '15m', '20min': '20m', '30min': '30m',
                '45min': '45m', '1h': '60m'
            }
            normalized = { key_map[k]: v for k, v in best_powers.items() if k in key_map }

            # 调试：记录更新前 Top3 快照（功率/距离/爬升）
            try:
                rec_snapshot = repo_get_or_create_records(db, athlete.id)
                # 仅对将要处理的时间窗打印
                for suf in sorted(normalized.keys()):
                    f1 = f"power_{suf}_1st"; f2 = f"power_{suf}_2nd"; f3 = f"power_{suf}_3rd"
                    logger.info(
                        "[segment-debug][before] athlete=%s interval=%s top3=(%s,%s,%s)",
                        athlete.id, suf, getattr(rec_snapshot, f1), getattr(rec_snapshot, f2), getattr(rec_snapshot, f3)
                    )
                logger.info(
                    "[segment-debug][before] athlete=%s longest_ride=(%s,%s,%s) max_elev=(%s,%s,%s)",
                    athlete.id,
                    getattr(rec_snapshot, 'longest_ride_1st'), getattr(rec_snapshot, 'longest_ride_2nd'), getattr(rec_snapshot, 'longest_ride_3rd'),
                    getattr(rec_snapshot, 'max_elevation_1st'), getattr(rec_snapshot, 'max_elevation_2nd'), getattr(rec_snapshot, 'max_elevation_3rd'),
                )
            except Exception:
                pass

            seg_records: List[Dict[str, Any]] = []
            try:
                sr_list = repo_update_best_powers(db, athlete.id, normalized, activity.id)
                if sr_list:
                    seg_records.extend(sr_list)
            except Exception:
                pass

            # 文件持久化：更新该运动员全局最佳曲线
            try:
                # 优先使用 best_power 流，其次按 power 计算
                activity_curve = None
                try:
                    best_curve_stream = stream_raw.get('best_power') or []
                    if best_curve_stream:
                        # stream 的 best_power 可能按 1..N 下标对齐
                        activity_curve = [int(x or 0) for x in best_curve_stream]
                except Exception:
                    activity_curve = None
                if activity_curve is None:
                    power = stream_raw.get('power') or []
                    if power:
                        activity_curve = self._compute_best_power_curve([int(p or 0) for p in power])
                if activity_curve:
                    repo_update_best_power_file(athlete.id, activity_curve)
            except Exception:
                pass

            # 距离与累计爬升
            distance_m = 0
            try:
                dist_stream = stream_raw.get('distance') or []
                if dist_stream:
                    distance_m = int(dist_stream[-1] or 0)
            except Exception:
                distance_m = 0

            elevation_gain = 0
            try:
                alt = stream_raw.get('altitude') or []
                if alt and len(alt) > 1:
                    prev = alt[0]
                    gain = 0
                    for h in alt[1:]:
                        if h is not None and prev is not None:
                            d = h - prev
                            if d > 0:
                                gain += d
                            prev = h
                    elevation_gain = int(gain)
            except Exception:
                elevation_gain = 0

            try:
                if distance_m > 0:
                    sr = repo_update_longest_ride(db, athlete.id, distance_m, activity.id)
                    if sr:
                        seg_records.append(sr)
            except Exception:
                pass
            try:
                if elevation_gain > 0:
                    sr = repo_update_max_elevation_gain(db, athlete.id, elevation_gain, activity.id)
                    if sr:
                        seg_records.append(sr)
            except Exception:
                pass

            # 调试：打印本次刷新明细与更新后 Top3 快照
            try:
                if seg_records:
                    logger.debug("[segment-debug][applied] updates=%s", seg_records)
                rec_after = repo_get_or_create_records(db, athlete.id)
                for suf in sorted(normalized.keys()):
                    f1 = f"power_{suf}_1st"; f2 = f"power_{suf}_2nd"; f3 = f"power_{suf}_3rd"
                    logger.debug(
                        "[segment-debug][after ] athlete=%s interval=%s top3=(%s,%s,%s)",
                        athlete.id, suf, getattr(rec_after, f1), getattr(rec_after, f2), getattr(rec_after, f3)
                    )
                logger.debug(
                    "[segment-debug][after ] athlete=%s longest_ride=(%s,%s,%s) max_elev=(%s,%s,%s)",
                    athlete.id,
                    getattr(rec_after, 'longest_ride_1st'), getattr(rec_after, 'longest_ride_2nd'), getattr(rec_after, 'longest_ride_3rd'),
                    getattr(rec_after, 'max_elevation_1st'), getattr(rec_after, 'max_elevation_2nd'), getattr(rec_after, 'max_elevation_3rd'),
                )
            except Exception:
                pass

            return seg_records or None
        except Exception:
            return None

    def _upsert_activity_tss(
        self,
        db: Session,
        activity_entry: Optional[Any],
        athlete_entry: Optional[Any],
        avg_power: Optional[int],
        moving_time: Optional[int],
        start_date: Optional[datetime] = None,
    ) -> Optional[int]:
        if not activity_entry or not athlete_entry:
            return None
        try:
            from ..core.analytics.training import calculate_training_load
            tss_val = calculate_training_load(avg_power, athlete_entry.ftp, moving_time)
            if tss_val > 0:
                activity_entry.tss = tss_val
                activity_entry.tss_updated = 1
                db.commit()
            return tss_val
        except Exception:
            db.rollback()
            return None

    def _update_athlete_status(
            self, 
            db: Session, 
            athlete_entry: Optional[Any] = None,
            ref_date: Optional[datetime] = None,
        ) -> Optional[int]:
        """计算并更新 Athlete 的 ctl/atl/tsb，返回 tsb（atl - ctl）。

        窗口基准时间：默认使用当前时间；若提供 ref_date，则以该时间为基准计算"过去7/42天"。
        适用于以"活动发生日期"为窗口参考的场景。
        """
        from sqlalchemy import func
        from datetime import datetime, timedelta

        if athlete_entry is None:
            return None
        now = ref_date or datetime.now()
        seven_days_ago = now - timedelta(days=7)
        forty_two_days_ago = now - timedelta(days=42)
        athlete_id = athlete_entry.id

        try:

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
            # 转为 float 再做除法，避免 Decimal 与 float 混算报错
            sum7 = float(sum_tss_7 or 0)
            sum42 = float(sum_tss_42 or 0)
            atl = int(round(sum7 / 7.0, 0))
            ctl = int(round(sum42 / 42.0, 0))
            tsb = ctl - atl

            athlete_entry.atl = atl
            athlete_entry.ctl = ctl
            athlete_entry.tsb = tsb
            db.commit()
            return tsb
        except Exception:
            db.rollback()
            logger.exception("[status-calc] 计算/写入 atl/ctl/tsb 失败 athlete_id=%s", getattr(athlete_entry, 'id', None))
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
    def get_overall(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "overall")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.overall import compute_overall_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        # 先装配 overall，写回当前活动 TSS，再刷新并注入 TSB
        result = compute_overall_info(stream_data, session_data, athlete)
        try:
            tl = result.get('training_load') if isinstance(result, dict) else getattr(result, 'training_load', None)
        except Exception:
            tl = None
        if tl is not None:
            try:
                act = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
                if act and tl > 0:
                    act.tss = int(tl)
                    act.tss_updated = 1
                    db.commit()
            except Exception:
                db.rollback()
        tsb_val = self._update_athlete_status(db, athlete, activity.start_date)
        if isinstance(result, dict):
            result['status'] = tsb_val
        else:
            try:
                result['status'] = tsb_val
            except Exception:
                pass
        return result

    def get_power(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "power")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.power import compute_power_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_power_info(stream_data, int(athlete.ftp), session_data)

    def get_heartrate(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "heartrate")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.heartrate import compute_heartrate_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        result = compute_heartrate_info(stream_data, bool(stream_data.get('power')), session_data)
        efficiency_value = None
        if isinstance(result, dict):
            efficiency_value = result.get('efficiency_index')
        self._update_activity_efficiency_factor(db, activity, efficiency_value)
        return result

    def get_speed(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "speed")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.speed import compute_speed_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, _athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_speed_info(stream_data, session_data)

    def get_cadence(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "cadence")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.cadence import compute_cadence_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, _athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_cadence_info(stream_data, session_data)

    def get_altitude(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "altitude")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.altitude import compute_altitude_info
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, _athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if session_data is None and getattr(activity, 'upload_fit_url', None):
            session_data = activity_data_manager.get_session_data(db, activity_id, activity.upload_fit_url)
        return compute_altitude_info(stream_data, session_data)

    def get_temperature(
        self,
        db: Session,
        activity_id: int,
        stream_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "temp")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..metrics.activities.temperature import compute_temperature_info
        from ..infrastructure.data_manager import activity_data_manager
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        return compute_temperature_info(stream_data)

    def get_training_effect(
        self,
        db: Session,
        activity_id: int,
        pair: Optional[Tuple[Any, Any]] = None,
        stream_data: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        from ..infrastructure.cache_manager import activity_cache_manager
        
        if use_cache:
            cached = activity_cache_manager.get_cached_metric(db, activity_id, "training_effect")
            if cached is not None:
                return cached
            if not activity_cache_manager.has_cache(db, activity_id):
                return None
        
        from ..repositories.activity_repo import get_activity_athlete
        from ..infrastructure.data_manager import activity_data_manager
        from ..core.analytics.training import (
            aerobic_effect, anaerobic_effect, power_zone_percentages,
            power_zone_times, calculate_training_load, estimate_calories_with_power, estimate_calories_with_heartrate
        )
        if pair is None:
            pair = get_activity_athlete(db, activity_id)
            if not pair:
                return None
        activity, athlete = pair
        if stream_data is None:
            stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        power = stream_data.get('power', [])
        if not power:
            return None
        ftp = int(athlete.ftp)
        if ftp is None or ftp <= 0:
            logger.warning("[training-effect] missing ftp for athlete_id=%s activity_id=%s", getattr(athlete, 'id', None), activity_id)
            return None
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

    @staticmethod
    def _locate_index(timeline: List[int], target: int, default: int = 0) -> int:
        if not timeline:
            return int(default)
        target_val = int(target)
        idx = bisect_left(timeline, target_val)
        if idx >= len(timeline):
            return len(timeline)
        return idx

    @staticmethod
    def _interval_summary_to_item(
        summary: IntervalSummary,
        timeline: List[int],
        start_override: Optional[int] = None,
        end_override: Optional[int] = None,
    ) -> IntervalItem:
        if timeline:
            start_idx = max(0, min(int(summary.start), len(timeline) - 1))
            end_idx = max(start_idx + 1, min(int(summary.end), len(timeline)))
            start_time = int(start_override) if start_override is not None else int(timeline[start_idx])
            if end_override is not None:
                end_time = int(end_override)
            else:
                ref_idx = min(end_idx - 1, len(timeline) - 1)
                end_time = int(timeline[ref_idx] + 1)
        else:
            start_time = int(start_override) if start_override is not None else int(summary.start)
            end_time = int(end_override) if end_override is not None else int(summary.end)

        duration = max(end_time - start_time, int(summary.duration))
        metadata = summary.metadata or {}
        cleaned_metadata: Dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (int, float, bool, str, list, dict)) or value is None:
                cleaned_metadata[key] = value
            else:
                try:
                    cleaned_metadata[key] = float(value)
                except Exception:
                    cleaned_metadata[key] = value

        return IntervalItem(
            start=start_time,
            end=end_time,
            duration=duration,
            classification=summary.classification,
            average_power=float(summary.average_power),
            peak_power=float(summary.peak_power),
            normalized_power=float(summary.normalized_power),
            intensity_factor=float(summary.intensity_factor),
            power_ratio=float(summary.power_ratio),
            time_above_95=float(summary.time_above_95),
            time_above_106=float(summary.time_above_106),
            time_above_120=float(summary.time_above_120),
            time_above_150=float(summary.time_above_150),
            heart_rate_avg=float(summary.heart_rate_avg) if summary.heart_rate_avg is not None else None,
            heart_rate_max=int(summary.heart_rate_max) if summary.heart_rate_max is not None else None,
            heart_rate_slope=float(summary.heart_rate_slope) if summary.heart_rate_slope is not None else None,
            metadata=cleaned_metadata,
        )

    def _build_interval_response_simplified(
        self,
        power_series: Sequence[int],
        timestamps: Sequence[int],
        heart_rate_series: Optional[Sequence[int]],
        ftp_value: float,
        lthr_value: Optional[float],
        hr_max_value: Optional[float],
        preview_file: Optional[Path],
    ) -> IntervalsResponse:
        """构建简化的 intervals 响应（功率检测）"""
        sample_count = len(power_series) if power_series else len(heart_rate_series or [])
        synthetic_activity_payload = {"moving_time": timestamps[-1] if timestamps else 0}
        sample_interval = self._estimate_sample_interval(timestamps, synthetic_activity_payload, sample_count)

        detection = detect_intervals(
            timestamps,
            power_series,
            ftp_value,
            heart_rate=heart_rate_series,
            lthr=lthr_value,
            hr_max=hr_max_value,
        )

        timeline = list(timestamps) if isinstance(timestamps, (list, tuple)) else list(timestamps)
        simplified_intervals: List[SimplifiedIntervalItem] = []
        
        for summary in detection.intervals:
            start_idx = self._locate_index(timeline, summary.start)
            end_idx = self._locate_index(timeline, summary.end, default=len(power_series))
            avg_power = float(np.mean(power_series[start_idx:end_idx])) if power_series and start_idx < len(power_series) else 0.0
            power_ratio = avg_power / ftp_value if ftp_value > 0 else 0.0
            
            simplified_intervals.append(SimplifiedIntervalItem(
                start=int(summary.start),
                end=int(summary.end),
                duration=int(summary.end - summary.start),
                classification=summary.classification,
                avg_power=round(avg_power, 2),
                power_ratio=round(power_ratio, 2),
            ))

        if detection.repeats:
            for block in detection.repeats:
                start_idx = self._locate_index(timeline, block.start)
                end_idx = self._locate_index(timeline, block.end, default=len(power_series))
                avg_power = float(np.mean(power_series[start_idx:end_idx])) if power_series and start_idx < len(power_series) else 0.0
                power_ratio = avg_power / ftp_value if ftp_value > 0 else 0.0
                
                simplified_intervals.append(SimplifiedIntervalItem(
                    start=int(block.start),
                    end=int(block.end),
                    duration=int(block.end - block.start),
                    classification=block.classification,
                    avg_power=round(avg_power, 2),
                    power_ratio=round(power_ratio, 2),
                ))

        simplified_intervals.sort(key=lambda item: item.start)

        preview_path = None
        if preview_file is not None and simplified_intervals:
            preview_file.parent.mkdir(parents=True, exist_ok=True)
            render_interval_preview(detection, timeline, power_series, str(preview_file))
            if preview_file.exists():
                preview_path = str(preview_file)

        return IntervalsResponse(
            duration=int(detection.duration),
            ftp=round(float(detection.ftp)),
            intervals=simplified_intervals,
            preview_image=preview_path,
        )

    @staticmethod
    def _build_preview_path(preview_dir: Optional[str], default_name: str) -> Optional[Path]:
        if preview_dir is None:
            preview_dir = 'artifacts/Pics'
        try:
            return Path(preview_dir) / default_name
        except Exception:
            return None

    @staticmethod
    def _extract_series_from_streams(stream_data: Dict[str, Any]) -> Tuple[List[int], List[int], Optional[List[int]]]:
        def _stream_values(key: str) -> List[int]:
            raw = stream_data.get(key)
            if isinstance(raw, dict):
                data = raw.get('data', [])
            else:
                data = raw or []
            return [int(x or 0) for x in data]

        power = _stream_values('watts')
        timestamps = _stream_values('time')
        if not timestamps:
            timestamps = _stream_values('elapsed_time')
        if not timestamps and power:
            timestamps = list(range(len(power)))
        heart_rate_vals = _stream_values('heartrate') if 'heartrate' in stream_data else []
        heart_rate = heart_rate_vals if heart_rate_vals else None
        return power, timestamps, heart_rate

    @staticmethod
    def _estimate_sample_interval(
        timestamps: Sequence[int],
        activity_payload: Optional[Dict[str, Any]],
        sample_count: int,
    ) -> float:
        if timestamps and len(timestamps) > 1:
            start = timestamps[0]
            end = timestamps[-1]
            duration = end - start
            steps = len(timestamps) - 1
            if duration > 0 and steps > 0:
                interval = duration / steps
                if interval > 0:
                    return max(0.5, float(interval))

        if activity_payload:
            moving_time = activity_payload.get("moving_time") or 0
            if moving_time and sample_count:
                interval = moving_time / sample_count
                if interval > 0:
                    return max(0.5, float(interval))
        return 1.0

    def _compute_zone_segments(
        self,
        power_series: Sequence[int],
        heart_rate_series: Optional[Sequence[int]],
        ftp_value: Optional[float],
        lthr_value: Optional[float],
        hr_max_value: Optional[float],
        sample_interval: float,
        min_segment_seconds: Optional[float] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        min_segment = min_segment_seconds or max(5.0, sample_interval * 5)
        try:
            if power_series and ftp_value and ftp_value > 0:
                payload = generate_zone_segments_payload(
                    power_series,
                    "power",
                    ftp=int(round(ftp_value)),
                    sample_interval=sample_interval,
                    min_segment_seconds=min_segment,
                )
                return build_zone_segment_visuals(payload, "power")
            if heart_rate_series and lthr_value and lthr_value > 0:
                max_hr_arg = int(round(hr_max_value)) if hr_max_value else None
                if max_hr_arg is not None and max_hr_arg <= int(round(lthr_value)):
                    max_hr_arg = None
                payload = generate_zone_segments_payload(
                    heart_rate_series,
                    "heart_rate",
                    lthr=int(round(lthr_value)),
                    max_hr=max_hr_arg,
                    sample_interval=sample_interval,
                    min_segment_seconds=min_segment,
                )
                return build_zone_segment_visuals(payload, "heart_rate")
        except Exception:
            logger.exception("[zone-segments][compute-error]")
        return None

    def _generate_and_save_intervals_local(
        self,
        db: Session,
        activity_id: int,
        local_pair: Optional[Tuple[Any, Any]],
        stream_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """生成 intervals 数据并保存到文件（本地路径）
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            local_pair: (activity, athlete) 元组
            stream_data: 本地流数据
            
        Returns:
            生成的intervals数据字典，失败返回None
        """
        try:
            from ..infrastructure.intervals_manager import save_intervals
            
            if not local_pair:
                return None
            
            activity, athlete = local_pair
            if not athlete:
                return None
            
            # 提取流数据
            power_series = stream_data.get('power') or []
            timestamps = stream_data.get('timestamp') or []
            heart_rate_series = stream_data.get('heart_rate') or []
            
            # 如果没有时间戳，生成合成时间戳
            if not timestamps and (power_series or heart_rate_series):
                timestamps = list(range(len(power_series) or len(heart_rate_series)))
            
            # 解析阈值
            ftp_value, lthr_value, hr_max_value = self._resolve_thresholds(
                athlete,
                ftp_override=None,
                lthr_override=None,
                hr_max_override=None,
            )
            
            # 判断活动类型（本地路径没有activity_data）
            is_cycling = self._is_cycling_activity(
                activity_data=None,
                activity_entry=activity,
                stream_data=stream_data,
            )
            
            # 选择数据源
            source_type, reference_value = self._select_intervals_data_source(
                is_cycling,
                power_series,
                heart_rate_series,
                ftp_value,
                lthr_value,
                hr_max_value,
            )
            
            if not source_type:
                logger.warning("[intervals] 无法计算intervals: activity_id=%s (无可用数据源)", activity_id)
                return None
            
            # 构建preview路径
            preview_file = self._build_preview_path(
                "artifacts/Pics",
                default_name=f"interval_preview_{activity_id}.png",
            )
            
            # 根据数据源调用不同的构建方法
            if source_type == "power":
                intervals_response = self._build_interval_response_simplified(
                    power_series,
                    timestamps,
                    heart_rate_series,
                    ftp_value,
                    lthr_value,
                    hr_max_value,
                    preview_file,
                )
            else:  # heartrate_lthr 或 heartrate_max
                intervals_response = self._build_interval_response_by_heartrate_simplified(
                    timestamps,
                    heart_rate_series,
                    lthr_value if source_type == "heartrate_lthr" else None,
                    hr_max_value,
                    preview_file,
                )
            
            if not intervals_response:
                return None
            
            # 转换为字典并保存
            intervals_dict = intervals_response.model_dump() if hasattr(intervals_response, 'model_dump') else intervals_response.dict()
            save_intervals(activity_id, intervals_dict)
            return intervals_dict
        except Exception:
            logger.exception("[intervals][generate-error-local] activity_id=%s", activity_id)
            return None

    def _generate_and_save_intervals_strava(
        self,
        db: Session,
        activity_id: int,
        activity_entry: Optional[Any],
        stream_data: Dict[str, Any],
        activity_data: Dict[str, Any],
        athlete_entry: Optional[Any],
        athlete_data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            from ..infrastructure.intervals_manager import save_intervals
            
            # 提取数据
            power_series, timestamps, heart_rate_series = self._extract_series_from_streams(stream_data)
            
            # 解析阈值
            ftp_value, lthr_value, hr_max_value = self._resolve_thresholds(
                athlete_entry,
                athlete_payload=athlete_data,
                activity_payload=activity_data,
            )
            
            # 判断活动类型
            is_cycling = self._is_cycling_activity(
                activity_data=activity_data,
                activity_entry=activity_entry,
                stream_data=stream_data,
            )

            
            # 选择数据源
            source_type, reference_value = self._select_intervals_data_source(
                is_cycling,
                power_series,
                heart_rate_series,
                ftp_value,
                lthr_value,
                hr_max_value,
            )
            
            if not source_type:
                logger.warning("[intervals] 无法生成intervals: activity_id=%s (无可用数据源)", activity_id)
                return None
            
            # 构建预览图路径
            base_identifier = (
                getattr(activity_entry, "external_id", None)
                or getattr(activity_entry, "id", None)
                or activity_data.get("id")
                or str(activity_id)
            )
            safe_base = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(base_identifier))
            preview_file = Path("artifacts/Pics") / f"interval_preview_{safe_base}.png"
            
            # 根据数据源执行检测
            if source_type == "power":
                intervals_response = self._build_interval_response_simplified(
                    power_series,
                    timestamps,
                    heart_rate_series,
                    ftp_value,
                    lthr_value,
                    hr_max_value,
                    preview_file,
                )
            else:  # heartrate_lthr 或 heartrate_max
                intervals_response = self._build_interval_response_by_heartrate_simplified(
                    timestamps,
                    heart_rate_series,
                    lthr_value if source_type == "heartrate_lthr" else None,
                    hr_max_value,
                    preview_file,
                )
            
            if not intervals_response:
                return None
            
            # 转换为字典并保存（简化格式）
            intervals_dict = intervals_response.model_dump() if hasattr(intervals_response, 'model_dump') else intervals_response.dict()
            save_intervals(activity_id, intervals_dict)
            return intervals_dict
        except Exception:
            logger.exception("[intervals][generate-error-strava] activity_id=%s", activity_id)
            return None

    def _is_cycling_activity(
        self,
        activity_data: Optional[Dict[str, Any]] = None,
        activity_entry: Optional[Any] = None,
        stream_data: Optional[Dict[str, Any]] = None,
    ) -> bool:

        # Strava路径：从activity_data判断
        if activity_data:
            sport_type = activity_data.get('sport_type', '').lower()
            if 'ride' in sport_type or 'cycling' in sport_type or sport_type == 'ride':
                logger.info("[intervals][data-source] activity是骑行活动: sport_type=%s", sport_type)
                return True
            if 'run' in sport_type or 'walk' in sport_type or 'hike' in sport_type or 'swim' in sport_type:
                logger.info("[intervals][data-source] activity不是骑行活动: sport_type=%s", sport_type)
                return False
        

        
        # 默认返回False（保守策略，假设是非骑行活动）
        return False

    def _select_intervals_data_source(
        self,
        is_cycling: bool,
        power_series: List[int],
        heart_rate_series: Optional[List[int]],
        ftp_value: Optional[float],
        lthr_value: Optional[float],
        hr_max_value: Optional[float],
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        根据活动类型和数据可用性，选择intervals计算的数据源
        
        Args:
            is_cycling: 是否为骑行活动
            power_series: 功率数据序列
            heart_rate_series: 心率数据序列
            ftp_value: FTP值
            lthr_value: 阈值心率
            hr_max_value: 最大心率
            
        Returns:
            (数据源类型, 参考值): 
            - ("power", ftp) - 使用功率数据
            - ("heartrate_lthr", lthr) - 使用阈值心率
            - ("heartrate_max", hr_max) - 使用最大心率（估算LTHR）
            - (None, None) - 无法计算
        """
        # 检查心率数据是否可用
        has_heartrate = (
            heart_rate_series 
            and len([x for x in heart_rate_series if x and x > 0]) > 0
        )
        
        # 检查功率数据是否可用
        has_power = (
            power_series 
            and len([x for x in power_series if x and x > 0]) > 0
        )
        
        if is_cycling:
            # 骑行活动：功率 > 阈值心率 > 最大心率
            if has_power and ftp_value and ftp_value > 0:
                logger.info("[intervals][data-source] activity使用功率检测: ftp=%s", ftp_value)
                return ("power", ftp_value)
            if has_heartrate and lthr_value and lthr_value > 0:
                logger.info("[intervals][data-source] activity使用阈值心率检测: lthr=%s", lthr_value)
                return ("heartrate_lthr", lthr_value)
            if has_heartrate and hr_max_value and hr_max_value > 0:
                logger.info("[intervals][data-source] activity使用最大心率检测（估算LTHR）: hr_max=%s", hr_max_value)
                return ("heartrate_max", hr_max_value)
        else:
            # 其他活动：阈值心率 > 最大心率
            if has_heartrate and lthr_value and lthr_value > 0:
                logger.info("[intervals][data-source] activity使用阈值心率检测: lthr=%s", lthr_value)
                return ("heartrate_lthr", lthr_value)
            if has_heartrate and hr_max_value and hr_max_value > 0:
                logger.info("[intervals][data-source] activity使用最大心率检测（估算LTHR）: hr_max=%s", hr_max_value)
                return ("heartrate_max", hr_max_value)
        
        logger.warning("[intervals][data-source] 无可用数据源: is_cycling=%s, has_power=%s, has_hr=%s", 
                      is_cycling, has_power, has_heartrate)
        return (None, None)

    def _build_interval_response_by_heartrate_simplified(
        self,
        timestamps: Sequence[int],
        heart_rate_series: Sequence[int],
        lthr_value: Optional[float],
        hr_max_value: Optional[float],
        preview_file: Optional[Path],
    ) -> IntervalsResponse:
        """构建简化的 intervals 响应（心率检测）"""
        from ..core.analytics.interval_detection import (
            detect_intervals_by_heartrate,
            _resolve_lthr_value,
        )
        
        # 解析阈值心率
        lthr = _resolve_lthr_value(lthr_value, hr_max_value)
        if not lthr or lthr <= 0:
            logger.warning("[intervals][heartrate] 无法获取有效阈值心率")
            return None
        
        sample_count = len(heart_rate_series) if heart_rate_series else 0
        synthetic_activity_payload = {"moving_time": timestamps[-1] if timestamps else 0}
        sample_interval = self._estimate_sample_interval(
            timestamps,
            synthetic_activity_payload,
            sample_count
        )
        
        # 执行心率检测
        detection = detect_intervals_by_heartrate(
            timestamps,
            heart_rate_series,
            lthr=lthr_value,
            hr_max=hr_max_value,
        )
        
        timeline = list(timestamps) if isinstance(timestamps, (list, tuple)) else list(timestamps)
        simplified_intervals: List[SimplifiedIntervalItem] = []
        
        for summary in detection.intervals:
            start_idx = self._locate_index(timeline, summary.start)
            end_idx = self._locate_index(timeline, summary.end, default=len(heart_rate_series))
            avg_hr = float(np.mean(heart_rate_series[start_idx:end_idx])) if heart_rate_series and start_idx < len(heart_rate_series) else 0.0
            # 对于心率检测，power_ratio 实际上是心率比率
            hr_ratio = avg_hr / lthr if lthr > 0 else 0.0
            
            simplified_intervals.append(SimplifiedIntervalItem(
                start=int(summary.start),
                end=int(summary.end),
                duration=int(summary.end - summary.start),
                classification=summary.classification,
                avg_power=round(avg_hr, 2),  # 这里存储的是平均心率
                power_ratio=round(hr_ratio, 2),  # 这里存储的是心率比率
            ))
        
        # 处理repeats
        if detection.repeats:
            for block in detection.repeats:
                start_idx = self._locate_index(timeline, block.start)
                end_idx = self._locate_index(timeline, block.end, default=len(heart_rate_series))
                avg_hr = float(np.mean(heart_rate_series[start_idx:end_idx])) if heart_rate_series and start_idx < len(heart_rate_series) else 0.0
                hr_ratio = avg_hr / lthr if lthr > 0 else 0.0
                
                simplified_intervals.append(SimplifiedIntervalItem(
                    start=int(block.start),
                    end=int(block.end),
                    duration=int(block.end - block.start),
                    classification=block.classification,
                    avg_power=round(avg_hr, 2),
                    power_ratio=round(hr_ratio, 2),
                ))
        
        simplified_intervals.sort(key=lambda item: item.start)
        
        # 生成预览图（TODO: 实现心率版本的预览图生成）
        preview_path = None
        # if preview_file is not None and simplified_intervals:
        #     preview_file.parent.mkdir(parents=True, exist_ok=True)
        #     render_interval_preview_by_heartrate(...)  # 需要实现
        #     if preview_file.exists():
        #         preview_path = str(preview_file)
        
        return IntervalsResponse(
            duration=int(detection.duration),
            ftp=round(float(lthr)),  # 使用阈值心率值（LTHR或估算值），四舍五入到整数
            intervals=simplified_intervals,
            preview_image=preview_path,
        )

    @staticmethod
    def _resolve_thresholds(
        athlete: Optional[Any],
        ftp_override: Optional[float] = None,
        lthr_override: Optional[float] = None,
        hr_max_override: Optional[float] = None,
        athlete_payload: Optional[Dict[str, Any]] = None,
        activity_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        ftp_value: Optional[float] = None
        lthr_value: Optional[float] = None
        hr_max_value: Optional[float] = None

        if ftp_override and ftp_override > 0:
            ftp_value = float(ftp_override)
        elif athlete and getattr(athlete, 'ftp', None):
            try:
                ftp_value = float(getattr(athlete, 'ftp'))
                # logger.info(f"ftp_value: {ftp_value}")
            except Exception:
                ftp_value = None
        elif athlete_payload and athlete_payload.get('ftp'):
            try:
                ftp_value = float(athlete_payload.get('ftp'))
                # logger.info(f"ftp_value-2: {ftp_value}")
            except Exception:
                ftp_value = None

        if lthr_override and lthr_override > 0:
            lthr_value = float(lthr_override)
        elif athlete and int(getattr(athlete, 'is_threshold_active', 0) or 0) == 1 and getattr(athlete, 'threshold_heartrate', None):
            try:
                lthr_value = float(getattr(athlete, 'threshold_heartrate'))
            except Exception:
                lthr_value = None
        elif athlete_payload and athlete_payload.get('lthr'):
            try:
                lthr_value = float(athlete_payload.get('lthr'))
            except Exception:
                lthr_value = None

        if hr_max_override and hr_max_override > 0:
            hr_max_value = float(hr_max_override)
        elif athlete and getattr(athlete, 'max_heartrate', None):
            try:
                hr_max_value = float(getattr(athlete, 'max_heartrate'))
            except Exception:
                hr_max_value = None
        elif athlete_payload and athlete_payload.get('max_heartrate'):
            try:
                hr_max_value = float(athlete_payload.get('max_heartrate'))
            except Exception:
                hr_max_value = None
        elif activity_payload and activity_payload.get('max_heartrate'):
            try:
                hr_max_value = float(activity_payload.get('max_heartrate'))
            except Exception:
                hr_max_value = None

        return ftp_value, lthr_value, hr_max_value


activity_service = ActivityService()
