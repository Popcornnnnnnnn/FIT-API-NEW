"""
活动数据管理器模块

用于全局管理数据流获取，避免重复下载和解析FIT文件。
"""

import time
import threading
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..streams.models import Resolution
from ..streams.crud import stream_crud


class ActivityDataManager:
    """活动数据管理器，用于全局管理数据流获取"""
    
    def __init__(self, cache_ttl: int = 3600, max_cache_size: int = 100):
        """
        初始化数据管理器
        
        Args:
            cache_ttl: 缓存生存时间（秒），默认1小时
            max_cache_size: 最大缓存条目数，默认100个活动
        """
        self._stream_cache = {}  # 缓存已获取的数据流
        self._session_cache = {}  # 缓存session数据
        self._athlete_cache = {}  # 缓存运动员信息
        self._cache_timestamps = {}  # 缓存时间戳
        self._cache_ttl = cache_ttl
        self._max_cache_size = max_cache_size
        self._lock = threading.Lock()  # 线程锁
        
        # 启动定时清理任务
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """启动定时清理任务"""
        def cleanup_task():
            while True:
                time.sleep(300)  # 每5分钟检查一次
                self._cleanup_expired_cache()
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_expired_cache(self):
        """清理过期的缓存"""
        current_time = time.time()
        with self._lock:
            # 清理过期的缓存
            expired_keys = [
                key for key, timestamp in self._cache_timestamps.items()
                if current_time - timestamp > self._cache_ttl
            ]
            for key in expired_keys:
                if key in self._stream_cache:
                    del self._stream_cache[key]
                if key in self._session_cache:
                    del self._session_cache[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
            
            # 如果缓存大小超过限制，删除最旧的条目
            total_cache_size = len(self._stream_cache) + len(self._session_cache)
            if total_cache_size > self._max_cache_size:
                # 按时间戳排序，删除最旧的
                sorted_keys = sorted(
                    self._cache_timestamps.items(),
                    key=lambda x: x[1]
                )
                keys_to_remove = [
                    key for key, _ in sorted_keys[:total_cache_size - self._max_cache_size]
                ]
                for key in keys_to_remove:
                    if key in self._stream_cache:
                        del self._stream_cache[key]
                    if key in self._session_cache:
                        del self._session_cache[key]
                    if key in self._cache_timestamps:
                        del self._cache_timestamps[key]
    
    def get_activity_streams(
        self, 
        db: Session, 
        activity_id: int, 
        keys: List[str], 
        resolution: Resolution
    ) -> List[Dict[str, Any]]:
        """获取活动数据流，如果已缓存则直接返回"""
        cache_key = f"{activity_id}_{resolution.value}_{','.join(sorted(keys))}"
        
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否存在且未过期
            if (cache_key in self._stream_cache and 
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] <= self._cache_ttl):
                print(f"🟢 [缓存命中] 活动{activity_id}的流数据 (keys: {keys})")
                return self._stream_cache[cache_key]
            
            # 首次获取或缓存过期，调用stream_crud
            print(f"🔴 [缓存未命中] 活动{activity_id}的流数据 (keys: {keys}) - 正在下载...")
            self._stream_cache[cache_key] = stream_crud.get_activity_streams(db, activity_id, keys, resolution)
            self._cache_timestamps[cache_key] = current_time
            print(f"✅ [下载完成] 活动{activity_id}的流数据已缓存")
        
        return self._stream_cache[cache_key]
    
    def get_activity_stream_data(
        self, 
        db: Session, 
        activity_id: int
    ) -> Dict[str, Any]:
        """获取活动的原始流数据，用于区间分析等"""
        cache_key = f"{activity_id}_raw"
        
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否存在且未过期
            if (cache_key in self._stream_cache and 
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] <= self._cache_ttl):
                print(f"🟢 [缓存命中] 活动{activity_id}的原始流数据")
                return self._stream_cache[cache_key]
            
            # 获取所有可用的流数据
            print(f"🔴 [缓存未命中] 活动{activity_id}的原始流数据 - 正在下载...")
            available_result = stream_crud.get_available_streams(db, activity_id)
            if available_result["status"] == "success":
                available_streams = available_result["available_streams"]
                streams_data = stream_crud.get_activity_streams(db, activity_id, available_streams, Resolution.HIGH)
                
                # 转换为字典格式
                stream_dict = {}
                for stream in streams_data:
                    stream_dict[stream["type"]] = stream["data"]
                
                self._stream_cache[cache_key] = stream_dict
                self._cache_timestamps[cache_key] = current_time
                print(f"✅ [下载完成] 活动{activity_id}的原始流数据已缓存")
            else:
                self._stream_cache[cache_key] = {}
                self._cache_timestamps[cache_key] = current_time
                print(f"❌ [下载失败] 活动{activity_id}的原始流数据")
        
        return self._stream_cache[cache_key]
    
    def get_athlete_info(
        self, 
        db: Session, 
        activity_id: int
    ) -> tuple:
        """获取运动员信息，如果已缓存则直接返回"""
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否存在且未过期
            if (activity_id in self._athlete_cache and 
                f"athlete_{activity_id}" in self._cache_timestamps and
                current_time - self._cache_timestamps[f"athlete_{activity_id}"] <= self._cache_ttl):
                return self._athlete_cache[activity_id]
            
            # 获取运动员信息（在函数内部导入避免循环导入）
            from .crud import get_activity_athlete
            self._athlete_cache[activity_id] = get_activity_athlete(db, activity_id)
            self._cache_timestamps[f"athlete_{activity_id}"] = current_time
        
        return self._athlete_cache[activity_id]
    
    def get_session_data(
        self, 
        db: Session, 
        activity_id: int,
        fit_url: str
    ) -> Optional[Dict[str, Any]]:
        """获取session数据，如果已缓存则直接返回"""
        cache_key = f"session_{activity_id}"
        
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否存在且未过期
            if (cache_key in self._session_cache and 
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] <= self._cache_ttl):
                print(f"🟢 [缓存命中] 活动{activity_id}的session数据")
                return self._session_cache[cache_key]
            
            # 首次获取或缓存过期，调用get_session_data
            print(f"🔴 [缓存未命中] 活动{activity_id}的session数据 - 正在下载FIT文件...")
            from .crud import get_session_data
            self._session_cache[cache_key] = get_session_data(fit_url)
            self._cache_timestamps[cache_key] = current_time
            print(f"✅ [下载完成] 活动{activity_id}的session数据已缓存")
        
        return self._session_cache[cache_key]
    
    def get_activity_lap_data(
        self, 
        db: Session, 
        activity_id: int,
        fit_url: str
    ) -> Optional[List[Dict[str, Any]]]:
        """获取活动lap数据，如果已缓存则直接返回"""
        cache_key = f"lap_{activity_id}"
        
        with self._lock:
            current_time = time.time()
            
            # 检查缓存是否存在且未过期
            if (cache_key in self._session_cache and 
                cache_key in self._cache_timestamps and
                current_time - self._cache_timestamps[cache_key] <= self._cache_ttl):
                print(f"🟢 [缓存命中] 活动{activity_id}的lap数据")
                return self._session_cache[cache_key]
            
            # 首次获取或缓存过期，调用get_lap_data
            print(f"🔴 [缓存未命中] 活动{activity_id}的lap数据 - 正在下载FIT文件...")
            from .crud import get_lap_data
            self._session_cache[cache_key] = get_lap_data(fit_url)
            self._cache_timestamps[cache_key] = current_time
            print(f"✅ [下载完成] 活动{activity_id}的lap数据已缓存")
        
        return self._session_cache[cache_key]
    
    def update_best_efforts(
        self,
        db: Session,
        activity_id: int
    ) -> Dict[str, Any]:
        """更新运动员最佳成绩记录"""
        try:
            # 获取活动信息
            activity, athlete = self.get_athlete_info(db, activity_id)
            if not activity or not athlete:
                return {
                    "success": False,
                    "new_records": {"power_records": {}, "speed_records": {}},
                    "message": "活动或运动员信息不存在"
                }
            
            # 获取流数据
            stream_data = self.get_activity_stream_data(db, activity_id)
            if not stream_data:
                return {
                    "success": False,
                    "new_records": {"power_records": {}, "speed_records": {}},
                    "message": "活动流数据不存在"
                }
            
            # 获取lap数据
            lap_data = self.get_activity_lap_data(db, activity_id, activity.upload_fit_url)
            
            # 调用最佳成绩更新函数
            from .crud import calculate_and_update_best_efforts
            result = calculate_and_update_best_efforts(
                db, activity_id, athlete.id, stream_data, lap_data
            )
            return result
            
        except Exception as e:
            print(f"❌ [最佳成绩更新失败] 活动{activity_id}: {str(e)}")
            return {
                "success": False,
                "new_records": {"power_records": {}, "speed_records": {}},
                "message": f"最佳成绩更新失败: {str(e)}"
            }
    
    def clear_cache(
        self, 
        activity_id: Optional[int] = None
    ):
        """清除缓存"""
        with self._lock:
            if activity_id is None:
                # 清除所有缓存
                self._stream_cache.clear()
                self._session_cache.clear()
                self._athlete_cache.clear()
                self._cache_timestamps.clear()
            else:
                # 清除特定活动的缓存
                keys_to_remove = [key for key in self._stream_cache.keys() if key.startswith(f"{activity_id}_")]
                for key in keys_to_remove:
                    del self._stream_cache[key]
                    if key in self._cache_timestamps:
                        del self._cache_timestamps[key]
                
                # 清除session缓存
                session_key = f"session_{activity_id}"
                if session_key in self._session_cache:
                    del self._session_cache[session_key]
                if session_key in self._cache_timestamps:
                    del self._cache_timestamps[session_key]
                
                # 清除lap缓存
                lap_key = f"lap_{activity_id}"
                if lap_key in self._session_cache:
                    del self._session_cache[lap_key]
                if lap_key in self._cache_timestamps:
                    del self._cache_timestamps[lap_key]
                
                if activity_id in self._athlete_cache:
                    del self._athlete_cache[activity_id]
                if f"athlete_{activity_id}" in self._cache_timestamps:
                    del self._cache_timestamps[f"athlete_{activity_id}"]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            return {
                "stream_cache_size": len(self._stream_cache),
                "session_cache_size": len(self._session_cache),
                "athlete_cache_size": len(self._athlete_cache),
                "total_cache_entries": len(self._cache_timestamps),
                "max_cache_size": self._max_cache_size,
                "cache_ttl": self._cache_ttl
            }

# 创建全局数据管理器实例
activity_data_manager = ActivityDataManager()
