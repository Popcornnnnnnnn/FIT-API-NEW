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
    def __init__(self, cache_ttl: int = 3600, max_cache_size: int = 100):
        self._stream_cache = {}
        self._session_cache = {}
        self._athlete_cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = cache_ttl
        self._max_cache_size = max_cache_size
        self._lock = threading.Lock()
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        def cleanup_task():
            while True:
                time.sleep(300)
                self._cleanup_expired_cache()
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()

    def _cleanup_expired_cache(self):
        current_time = time.time()
        with self._lock:
            expired_keys = [key for key, timestamp in self._cache_timestamps.items() if current_time - timestamp > self._cache_ttl]
            for key in expired_keys:
                self._stream_cache.pop(key, None)
                self._session_cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            total_cache_size = len(self._stream_cache) + len(self._session_cache)
            if total_cache_size > self._max_cache_size:
                sorted_keys = sorted(self._cache_timestamps.items(), key=lambda x: x[1])
                keys_to_remove = [key for key, _ in sorted_keys[:total_cache_size - self._max_cache_size]]
                for key in keys_to_remove:
                    self._stream_cache.pop(key, None)
                    self._session_cache.pop(key, None)
                    self._cache_timestamps.pop(key, None)

    def get_activity_streams(self, db: Session, activity_id: int, keys: List[str], resolution: Resolution) -> List[Dict[str, Any]]:
        cache_key = f"{activity_id}_{resolution.value}_{','.join(sorted(keys))}"
        with self._lock:
            current_time = time.time()
            if cache_key in self._stream_cache and cache_key in self._cache_timestamps and current_time - self._cache_timestamps[cache_key] <= self._cache_ttl:
                return self._stream_cache[cache_key]
            self._stream_cache[cache_key] = stream_crud.get_activity_streams(db, activity_id, keys, resolution)
            self._cache_timestamps[cache_key] = current_time
        return self._stream_cache[cache_key]

    def get_activity_stream_data(self, db: Session, activity_id: int) -> Dict[str, Any]:
        cache_key = f"{activity_id}_raw"
        with self._lock:
            current_time = time.time()
            if cache_key in self._stream_cache and cache_key in self._cache_timestamps and current_time - self._cache_timestamps[cache_key] <= self._cache_ttl:
                return self._stream_cache[cache_key]
            available_result = stream_crud.get_available_streams(db, activity_id)
            if available_result["status"] == "success":
                available_streams = available_result["available_streams"]
                streams_data = stream_crud.get_activity_streams(db, activity_id, available_streams, Resolution.HIGH)
                stream_dict = {stream["type"]: stream["data"] for stream in streams_data}
                self._stream_cache[cache_key] = stream_dict
            else:
                self._stream_cache[cache_key] = {}
            self._cache_timestamps[cache_key] = current_time
        return self._stream_cache[cache_key]

    def get_athlete_info(self, db: Session, activity_id: int) -> tuple:
        with self._lock:
            current_time = time.time()
            if (activity_id in self._athlete_cache and f"athlete_{activity_id}" in self._cache_timestamps and current_time - self._cache_timestamps[f"athlete_{activity_id}"] <= self._cache_ttl):
                return self._athlete_cache[activity_id]
            from ..services.activity_crud import get_activity_athlete
            self._athlete_cache[activity_id] = get_activity_athlete(db, activity_id)
            self._cache_timestamps[f"athlete_{activity_id}"] = current_time
        return self._athlete_cache[activity_id]

    def get_session_data(self, db: Session, activity_id: int, fit_url: str) -> Optional[Dict[str, Any]]:
        cache_key = f"session_{activity_id}"
        with self._lock:
            current_time = time.time()
            if cache_key in self._session_cache and cache_key in self._cache_timestamps and current_time - self._cache_timestamps[cache_key] <= self._cache_ttl:
                return self._session_cache[cache_key]
            from ..services.activity_crud import get_session_data
            self._session_cache[cache_key] = get_session_data(fit_url)
            self._cache_timestamps[cache_key] = current_time
        return self._session_cache[cache_key]

    def clear_cache(self, activity_id: Optional[int] = None):
        with self._lock:
            if activity_id is None:
                self._stream_cache.clear()
                self._session_cache.clear()
                self._athlete_cache.clear()
                self._cache_timestamps.clear()
            else:
                keys_to_remove = [key for key in list(self._stream_cache.keys()) if key.startswith(f"{activity_id}_")]
                for key in keys_to_remove:
                    self._stream_cache.pop(key, None)
                    self._cache_timestamps.pop(key, None)
                session_key = f"session_{activity_id}"
                self._session_cache.pop(session_key, None)
                self._cache_timestamps.pop(session_key, None)
                self._athlete_cache.pop(activity_id, None)
                self._cache_timestamps.pop(f"athlete_{activity_id}", None)

    def get_cache_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "stream_cache_size": len(self._stream_cache),
                "session_cache_size": len(self._session_cache),
                "athlete_cache_size": len(self._athlete_cache),
                "total_cache_entries": len(self._cache_timestamps),
                "max_cache_size": self._max_cache_size,
                "cache_ttl": self._cache_ttl,
            }


activity_data_manager = ActivityDataManager()

