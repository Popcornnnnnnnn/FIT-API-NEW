"""Thin facade for Strava analysis delegating to split modules."""

"""Strava 分析器门面类，负责协调各子模块进行数据分析。
本模块主要用于统一入口，调用分离的分析逻辑。"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging
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
    ) -> AllActivityDataResponse:
        """整合 Strava 活动/流数据，返回聚合响应。

        参数：
            activity_data: 活动详情（Strava /activities/{id}）
            stream_data: 流数据（Strava streams，key_by_type=true）
            athlete_data: 运动员信息（当前未使用，预留）
            external_id: 外部活动 ID
            db: 数据库会话（用于查询/可选写库）
            keys: 需要返回的流键（可选）
            resolution: 目标分辨率（保留字段，无强制影响）
        """
        if stream_data and _ups.is_low_resolution(stream_data):
            prepared = _ups.prepare_for_upsampling(stream_data)
            stream_data = _ups.upsample_low_resolution(prepared, activity_data.get('moving_time', 0))

        streams = _extract.extract_stream_data(stream_data, keys, resolution) if keys else None
        best_powers, segment_records = _best.analyze_best_powers(activity_data, stream_data, external_id, db, None)

        return AllActivityDataResponse(
            overall=_metrics.analyze_overall(activity_data, stream_data, external_id, db),
            power=_metrics.analyze_power(activity_data, stream_data, external_id, db),
            heartrate=_metrics.analyze_heartrate(activity_data, stream_data),
            cadence=None,
            speed=_metrics.analyze_speed(activity_data, stream_data),
            training_effect=_metrics.analyze_training_effect(activity_data, stream_data, external_id, db),
            altitude=_metrics.analyze_altitude(activity_data, stream_data),
            temp=_metrics.analyze_temperature(activity_data, stream_data),
            zones=_metrics.analyze_zones(activity_data, stream_data, external_id, db),
            best_powers=best_powers,
            streams=streams,
            segment_records=segment_records,
        )

    @staticmethod
    def analyze_best_powers(
        activity_data: Dict[str, Any],
        stream_data: Dict[str, Any],
        external_id: Optional[int] = None,
        db: Optional[Session] = None,
        athlete_id: Optional[int] = None,
    ):
        """提取最佳功率曲线并尝试更新个人纪录（安全失败）。"""
        return _best.analyze_best_powers(activity_data, stream_data, external_id, db, athlete_id)
