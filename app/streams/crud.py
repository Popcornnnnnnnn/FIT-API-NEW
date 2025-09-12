"""
本文件包含流数据相关的数据库操作函数（CRUD操作）。

提供以下功能：
1. 流数据的获取和缓存
2. FIT文件解析和流数据提取
3. 流数据的重采样和格式化
"""

import base64
import json
import requests
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from . import models
from .fit_parser import FitParser
from .models import SeriesType
from ..db.models import TbActivity, TbAthlete

class StreamCRUD:
    """流数据CRUD操作类"""
    
    def __init__(self):
        """初始化CRUD操作"""
        self.fit_parser = FitParser()
    
    def get_activity_streams(
        self, 
        db: Session, 
        activity_id: int, 
        keys: List[str], 
        resolution: models.Resolution = models.Resolution.HIGH
    ) -> List[Dict[str, Any]]:
        # 检查活动是否存在
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return []
        
        # 获取或解析流数据
        stream_data = self._get_or_parse_stream_data(db, activity)
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
                        from ..activities.strava_analyzer import StravaAnalyzer
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
                            'activity_id': activity.id
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
                            athlete_id=activity.athlete_id
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
        stream_data = self._get_or_parse_stream_data(db, activity)
        available_streams = stream_data.get_available_streams()
        
        return {
            "status": "success",
            "message": "获取成功",
            "available_streams": available_streams,
            "total_streams": len(available_streams)
        }
    
    def _get_or_parse_stream_data(
        self, 
        db: Session, 
        activity: models.TbActivity
    ) -> Optional[models.StreamData]:
        try:
            response = requests.get(activity.upload_fit_url, timeout=30)
            response.raise_for_status()
            file_data = response.content
            
            
            athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
            athlete_info = {
                'ftp': int(athlete.ftp),
                'wj': athlete.w_balance
            }
            return self.fit_parser.parse_fit_file(file_data, athlete_info)
            
        except Exception as e:
            return None
    
# 创建全局实例
stream_crud = StreamCRUD() 
