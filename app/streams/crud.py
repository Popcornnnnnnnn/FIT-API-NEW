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
# from ..activities.strava_analyzer import StravaAnalyzer

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
        activity = db.query(models.TbActivity).filter(models.TbActivity.id == activity_id).first()
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
                result.append({
                    "type": key,
                    "data": stream_obj.data,
                    "series_type": stream_obj.series_type,
                    "original_size": original_size,
                    "resolution": actual_resolution.value
                })
        
        return result
    
    def get_available_streams(
        self, db: Session, 
        activity_id: int
    ) -> Dict[str, Any]:
        activity = db.query(models.TbActivity).filter(models.TbActivity.id == activity_id).first()
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
            
            
            athlete = db.query(models.TbAthlete).filter(models.TbAthlete.id == activity.athlete_id).first()
            athlete_info = {
                'ftp': int(athlete.ftp),
                'wj': athlete.w_balance
            }
            return self.fit_parser.parse_fit_file(file_data, athlete_info)
            
        except Exception as e:
            return None
    
# 创建全局实例
stream_crud = StreamCRUD() 