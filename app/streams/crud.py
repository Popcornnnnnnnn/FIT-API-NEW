"""
本文件包含流数据相关的数据库操作函数（CRUD操作）。

提供以下功能：
1. 流数据的获取和缓存
2. FIT文件解析和流数据提取
3. 流数据的重采样和格式化
"""

import base64
import json
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from . import models
from .fit_parser import FitParser
from ..activities.models import Activity

class StreamCRUD:
    """流数据CRUD操作类"""
    
    def __init__(self):
        """初始化CRUD操作"""
        self.fit_parser = FitParser()
        # 简单的内存缓存，实际项目中应该使用Redis等
        self._stream_cache = {}
    
    def get_activity_streams(
        self, 
        db: Session, 
        activity_id: int, 
        keys: List[str], 
        resolution: models.Resolution = models.Resolution.HIGH,
        series_type: models.SeriesType = models.SeriesType.NONE
    ) -> List[Dict[str, Any]]:
        """
        获取活动的流数据，支持series_type参数
        """
        # 检查活动是否存在
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return []
        # 获取或解析流数据
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return []
        # 获取原始distance和timestamp数据（用于distance系列类型）
        original_distance = stream_data.distance
        original_timestamp = stream_data.timestamp
        
        # 获取重采样后的distance和timestamp数据（用于其他用途）
        resampled_distance = stream_data._resample_data(stream_data.distance, resolution)
        resampled_timestamp = stream_data._resample_data(stream_data.timestamp, resolution)
        result = []
        for key in keys:
            if key in self.fit_parser.supported_fields:
                key_data = stream_data._resample_data(getattr(stream_data, key), resolution)
                if not key_data:
                    continue
                # 获取原始数据长度（不经过重采样）
                original_data = getattr(stream_data, key)
                original_size = len(original_data) if original_data else 0
                
                if series_type == models.SeriesType.DISTANCE:
                    # 使用原始distance数据，确保distance间隔准确
                    min_len = min(len(key_data), len(original_distance))
                    data = [{"distance": original_distance[i], "value": key_data[i]} for i in range(min_len)]
                    result.append({
                        "type": key,
                        "data": data,
                        "series_type": "distance",
                        "original_size": original_size,
                        "resolution": resolution.value
                    })
                elif series_type == models.SeriesType.TIME:
                    # 使用原始timestamp数据，确保时间间隔准确
                    min_len = min(len(key_data), len(original_timestamp))
                    data = [{"time": original_timestamp[i], "value": key_data[i]} for i in range(min_len)]
                    result.append({
                        "type": key,
                        "data": data,
                        "series_type": "time",
                        "original_size": original_size,
                        "resolution": resolution.value
                    })
                else:
                    # none: 只返回key序列本身
                    data = key_data
                    result.append({
                        "type": key,
                        "data": data,
                        "series_type": "none",
                        "original_size": original_size,
                        "resolution": resolution.value
                    })
        return result
    
    def get_available_streams(self, db: Session, activity_id: int) -> List[str]:
        """
        获取活动可用的流数据类型
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            
        Returns:
            List[str]: 可用的流类型列表
        """
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return []
        
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return []
        
        return stream_data.get_available_streams()
    
    def get_stream_summary(self, db: Session, activity_id: int, stream_type: str) -> Optional[Dict[str, Any]]:
        """
        获取指定流类型的统计信息
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            stream_type: 流类型
            
        Returns:
            Dict: 统计信息
        """
        activity = db.query(Activity).filter(Activity.id == activity_id).first()
        if not activity:
            return None
        
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return None
        
        return stream_data.get_summary_stats(stream_type)
    
    def _get_or_parse_stream_data(self, db: Session, activity: Activity) -> Optional[models.StreamData]:
        """
        获取或解析活动的流数据
        
        Args:
            db: 数据库会话
            activity: 活动对象
            
        Returns:
            StreamData: 流数据对象
        """
        # 检查缓存
        cache_key = f"activity_{activity.id}"
        if cache_key in self._stream_cache:
            return self._stream_cache[cache_key]
        
        # 从数据库获取文件数据
        if not activity.file_data:
            return None
        
        try:
            # 解码Base64数据
            file_data = base64.b64decode(activity.file_data)
            
            # 解析FIT文件
            stream_data = self.fit_parser.parse_fit_file(file_data)
            
            # 缓存结果
            self._stream_cache[cache_key] = stream_data
            
            return stream_data
            
        except Exception as e:
            print(f"解析活动 {activity.id} 的流数据时发生错误: {e}")
            return None
    
    def clear_cache(self, activity_id: Optional[int] = None):
        """
        清除缓存
        
        Args:
            activity_id: 活动ID，如果为None则清除所有缓存
        """
        if activity_id is None:
            self._stream_cache.clear()
        else:
            cache_key = f"activity_{activity_id}"
            if cache_key in self._stream_cache:
                del self._stream_cache[cache_key]

# 创建全局实例
stream_crud = StreamCRUD() 