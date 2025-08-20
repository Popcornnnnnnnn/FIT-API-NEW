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
from .models import TbActivityCache
from ..db_base import Base
import logging

logger = logging.getLogger(__name__)

class ActivityCacheManager:
    """活动数据缓存管理器"""
    
    def __init__(self, storage_base_path: str = "/data/activity_cache"):
        """
        初始化缓存管理器
        
        Args:
            storage_base_path: 服务器存储基础路径
        """
        self.storage_base_path = storage_base_path
        
        # 确保存储目录存在
        os.makedirs(storage_base_path, exist_ok=True)
    
    def generate_cache_key(self, activity_id: int, **kwargs) -> str:
        """
        生成缓存键
        
        Args:
            activity_id: 活动ID
            **kwargs: 其他影响缓存的因素（如keys, resolution等）
        
        Returns:
            缓存键字符串
        """
        # 只考虑 resolution 参数，忽略 access_token
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ['resolution'] and v is not None}
        
        # 将参数排序并组合
        param_str = "&".join([f"{k}={v}" for k, v in sorted(filtered_kwargs.items())])
        cache_input = f"activity_{activity_id}_{param_str}"
        
        # 使用MD5生成固定长度的缓存键
        return hashlib.md5(cache_input.encode()).hexdigest()
    
    def get_cache(self, db: Session, activity_id: int, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存数据
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            cache_key: 缓存键
        
        Returns:
            缓存数据字典，如果不存在或已过期则返回None
        """
        try:
            # 查询缓存记录
            cache_record = db.query(TbActivityCache).filter(
                and_(
                    TbActivityCache.activity_id == activity_id,
                    TbActivityCache.cache_key == cache_key,
                    TbActivityCache.is_active == 1
                )
            ).first()
            
            if not cache_record:
                return None
            
            # 不检查过期时间，缓存永久有效
            
            # 检查文件是否存在
            if not os.path.exists(cache_record.file_path):
                logger.warning(f"缓存文件不存在: {cache_record.file_path}")
                return None
            
            # 读取JSON文件
            try:
                with open(cache_record.file_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                logger.info(f"缓存命中: activity_id={activity_id}, cache_key={cache_key}")
                return cached_data
                
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"读取缓存文件失败: {cache_record.file_path}, error: {e}")
                return None
                
        except Exception as e:
            logger.error(f"获取缓存失败: activity_id={activity_id}, error: {e}")
            return None
    
    def set_cache(self, db: Session, activity_id: int, cache_key: str, data: Dict[str, Any], 
                  metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        设置缓存数据
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
            cache_key: 缓存键
            data: 要缓存的数据
            metadata: 缓存元数据
        
        Returns:
            是否成功设置缓存
        """
        try:
            # 生成文件路径
            file_name = f"{activity_id}_{cache_key}.json"
            file_path = os.path.join(self.storage_base_path, file_name)
            
            # 写入JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 获取文件大小
            file_size = os.path.getsize(file_path)
            
            # 不设置过期时间，缓存永久有效
            expires_at = None
            
            # 更新或插入缓存记录
            cache_record = db.query(TbActivityCache).filter(
                TbActivityCache.activity_id == activity_id
            ).first()
            
            if cache_record:
                # 更新现有记录
                cache_record.cache_key = cache_key
                cache_record.file_path = file_path
                cache_record.file_size = file_size
                cache_record.updated_at = datetime.now()
                cache_record.expires_at = expires_at
                cache_record.cache_metadata = json.dumps(metadata) if metadata else None
            else:
                # 创建新记录
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
        """
        使缓存失效
        
        Args:
            db: 数据库会话
            activity_id: 活动ID
        
        Returns:
            是否成功使缓存失效
        """
        try:
            cache_records = db.query(TbActivityCache).filter(
                TbActivityCache.activity_id == activity_id
            ).all()
            
            for record in cache_records:
                # 删除文件
                if os.path.exists(record.file_path):
                    try:
                        os.remove(record.file_path)
                    except OSError:
                        pass
                
                # 标记为无效
                record.is_active = 0
                record.updated_at = datetime.now()
            
            db.commit()
            logger.info(f"缓存失效成功: activity_id={activity_id}")
            return True
            
        except Exception as e:
            logger.error(f"使缓存失效失败: activity_id={activity_id}, error: {e}")
            db.rollback()
            return False
    


# 全局缓存管理器实例
activity_cache_manager = ActivityCacheManager()
