"""
本文件包含活动相关的数据库操作函数（CRUD操作）。

提供以下功能：
1. 活动的增删改查操作
2. 文件上传和存储
3. 数据库事务管理
"""

from sqlalchemy.orm import Session
from . import models, schemas
import base64
import uuid

def create_activity_from_upload(
    db: Session, 
    file_data: bytes,
    file_name: str,
    athlete_id: int,
    name: str = None,
    description: str = None,
    trainer: bool = False,
    commute: bool = False,
    data_type: str = "fit",
    external_id: str = None
):
    """从上传的文件创建活动记录"""
    
    # 检查是否存在相同的文件名和大小的文件
    file_size = len(file_data)
    existing_activity = db.query(models.Activity).filter(
        models.Activity.athlete_id == athlete_id,
        models.Activity.file_name == file_name,
        models.Activity.file_data.isnot(None)
    ).first()
    
    if existing_activity:
        # 如果找到同名文件，检查文件大小是否相同
        try:
            existing_file_data = base64.b64decode(existing_activity.file_data.encode('utf-8'))
            if len(existing_file_data) == file_size:
                raise ValueError(f"文件 '{file_name}' 已存在且大小相同，不允许重复上传")
        except Exception as e:
            # 如果解码失败，仍然认为可能是重复文件，阻止上传
            raise ValueError(f"文件 '{file_name}' 已存在，不允许重复上传")
    
    # 生成唯一ID字符串
    id_str = str(uuid.uuid4())
    
    # 将文件数据编码为base64字符串存储
    file_data_b64 = base64.b64encode(file_data).decode('utf-8')
    
    # 创建活动记录
    db_activity = models.Activity(
        athlete_id=athlete_id,
        file_data=file_data_b64,
        file_name=file_name,
        name=name or file_name,  # 如果没有提供名称，使用文件名
        description=description,
        trainer=trainer,
        commute=commute,
        data_type=data_type,
        external_id=external_id or id_str,  # 如果没有提供外部ID，使用生成的ID
        status="pending"  # 初始状态为待处理
    )
    
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    
    return db_activity, id_str

def get_activity(db: Session, activity_id: int):
    """根据ID获取活动信息"""
    return db.query(models.Activity).filter(models.Activity.id == activity_id).first()

def get_activities_by_athlete(db: Session, athlete_id: int, skip: int = 0, limit: int = 100):
    """获取指定运动员的活动列表"""
    return db.query(models.Activity).filter(
        models.Activity.athlete_id == athlete_id
    ).offset(skip).limit(limit).all()

def update_activity_status(db: Session, activity_id: int, status: str, error: str = None):
    """更新活动状态"""
    db_activity = db.query(models.Activity).filter(models.Activity.id == activity_id).first()
    if db_activity is None:
        return None
    
    db_activity.status = status
    if error:
        db_activity.error = error
    
    db.commit()
    db.refresh(db_activity)
    return db_activity 