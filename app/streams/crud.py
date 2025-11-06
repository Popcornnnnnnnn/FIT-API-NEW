"""
数据流 CRUD 层（与 FIT 解析器协作）

提供：
1) 流数据的获取与统一返回格式；
2) 从 FIT 文件解析 records，并构建 StreamData；
3) 重采样（分辨率 high/medium/low）与 best_power 的附加处理（含可选写库）。
"""

import base64
import json
import requests
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from . import models
from .fit_parser import FitParser
from .models import SeriesType
from ..db.models import TbActivity, TbAthlete
from fitparse import FitFile
from io import BytesIO

logger = logging.getLogger(__name__)

class StreamCRUD:
    """流数据CRUD操作类"""
    
    def __init__(self):
        """初始化CRUD操作"""
        self.fit_parser = FitParser()
        self._parsed_cache: Dict[int, models.StreamData] = {}
        self._session_cache: Dict[int, Optional[Dict[str, Any]]] = {}
        self._raw_fit_cache: Dict[int, bytes] = {}

    def _parse_session_from_bytes(self, file_data: bytes) -> Optional[Dict[str, Any]]:
        try:
            fitfile = FitFile(BytesIO(file_data))
            fields = [
                'total_distance', 'total_elapsed_time', 'total_timer_time',
                'avg_power', 'max_power', 'avg_heart_rate', 'max_heart_rate',
                'total_calories', 'total_ascent', 'total_descent',
                'avg_cadence', 'max_cadence', 'left_right_balance',
                'left_torque_effectiveness', 'right_torque_effectiveness',
                'left_pedal_smoothness', 'right_pedal_smoothness',
                'avg_speed', 'max_speed', 'avg_temperature', 'max_temperature', 'min_temperature',
                'normalized_power', 'training_stress_score', 'intensity_factor',
                'sport', 'sub_sport'  # 添加运动类型字段
            ]
            for message in fitfile.get_messages('session'):
                session_data: Dict[str, Any] = {}
                for field in fields:
                    value = message.get_value(field)
                    if value is not None:
                        # 对于 sport 和 sub_sport，如果是枚举值，转换为字符串
                        if field in ('sport', 'sub_sport'):
                            # fitparse 返回的可能是枚举对象，需要转换为字符串
                            if hasattr(value, 'name'):
                                session_data[field] = value.name.lower()
                            elif isinstance(value, str):
                                session_data[field] = value.lower()
                            else:
                                session_data[field] = str(value).lower()
                        else:
                            session_data[field] = value
                if session_data:
                    return session_data
            return None
        except Exception:
            return None

    def load_stream_data(
        self,
        db: Session,
        activity_id: int,
        activity: Optional[TbActivity] = None,
        use_cache: bool = True,
    ) -> Optional[models.StreamData]:
        """解析活动对应的 FIT 数据并返回 StreamData，默认启用进程内缓存。"""
        if use_cache and activity_id in self._parsed_cache:
            cached = self._parsed_cache[activity_id]
            if getattr(cached, "_parse_failed", False) or getattr(cached, "_fit_backend", None) is None:
                logger.info(
                    "[stream-crud] dropping stale cached stream for activity_id=%s",
                    activity_id,
                )
                self._parsed_cache.pop(activity_id, None)
            else:
                return cached

        if activity is None:
            activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return None

        data = self._get_or_parse_stream_data(db, activity, use_cache=use_cache)
        if data and use_cache:
            self._parsed_cache[activity_id] = data
        return data

    def load_session_data(
        self,
        db: Session,
        activity_id: int,
        fit_url: Optional[str],
        use_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """获取 FIT session 概要，优先使用缓存/已解析的文件。"""
        if use_cache and activity_id in self._session_cache:
            return self._session_cache[activity_id]

        stream_data = self.load_stream_data(db, activity_id, use_cache=use_cache)
        if stream_data and use_cache and activity_id in self._session_cache:
            return self._session_cache[activity_id]

        if fit_url:
            try:
                response = requests.get(fit_url, timeout=30)
                response.raise_for_status()
                session_data = self._parse_session_from_bytes(response.content)
                if use_cache:
                    self._raw_fit_cache[activity_id] = response.content
                    self._session_cache[activity_id] = session_data
                return session_data
            except Exception:
                return None
        return None
        self._parsed_cache: Dict[int, models.StreamData] = {}

    def get_activity_streams(
        self, 
        db: Session, 
        activity_id: int, 
        keys: List[str], 
        resolution: models.Resolution = models.Resolution.HIGH
    ) -> List[Dict[str, Any]]:
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return []

        stream_data = self.load_stream_data(db, activity_id, activity=activity)
        if not stream_data:
            return []
        
        result = []
        for key in keys:
            if key in self.fit_parser.supported_fields:
                try:
                    # 对于 best_power，强制使用 high 分辨率，忽略传入的 resolution 参数
                    if key == 'best_power':
                        stream_obj = stream_data.get_stream(key, models.Resolution.HIGH)
                    else:
                        stream_obj = stream_data.get_stream(key, resolution)
                except ValueError as e:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=400, detail=str(e))
                
                if not stream_obj or not stream_obj.data:
                    continue
                
                # 获取原始数据长度
                original_data = getattr(stream_data, key)
                original_size = len(original_data) if original_data else 0
                
                # 对于 best_power，强制返回 high 分辨率
                actual_resolution = models.Resolution.HIGH if key == 'best_power' else resolution

                # 统一返回格式
                item = {
                    "type": key,
                    "data": stream_obj.data,
                    "series_type": stream_obj.series_type,
                    "original_size": original_size,
                    "resolution": actual_resolution.value
                }

                # 如果请求 best_power，则计算并更新数据库的最佳分段，同时把信息附加到返回中
                if key == 'best_power':
                    try:
                        # 避免循环依赖：在函数内部延迟导入
                        from ..analyzers.strava_analyzer import StravaAnalyzer
                        # 组装 activity_data
                        distance_m = 0
                        if stream_data.distance:
                            try:
                                distance_m = int(stream_data.distance[-1] or 0)
                            except Exception:
                                distance_m = 0

                        # 计算总爬升（正向增量求和）
                        elevation_gain = 0
                        if stream_data.altitude and len(stream_data.altitude) > 1:
                            prev = stream_data.altitude[0]
                            gain = 0
                            for h in stream_data.altitude[1:]:
                                if h is not None and prev is not None:
                                    delta = h - prev
                                    if delta > 0:
                                        gain += delta
                                    prev = h
                            elevation_gain = int(gain)

                        activity_data_stub = {
                            'distance': distance_m,
                            'total_elevation_gain': elevation_gain,
                            'activity_id': activity_id
                        }

                        # 组装 stream_data 为 StravaAnalyzer 可用的格式
                        stream_data_stub = {
                            'watts': { 'data': stream_data.power or [] }
                        }

                        best_powers, segment_records = StravaAnalyzer.analyze_best_powers(
                            activity_data_stub,
                            stream_data_stub,
                            external_id=None,
                            db=db,
                            athlete=activity.athlete_id,
                            activity_entry=activity,
                        )

                        if best_powers:
                            item["best_powers"] = best_powers
                        if segment_records:
                            # pydantic/fastapi可直接序列化 dataclass/pydantic，对象此处假定为可序列化
                            # 若为自定义类，转成 dict
                            try:
                                item["segment_records"] = [sr.model_dump() if hasattr(sr, 'model_dump') else sr.__dict__ for sr in segment_records]
                            except Exception:
                                item["segment_records"] = None
                    except Exception:
                        # 忽略最佳分段更新错误，不影响流数据返回
                        pass

                result.append(item)
        return result

    def get_available_streams(
        self, db: Session, 
        activity_id: int
    ) -> Dict[str, Any]:
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return {
                "status": "error",
                "message": "活动不存在",
                "available_streams": [],
                "total_streams": 0,
            }

        stream_data = self.load_stream_data(db, activity_id, activity=activity)
        if not stream_data:
            return {
                "status": "error",
                "message": "流数据不可用或解析失败",
                "available_streams": [],
                "total_streams": 0,
            }

        available_streams = stream_data.get_available_streams()
        return {
            "status": "success",
            "message": "获取成功",
            "available_streams": available_streams,
            "total_streams": len(available_streams),
        }
    
    def _get_or_parse_stream_data(
        self,
        db: Session,
        activity: TbActivity,
        use_cache: bool = True,
    ) -> Optional[models.StreamData]:
        if use_cache and activity.id in self._parsed_cache:
            return self._parsed_cache[activity.id]

        try:
            if use_cache and activity.id in self._raw_fit_cache:
                file_data = self._raw_fit_cache[activity.id]
            else:
                response = requests.get(activity.upload_fit_url, timeout=30)
                response.raise_for_status()
                file_data = response.content
                if use_cache:
                    self._raw_fit_cache[activity.id] = file_data

            athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
            athlete_info = {
                'ftp': int(athlete.ftp),
                'wj': athlete.w_balance
            }
            parsed = self.fit_parser.parse_fit_file(file_data, athlete_info)
            if getattr(parsed, "_parse_failed", False):
                logger.error(
                    "[stream-crud] parsing failed for activity_id=%s; clearing cached raw data",
                    activity.id,
                )
                if use_cache:
                    self._raw_fit_cache.pop(activity.id, None)
                    self._parsed_cache.pop(activity.id, None)
                return None
            if use_cache:
                self._parsed_cache[activity.id] = parsed
                self._session_cache[activity.id] = self._parse_session_from_bytes(file_data)
            return parsed
        except Exception as e:
            return None
    
# 创建全局实例
stream_crud = StreamCRUD() 
