"""
活动数据缓存管理器

负责管理活动数据的缓存，包括：
1. 缓存数据的存储和检索
2. 缓存过期管理
3. 文件存储管理
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..db.models import TbActivityCache
import logging
from ..config import CACHE_DIR

logger = logging.getLogger(__name__)


class ActivityCacheManager:
    def __init__(self, storage_base_path: str = CACHE_DIR):
        self.storage_base_path = storage_base_path
        os.makedirs(storage_base_path, exist_ok=True)

    def generate_cache_key(self, activity_id: int, **kwargs) -> str:
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['resolution', 'keys'] and v is not None}
        param_str = "&".join([f"{k}={v}" for k, v in sorted(filtered_kwargs.items())])
        cache_input = f"activity_{activity_id}_{param_str}"
        return hashlib.md5(cache_input.encode()).hexdigest()

    def get_cache(self, db: Session, activity_id: int, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            cache_record = db.query(TbActivityCache).filter(
                and_(
                    TbActivityCache.activity_id == activity_id,
                    TbActivityCache.cache_key == cache_key,
                    TbActivityCache.is_active == 1
                )
            ).first()
            if not cache_record:
                return None
            if not os.path.exists(cache_record.file_path):
                logger.warning(f"缓存文件不存在: {cache_record.file_path}")
                return None
            with open(cache_record.file_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            logger.info(f"缓存命中: activity_id={activity_id}, cache_key={cache_key}")
            return cached_data
        except Exception as e:
            logger.error(f"获取缓存失败: activity_id={activity_id}, error: {e}")
            return None

    def set_cache(self, db: Session, activity_id: int, cache_key: str, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            file_name = f"{activity_id}_{cache_key}.json"
            file_path = os.path.join(self.storage_base_path, file_name)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            file_size = os.path.getsize(file_path)
            expires_at = None
            cache_record = db.query(TbActivityCache).filter(
                TbActivityCache.activity_id == activity_id
            ).first()
            if cache_record:
                cache_record.cache_key = cache_key
                cache_record.file_path = file_path
                cache_record.file_size = file_size
                cache_record.updated_at = datetime.now()
                cache_record.expires_at = expires_at
                cache_record.is_active = 1
                cache_record.cache_metadata = json.dumps(metadata) if metadata else None
            else:
                cache_record = TbActivityCache(
                    activity_id=activity_id,
                    cache_key=cache_key,
                    file_path=file_path,
                    file_size=file_size,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    expires_at=expires_at,
                    cache_metadata=json.dumps(metadata) if metadata else None
                )
                db.add(cache_record)
            db.commit()
            logger.info(f"缓存设置成功: activity_id={activity_id}, cache_key={cache_key}, file_path={file_path}")
            return True
        except Exception as e:
            logger.error(f"设置缓存失败: activity_id={activity_id}, error: {e}")
            db.rollback()
            return False

    def invalidate_cache(self, db: Session, activity_id: int) -> bool:
        try:
            cache_records = db.query(TbActivityCache).filter(
                TbActivityCache.activity_id == activity_id
            ).all()
            for record in cache_records:
                if os.path.exists(record.file_path):
                    try:
                        os.remove(record.file_path)
                    except OSError:
                        pass
                record.is_active = 0
                record.updated_at = datetime.now()
            db.commit()
            logger.info(f"缓存失效成功: activity_id={activity_id}")
            return True
        except Exception as e:
            logger.error(f"使缓存失效失败: activity_id={activity_id}, error: {e}")
            db.rollback()
            return False

    def get_cached_metric(self, db: Session, activity_id: int, metric_name: str) -> Optional[Dict[str, Any]]:
        """
        从 /all 的整体缓存中提取单项数据
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            metric_name: 指标名称（overall, power, heartrate, cadence, speed, altitude, temp, training_effect）
            
        Returns:
            单项数据字典，如果缓存不存在或指标不存在则返回 None
        """
        try:
            cache_record = db.query(TbActivityCache).filter(
                and_(
                    TbActivityCache.activity_id == activity_id,
                    TbActivityCache.is_active == 1
                )
            ).order_by(TbActivityCache.updated_at.desc()).first()
            
            if not cache_record:
                return None
            
            if not os.path.exists(cache_record.file_path):
                logger.warning(f"[metric-cache][file-missing] activity_id={activity_id}, file={cache_record.file_path}")
                return None
            
            with open(cache_record.file_path, 'r', encoding='utf-8') as f:
                all_cache_data = json.load(f)
            
            metric_data = all_cache_data.get(metric_name)
            if metric_data is None:
                return None
            
            logger.debug(f"[metric-cache][hit] activity_id={activity_id}, metric={metric_name}")
            return metric_data
            
        except Exception as e:
            logger.error(f"[metric-cache][error] activity_id={activity_id}, metric={metric_name}, error: {e}")
            return None

    def has_cache(self, db: Session, activity_id: int) -> bool:
        """
        检查活动是否有缓存数据
        
        Returns:
            True 如果存在有效缓存，False otherwise
        """
        try:
            cache_record = db.query(TbActivityCache).filter(
                and_(
                    TbActivityCache.activity_id == activity_id,
                    TbActivityCache.is_active == 1
                )
            ).first()
            if not cache_record:
                return False
            return os.path.exists(cache_record.file_path)
        except Exception:
            return False


activity_cache_manager = ActivityCacheManager()

