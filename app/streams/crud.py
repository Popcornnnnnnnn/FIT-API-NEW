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

class StreamCRUD:
    """流数据CRUD操作类"""
    
    def __init__(self):
        """初始化CRUD操作"""
        self.fit_parser = FitParser()
        # 简单的内存缓存，实际项目中应该使用Redis等
        self._stream_cache = {}
    
    def get_single_stream(
        self, 
        db: Session, 
        activity_id: int, 
        key: str, 
        resolution: models.Resolution = models.Resolution.HIGH
    ) -> Optional[List[Any]]:
        """
        获取活动的单个流数据
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            key: 流数据类型
            resolution: 数据分辨率
            
        Returns:
            List: 流数据列表或None
        """
        # 检查活动是否存在
        activity = db.query(models.TbActivity).filter(models.TbActivity.id == activity_id).first()
        if not activity:
            return None
        
        # 获取或解析流数据
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return None
        
        # 检查key是否在支持的字段中
        if key not in self.fit_parser.supported_fields:
            return None
        
        try:
            # 获取流数据
            stream_obj = stream_data.get_stream(key, resolution)
            if not stream_obj or not stream_obj.data:
                return None
            
            return stream_obj.data
            
        except Exception as e:
            return None
    
    def get_activity_streams(
        self, 
        db: Session, 
        activity_id: int, 
        keys: List[str], 
        resolution: models.Resolution = models.Resolution.HIGH
    ) -> List[Dict[str, Any]]:
        """
        获取活动的流数据
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            keys: 请求的流数据类型列表
            resolution: 数据分辨率
            
        Returns:
            List: 流数据数组，每个元素包含 type, data, series_type, original_size, resolution
        """
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
                    "series_type": "none",
                    "original_size": original_size,
                    "resolution": actual_resolution.value
                })
        
        return result
    
    def get_available_streams(self, db: Session, activity_id: int) -> Dict[str, Any]:
        """
        获取活动可用的流数据类型
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            
        Returns:
            Dict: 包含状态和可用流类型的信息
        """
        # 检查活动是否存在
        activity = db.query(models.TbActivity).filter(models.TbActivity.id == activity_id).first()
        if not activity:
            return {
                "status": "not_found",
                "message": f"活动 {activity_id} 不存在",
                "available_streams": [],
                "total_streams": 0
            }
        
        # 检查是否有upload_fit_url
        if not activity.upload_fit_url:
            return {
                "status": "no_file",
                "message": f"活动 {activity_id} 没有关联的FIT文件",
                "available_streams": [],
                "total_streams": 0
            }
        
        # 获取或解析流数据
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return {
                "status": "parse_error",
                "message": f"活动 {activity_id} 的FIT文件解析失败",
                "available_streams": [],
                "total_streams": 0
            }
        
        # 获取可用的流类型
        available_streams = stream_data.get_available_streams()
        
        return {
            "status": "success",
            "message": "获取成功",
            "available_streams": available_streams,
            "total_streams": len(available_streams)
        }
    
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
        activity = db.query(models.TbActivity).filter(models.TbActivity.id == activity_id).first()
        if not activity:
            return None
        
        stream_data = self._get_or_parse_stream_data(db, activity)
        if not stream_data:
            return None
        
        return stream_data.get_summary_stats(stream_type)
    
    def _get_or_parse_stream_data(self, db: Session, activity: models.TbActivity) -> Optional[models.StreamData]:
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
        
        # 从URL下载FIT文件
        if not activity.upload_fit_url:
            return None
        
        try:
            # 下载FIT文件
            response = requests.get(activity.upload_fit_url, timeout=30)
            response.raise_for_status()
            file_data = response.content
            
            # 获取运动员信息用于w_balance计算
            athlete_info = None
            # 从tb_athlete表获取运动员信息
            try:
                # 首先检查活动是否有 athlete_id
                if hasattr(activity, 'athlete_id') and activity.athlete_id is not None:
                    # 通过 athlete_id 查找对应的运动员
                    athlete = db.query(models.TbAthlete).filter(models.TbAthlete.id == activity.athlete_id).first()
                    
                    if athlete is not None and athlete.ftp is not None and athlete.w_balance is not None:
                        athlete_info = {
                            'ftp': athlete.ftp,
                            'wj': athlete.w_balance  # 假设w_balance字段存储的是wj值
                        }
                    else:
                        print(f"运动员信息不完整: athlete_id={activity.athlete_id}, ftp={getattr(athlete, 'ftp', None) if athlete else None}, w_balance={getattr(athlete, 'w_balance', None) if athlete else None}")
                else:
                    print(f"活动 {activity.id} 的athlete_id为空")
                
            except Exception as e:
                print(f"获取运动员信息时出错: {str(e)}")
                return None

        
            # ! 这里有问题
            # 解析FIT文件
            stream_data = self.fit_parser.parse_fit_file(file_data, athlete_info)
            
            # 缓存结果
            self._stream_cache[cache_key] = stream_data
            
            return stream_data
            
        except Exception as e:
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