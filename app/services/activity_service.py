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

from ..clients.strava_client import StravaClient
from ..schemas.activities import (
    AllActivityDataResponse,
    ZoneData,
    IntervalsResponse,
    IntervalItem,
    BestPowerCurveRecord,
)
from ..streams.crud import stream_crud
from ..streams.models import Resolution
from ..infrastructure.data_manager import activity_data_manager
from ..analyzers.strava_analyzer import StravaAnalyzer
from ..core.analytics import zones as ZoneAnalyzer
from ..core.analytics.interval_detection import (
    detect_intervals,
    render_interval_preview,
    summarize_window,
    IntervalSummary,
)


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
            # 尝试将本地活动ID映射为 Strava external_id，再调用 Strava
            strava_id = activity_id
            athlete_obj = None
            local_activity = None
            try:
                from ..db.models import TbActivity
                local = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
                if local:
                    local_activity = local
                if local and getattr(local, 'external_id', None):
                    try:
                        strava_id = int(str(local.external_id))
                        logger.debug("[strava-id-map] local activity %s -> external_id %s", activity_id, strava_id)
                    except Exception:
                        pass
                    if getattr(local, 'athlete_id', None):
                        from ..repositories.activity_repo import get_activity_athlete
                        try:
                            pair_local = get_activity_athlete(db, activity_id)
                            if pair_local:
                                _, athlete_obj = pair_local
                        except Exception:
                            athlete_obj = None
            except Exception:
                pass

            try:
                full = client.fetch_full(strava_id, keys=keys_list_all, resolution=None)
            except Exception as e:
                # 统一转译为 HTTP 异常，便于路由返回明确信息
                try:
                    from ..clients.strava_client import StravaApiError
                    from fastapi import HTTPException
                except Exception:
                    StravaApiError = None  # type: ignore
                    HTTPException = Exception  # type: ignore

                if StravaApiError and isinstance(e, StravaApiError):
                    # 如果是 404，提示更明确的原因
                    if e.status_code == 404:
                        # 若当前 strava_id 就是传入 activity_id，提示可能传了本地ID
                        if strava_id == activity_id:
                            raise HTTPException(status_code=404, detail="Strava 活动不存在或无权限访问（404）。请确认传入的是 Strava 活动ID，或在本地活动上绑定 external_id 后重试。")
                        else:
                            raise HTTPException(status_code=404, detail="Strava 活动不存在或无权限访问（404）。external_id 无效或不可访问。")
                    else:
                        raise HTTPException(status_code=e.status_code, detail=f"Strava API 错误: {e.message}")
                else:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=500, detail=f"调用 Strava 失败: {str(e)}")

            activity_data = full['activity']
            stream_data = full['streams']
            athlete_data = full['athlete']

            athlete_profile: Optional[Dict[str, Any]] = None
            profile_candidate: Dict[str, Any] = {}
            if athlete_obj:
                try:
                    ftp_local = getattr(athlete_obj, 'ftp', None)
                    if ftp_local:
                        profile_candidate['ftp'] = int(ftp_local)
                except Exception:
                    pass
                try:
                    w_prime_local = getattr(athlete_obj, 'w_balance', None)
                    if w_prime_local:
                        profile_candidate['w_prime'] = int(w_prime_local)
                except Exception:
                    pass
                try:
                    weight_local = getattr(athlete_obj, 'weight', None)
                    if weight_local:
                        profile_candidate['weight'] = float(weight_local)
                except Exception:
                    pass

            if isinstance(athlete_data, dict):
                try:
                    ftp_remote = athlete_data.get('ftp')
                    if ftp_remote:
                        profile_candidate.setdefault('ftp', int(ftp_remote))
                except Exception:
                    pass
                try:
                    weight_remote = athlete_data.get('weight') or athlete_data.get('weight_kg')
                    if weight_remote:
                        profile_candidate.setdefault('weight', float(weight_remote))
                except Exception:
                    pass
                try:
                    w_balance_remote = athlete_data.get('w_balance') or athlete_data.get('w_prime') or athlete_data.get('wj')
                    if w_balance_remote:
                        profile_candidate.setdefault('w_prime', float(w_balance_remote))
                except Exception:
                    pass

            if profile_candidate:
                athlete_profile = profile_candidate

            if keys:
                keys_list = [k.strip() for k in keys.split(',') if k.strip()]
            else:
                keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']

            result = StravaAnalyzer.analyze_activity_data(
                activity_data,
                stream_data,
                athlete_data,
                activity_id,
                db,
                keys_list,
                resolution,
                athlete_profile=athlete_profile,
            )
            try:
                hr_metrics = getattr(result, 'heartrate', None)
            except Exception:
                hr_metrics = None
            efficiency_value = None
            if hr_metrics is not None:
                if isinstance(hr_metrics, dict):
                    efficiency_value = hr_metrics.get('efficiency_index')
                else:
                    efficiency_value = getattr(hr_metrics, 'efficiency_index', None)
            try:
                from ..db.models import TbActivity
                target_activity = local_activity
                if target_activity is None:
                    target_activity = db.query(TbActivity).filter(TbActivity.external_id == str(strava_id)).first()
                if target_activity:
                    if local_activity is None:
                        local_activity = target_activity
                    self._update_activity_efficiency_factor(db, target_activity, efficiency_value)
            except Exception as e:
                logger.exception("[db-error][efficiency-factor-strava] activity_id=%s err=%s", activity_id, e)
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
                # 附加 best_power_record（独立于分辨率）
                try:
                    from ..db.models import TbActivity
                    from ..repositories.best_power_file_repo import load_best_curve
                    # 尝试用 external_id 反查本地 athlete_id
                    best_power_record = None
                    local = db.query(TbActivity).filter(TbActivity.external_id == str(strava_id)).first()
                    if local and getattr(local, 'athlete_id', None):
                        curve = load_best_curve(int(local.athlete_id))
                        if curve:
                            best_power_record = {
                                'athlete_id': int(local.athlete_id),
                                'length': len(curve),
                                'best_curve': curve,
                            }
                    result.best_power_record = (
                        BestPowerCurveRecord.model_validate(best_power_record)
                        if best_power_record
                        else None
                    )
                except Exception:
                    result.best_power_record = None
                try:
                    power_series, timestamps, heart_rate_series = self._extract_series_from_streams(stream_data)
                    ftp_value, lthr_value, hr_max_value = self._resolve_thresholds(
                        athlete_obj,
                        athlete_payload=athlete_data,
                        activity_payload=activity_data,
                    )
                    if power_series and ftp_value and ftp_value > 0:
                        preview_file = self._build_preview_path(
                            None,
                            default_name=f"interval_preview_strava_{strava_id}.png",
                        )
                        intervals_resp = self._build_interval_response(
                            power_series,
                            timestamps,
                            heart_rate_series,
                            ftp_value,
                            lthr_value,
                            hr_max_value,
                            preview_file,
                        )
                        result.intervals = intervals_resp
                except Exception:
                    logger.exception("[section-error][intervals-strava] activity_id=%s", activity_id)
                    pass
            except Exception:
                pass
            return result

        # Local DB path: compose using service methods and metrics
        response_data = {}
        try:
            response_data["overall"] = self.get_overall(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][overall] activity_id=%s err=%s", activity_id, e)
            response_data["overall"] = None
        try:
            response_data["power"] = self.get_power(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][power] activity_id=%s err=%s", activity_id, e)
            response_data["power"] = None
        try:
            response_data["heartrate"] = self.get_heartrate(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][heartrate] activity_id=%s err=%s", activity_id, e)
            response_data["heartrate"] = None
        try:
            response_data["cadence"] = self.get_cadence(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][cadence] activity_id=%s err=%s", activity_id, e)
            response_data["cadence"] = None
        try:
            response_data["speed"] = self.get_speed(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][speed] activity_id=%s err=%s", activity_id, e)
            response_data["speed"] = None
        try:
            response_data["training_effect"] = self.get_training_effect(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][training_effect] activity_id=%s err=%s", activity_id, e)
            response_data["training_effect"] = None
        try:
            response_data["altitude"] = self.get_altitude(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][altitude] activity_id=%s err=%s", activity_id, e)
            response_data["altitude"] = None
        try:
            response_data["temp"] = self.get_temperature(db, activity_id)
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
            stream_raw = activity_data_manager.get_activity_stream_data(db, activity_id)
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

        try:
            response_data["intervals"] = self.get_intervals(db, activity_id)
        except Exception as e:
            logger.exception("[section-error][intervals] activity_id=%s err=%s", activity_id, e)
            response_data["intervals"] = None

        return AllActivityDataResponse(**response_data)

    # ---- helpers ----
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
            buckets = ZoneAnalyzer.analyze_heartrate_zones_lthr(hr, lthr)
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

    def get_intervals(
        self,
        db: Session,
        activity_id: int,
        access_token: Optional[str] = None,
        ftp_override: Optional[float] = None,
        lthr_override: Optional[float] = None,
        hr_max_override: Optional[float] = None,
        preview_dir: Optional[str] = None,
    ) -> Optional[IntervalsResponse]:
        if access_token:
            return self._get_intervals_from_strava(
                db,
                activity_id,
                access_token,
                ftp_override=ftp_override,
                lthr_override=lthr_override,
                hr_max_override=hr_max_override,
                preview_dir=preview_dir,
            )
        return self._get_intervals_from_local(
            db,
            activity_id,
            ftp_override=ftp_override,
            lthr_override=lthr_override,
            hr_max_override=hr_max_override,
            preview_dir=preview_dir,
        )

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
        result = compute_heartrate_info(stream_data, bool(stream_data.get('power')), session_data)
        efficiency_value = None
        if isinstance(result, dict):
            efficiency_value = result.get('efficiency_index')
        self._update_activity_efficiency_factor(db, activity, efficiency_value)
        return result

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

    def _get_intervals_from_local(
        self,
        db: Session,
        activity_id: int,
        ftp_override: Optional[float] = None,
        lthr_override: Optional[float] = None,
        hr_max_override: Optional[float] = None,
        preview_dir: Optional[str] = None,
    ) -> Optional[IntervalsResponse]:
        from ..repositories.activity_repo import get_activity_athlete

        pair = get_activity_athlete(db, activity_id)
        if not pair:
            return None
        activity, athlete = pair
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if not stream_data:
            return None

        power_series = stream_data.get('power') or []
        if not power_series:
            return None
        timestamps = stream_data.get('timestamp') or list(range(len(power_series)))
        heart_rate_series = stream_data.get('heart_rate') or None

        ftp_value, lthr_value, hr_max_value = self._resolve_thresholds(
            athlete,
            ftp_override=ftp_override,
            lthr_override=lthr_override,
            hr_max_override=hr_max_override,
        )
        if not ftp_value or ftp_value <= 0:
            return None

        preview_file = self._build_preview_path(
            preview_dir,
            default_name=f"interval_preview_{activity_id}.png",
        )

        return self._build_interval_response(
            power_series,
            timestamps,
            heart_rate_series,
            ftp_value,
            lthr_value,
            hr_max_value,
            preview_file,
        )

    def _get_intervals_from_strava(
        self,
        db: Session,
        activity_id: int,
        access_token: str,
        ftp_override: Optional[float] = None,
        lthr_override: Optional[float] = None,
        hr_max_override: Optional[float] = None,
        preview_dir: Optional[str] = None,
    ) -> Optional[IntervalsResponse]:
        strava_id = activity_id
        athlete_obj = None
        try:
            from ..db.models import TbActivity
            local = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
            if local and getattr(local, 'external_id', None):
                try:
                    strava_id = int(str(local.external_id))
                except Exception:
                    pass
                if getattr(local, 'athlete_id', None):
                    from ..repositories.activity_repo import get_activity_athlete
                    pair = get_activity_athlete(db, activity_id)
                    if pair:
                        _, athlete_obj = pair
        except Exception:
            athlete_obj = None

        client = StravaClient(access_token)
        try:
            keys = ['time', 'elapsed_time', 'watts', 'heartrate']
            full = client.fetch_full(strava_id, keys=keys, resolution=None)
        except Exception:
            return None

        stream_data = full.get('streams') or {}
        activity_data = full.get('activity') or {}
        athlete_data = full.get('athlete') or {}

        power_series, timestamps, heart_rate_series = self._extract_series_from_streams(stream_data)
        if not power_series:
            return None

        ftp_value, lthr_value, hr_max_value = self._resolve_thresholds(
            athlete_obj,
            ftp_override=ftp_override,
            lthr_override=lthr_override,
            hr_max_override=hr_max_override,
            athlete_payload=athlete_data,
            activity_payload=activity_data,
        )
        if not ftp_value or ftp_value <= 0:
            return None

        preview_file = self._build_preview_path(
            preview_dir,
            default_name=f"interval_preview_strava_{strava_id}.png",
        )

        return self._build_interval_response(
            power_series,
            timestamps,
            heart_rate_series,
            ftp_value,
            lthr_value,
            hr_max_value,
            preview_file,
        )


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

    def _build_interval_response(
        self,
        power_series: Sequence[int],
        timestamps: Sequence[int],
        heart_rate_series: Optional[Sequence[int]],
        ftp_value: float,
        lthr_value: Optional[float],
        hr_max_value: Optional[float],
        preview_file: Optional[Path],
    ) -> IntervalsResponse:
        detection = detect_intervals(
            timestamps,
            power_series,
            ftp_value,
            heart_rate=heart_rate_series,
            lthr=lthr_value,
            hr_max=hr_max_value,
        )

        timeline = list(timestamps) if isinstance(timestamps, (list, tuple)) else list(timestamps)
        items: List[IntervalItem] = []
        for summary in detection.intervals:
            items.append(self._interval_summary_to_item(summary, timeline))

        if detection.repeats:
            for block in detection.repeats:
                start_idx = self._locate_index(timeline, block.start)
                end_idx = self._locate_index(timeline, block.end, default=len(power_series))
                repeat_summary = summarize_window(
                    power_series,
                    heart_rate_series,
                    ftp_value,
                    start_idx,
                    end_idx,
                    lthr=lthr_value,
                    hr_max=hr_max_value,
                )
                repeat_summary.classification = block.classification
                metadata = dict(repeat_summary.metadata)
                metadata['cycles'] = block.cycles
                repeat_summary.metadata = metadata
                items.append(self._interval_summary_to_item(repeat_summary, timeline, block.start, block.end))

        items.sort(key=lambda item: item.start)

        preview_path = None
        if preview_file is not None and items:
            preview_file.parent.mkdir(parents=True, exist_ok=True)
            render_interval_preview(detection, timeline, power_series, str(preview_file))
            if preview_file.exists():
                preview_path = str(preview_file)

        return IntervalsResponse(
            duration=int(detection.duration),
            ftp=float(detection.ftp),
            items=items,
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
            except Exception:
                ftp_value = None
        elif athlete_payload and athlete_payload.get('ftp'):
            try:
                ftp_value = float(athlete_payload.get('ftp'))
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
