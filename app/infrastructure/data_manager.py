"""
活动数据管理器模块

用于全局管理数据流获取，避免重复下载和解析FIT文件。
"""

import time
import threading
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging
from ..streams.models import Resolution
from ..streams.crud import stream_crud


logger = logging.getLogger(__name__)


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
            cache_pre_hit = activity_id in stream_crud._parsed_cache
            stream_obj = stream_crud.load_stream_data(db, activity_id, use_cache=True)
            if stream_obj:
                available_streams = stream_obj.get_available_streams()
                stream_dict: Dict[str, Any] = {}
                total_points = 0
                for key in available_streams:
                    data = getattr(stream_obj, key, None)
                    if data:
                        # 避免重复复制大数组，若本身是 list 则直接复用
                        values = data if isinstance(data, list) else list(data)
                        stream_dict[key] = values
                        total_points += len(values)
                self._stream_cache[cache_key] = stream_dict
            else:
                self._stream_cache[cache_key] = {}
            self._cache_timestamps[cache_key] = current_time
        logger.info(
            "[data_manager.stream_data.detail] activity_id=%s cache_pre_hit=%s streams=%s total_points=%s\n",
            activity_id,
            cache_pre_hit,
            len(self._stream_cache[cache_key]) if stream_obj else 0,
            sum(len(v) for v in self._stream_cache[cache_key].values()) if stream_obj else 0,
        )
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
            session_summary = stream_crud.load_session_data(db, activity_id, fit_url)
            if session_summary is None:
                session_summary = get_session_data(fit_url)
            self._session_cache[cache_key] = session_summary
            self._cache_timestamps[cache_key] = current_time
        logger.info(
            "[data_manager.session_data.detail] activity_id=%s has_summary=%s\n",
            activity_id,
            session_summary is not None,
        )
        return self._session_cache[cache_key]

    def clear_cache(self, activity_id: Optional[int] = None):
        with self._lock:
            if activity_id is None:
                self._stream_cache.clear()
                self._session_cache.clear()
                self._athlete_cache.clear()
                self._cache_timestamps.clear()
                stream_crud._parsed_cache.clear()
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
                stream_crud._parsed_cache.pop(activity_id, None)

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
