"""Intervals 文件管理器

负责将 intervals 数据持久化到本地文件系统，以及从文件读取。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# intervals 数据存储目录
INTERVALS_DIR = Path("data/intervals")


def ensure_intervals_dir() -> None:
    """确保 intervals 目录存在"""
    try:
        INTERVALS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("[intervals-manager][mkdir-error] %s", e)


def save_intervals(activity_id: int, intervals_data: Dict[str, Any]) -> bool:
    """保存 intervals 数据到文件
    
    Args:
        activity_id: 活动ID
        intervals_data: intervals 数据字典
        
    Returns:
        是否保存成功
    """
    try:
        ensure_intervals_dir()
        file_path = INTERVALS_DIR / f"{activity_id}.json"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(intervals_data, f, ensure_ascii=False, indent=2)
        
        # logger.info("[intervals-manager][save] activity_id=%s path=%s", activity_id, file_path)
        return True
    except Exception as e:
        logger.exception("[intervals-manager][save-error] activity_id=%s err=%s", activity_id, e)
        return False


def load_intervals(activity_id: int) -> Optional[Dict[str, Any]]:
    """从文件加载 intervals 数据
    
    Args:
        activity_id: 活动ID
        
    Returns:
        intervals 数据字典，如果文件不存在或读取失败则返回 None
    """
    try:
        file_path = INTERVALS_DIR / f"{activity_id}.json"
        
        if not file_path.exists():
            logger.debug("[intervals-manager][load] file not found for activity_id=%s", activity_id)
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info("[intervals-manager][load] activity_id=%s path=%s", activity_id, file_path)
        return data
    except Exception as e:
        logger.exception("[intervals-manager][load-error] activity_id=%s err=%s", activity_id, e)
        return None


def delete_intervals(activity_id: int) -> bool:
    """删除指定活动的 intervals 文件
    
    Args:
        activity_id: 活动ID
        
    Returns:
        是否删除成功
    """
    try:
        file_path = INTERVALS_DIR / f"{activity_id}.json"
        
        if not file_path.exists():
            logger.debug("[intervals-manager][delete] file not found for activity_id=%s", activity_id)
            return True
        
        file_path.unlink()
        logger.info("[intervals-manager][delete] activity_id=%s path=%s", activity_id, file_path)
        return True
    except Exception as e:
        logger.exception("[intervals-manager][delete-error] activity_id=%s err=%s", activity_id, e)
        return False

