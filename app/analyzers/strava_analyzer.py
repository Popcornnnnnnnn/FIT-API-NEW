"""Thin facade for Strava analysis delegating to split modules."""

"""Strava 分析器门面类，负责协调各子模块进行数据分析。
本模块主要用于统一入口，调用分离的分析逻辑。"""

from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
import logging
from time import perf_counter
from ..schemas.activities import AllActivityDataResponse
from .strava import upsampling as _ups, extract as _extract, metrics as _metrics, best_powers as _best


logger = logging.getLogger(__name__)


class StravaAnalyzer:
    @staticmethod
    def analyze_activity_data(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        athlete_data: Dict[str, Any],
        external_id: int,
        db: Session,
        keys: Optional[List[str]] = None,
        resolution: str = "high",
        athlete_entry: Optional[Any] = None,
        activity_entry: Optional[Any] = None,
    ) -> AllActivityDataResponse:
        """整合 Strava 活动/流数据，返回聚合响应。

        参数：
            activity_data: 活动详情（Strava /activities/{id}）
            stream_data  : 流数据（Strava streams，key_by_type=true）
            athlete_data : 运动员信息（当前未使用，预留）
            external_id  : 外部活动 ID
            db           : 数据库会话（用于查询/可选写库）
            keys         : 需要返回的流键（可选）
            resolution   : 目标分辨率（保留字段，无强制影响）
            athlete_entry: 本地/远程运动员能力信息（ftp、w' 等），用于推导衍生流
        """
        perf_marks: List[Tuple[str, float]] = [("start", perf_counter())]
        try:
            if stream_data and _ups.is_low_resolution(stream_data):
                prepared    = _ups.prepare_for_upsampling(stream_data)
                stream_data = _ups.upsample_low_resolution(prepared, activity_data.get('moving_time', 0))
                perf_marks.append(("upsample", perf_counter()))
            else:
                perf_marks.append(("upsample_check", perf_counter()))

            stream_data = _extract.enrich_with_derived_streams(stream_data, activity_data, athlete_entry)
            perf_marks.append(("enrich", perf_counter()))

            streams = _extract.extract_stream_data(stream_data, keys, resolution) if keys else None
            perf_marks.append(("extract", perf_counter())) # ! SLOW

            best_powers, segment_records = _best.analyze_best_powers(
                activity_data,
                stream_data,
                external_id,
                db,
                athlete_entry if athlete_entry is not None else getattr(activity_entry, 'athlete_id', None),
                activity_entry,
            )
            perf_marks.append(("best_powers", perf_counter())) # ! SLOW

            overall = _metrics.analyze_overall(activity_data, stream_data, external_id, db)
            perf_marks.append(("metrics_overall", perf_counter()))
            power = _metrics.analyze_power(activity_data, stream_data, external_id, db)
            perf_marks.append(("metrics_power", perf_counter()))
            heartrate = _metrics.analyze_heartrate(activity_data, stream_data)
            perf_marks.append(("metrics_heartrate", perf_counter()))
            cadence = _metrics.analyze_cadence(activity_data, stream_data)
            perf_marks.append(("metrics_cadence", perf_counter()))
            speed = _metrics.analyze_speed(activity_data, stream_data)
            perf_marks.append(("metrics_speed", perf_counter())) # OKAY
            training_effect = _metrics.analyze_training_effect(activity_data, stream_data, external_id, db)
            perf_marks.append(("metrics_training", perf_counter()))
            altitude = _metrics.analyze_altitude(activity_data, stream_data)
            perf_marks.append(("metrics_altitude", perf_counter())) # OKAY
            temp = _metrics.analyze_temperature(activity_data, stream_data)
            perf_marks.append(("metrics_temp", perf_counter())) # OKAY
            zones = _metrics.analyze_zones(activity_data, stream_data, external_id, db)
            perf_marks.append(("metrics_zones", perf_counter()))

            response = AllActivityDataResponse(
                overall         = overall,
                power           = power,
                heartrate       = heartrate,
                cadence         = cadence,
                speed           = speed,
                training_effect = training_effect,
                altitude        = altitude,
                temp            = temp,
                zones           = zones,
                best_powers     = best_powers,
                streams         = streams,
                segment_records = segment_records,
            )
            perf_marks.append(("build_response", perf_counter()))
            return response
        finally:
            perf_marks.append(("end", perf_counter()))
            # StravaAnalyzer._log_perf_timeline("analyzer.strava", external_id, perf_marks)
            print()

    @staticmethod
    def analyze_best_powers(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        external_id: Optional[int] = None,
        db: Optional[Session] = None,
        athlete: Optional[Any] = None,
        activity_entry: Optional[Any] = None,
    ):
        """提取最佳功率曲线并尝试更新个人纪录（安全失败）。"""
        return _best.analyze_best_powers(activity_data, stream_data, external_id, db, athlete, activity_entry)

    @staticmethod
    def _log_perf_timeline(tag: str, activity_id: int, marks: List[Tuple[str, float]]) -> None:
        if not marks or len(marks) < 2:
            return
        segments = []
        prev_ts = marks[0][1]
        for label, ts in marks[1:]:
            segments.append(f"{label}={(ts - prev_ts) * 1000:.1f}ms")
            prev_ts = ts
        total = (marks[-1][1] - marks[0][1]) * 1000
        logger.info(
            "[perf][%s] activity_id=%s total=%.1fms %s",
            tag,
            activity_id,
            total,
            " | ".join(segments),
        )
