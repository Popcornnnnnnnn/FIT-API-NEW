"""
Activities模块的数据库操作函数

包含活动相关的数据库查询和操作。
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, Tuple, Dict, Any
from ..streams.models import TbActivity, TbAthlete
from ..streams.crud import StreamCRUD
from ..utils import get_db

def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    """
    根据活动ID获取活动和运动员信息
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Tuple[TbActivity, TbAthlete]: 活动和运动员信息，如果不存在则返回None
    """
    # 查询活动信息
    activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
    if not activity:
        return None
    
    # 查询运动员信息
    athlete = db.query(TbAthlete).filter(TbAthlete.id == activity.athlete_id).first()
    if not athlete:
        return None
    
    return activity, athlete

def get_activity_stream_data(db: Session, activity_id: int) -> Optional[Dict[str, Any]]:
    """
    获取活动的流数据
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        
    Returns:
        Dict[str, Any]: 流数据字典，如果不存在则返回None
    """
    try:
        # 查询活动信息
        activity = db.query(TbActivity).filter(TbActivity.id == activity_id).first()
        if not activity:
            return None
        
        # 使用StreamCRUD获取流数据
        stream_crud = StreamCRUD()
        stream_data = stream_crud._get_or_parse_stream_data(db, activity)
        
        if not stream_data:
            return None
        
        # 转换为字典格式
        result = {}
        for field_name in stream_data.model_fields:
            if field_name not in ('timestamp', 'distance', 'elapsed_time'):
                data = getattr(stream_data, field_name)
                if data and any(x is not None and x != 0 for x in data):
                    result[field_name] = data
        
        return result
        
    except Exception as e:
        print(f"获取活动流数据失败: {e}")
        return None 