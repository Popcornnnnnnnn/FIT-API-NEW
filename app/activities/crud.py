"""
本文件包含活动相关的数据库操作函数（CRUD操作）。

提供以下功能：
1. 活动的增删改查操作
2. 文件上传和存储
3. 数据库事务管理
4. 活动区间分布数据计算
"""

from sqlalchemy.orm import Session
from . import models, schemas
from ..streams.crud import stream_crud
from typing import List, Dict, Any
import base64
import uuid
import math

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

def get_activities(db: Session, skip: int = 0, limit: int = 100):
    """获取活动列表，支持分页"""
    return db.query(models.Activity).offset(skip).limit(limit).all()

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

def format_time(seconds: int) -> str:
    """将秒数格式化为智能时间格式"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        # 有小时：显示 HH:MM:SS
        return f"{hours}:{minutes:02d}:{secs:02d}"
    elif minutes > 0:
        # 有分钟但没有小时：显示 MM:SS
        return f"{minutes}:{secs:02d}"
    else:
        # 只有秒：显示 Xs
        return f"{secs}s"

def get_activity_zones(db: Session, activity_id: int, zone_type: str) -> schemas.ZoneDistribution:
    """
    获取单个活动的功率或心率区间分布数据
    
    Args:
        db: 数据库会话
        activity_id: 活动ID
        zone_type: 区间类型 ("power" 或 "heart_rate")
        
    Returns:
        ZoneDistribution: 区间分布数据
    """
    # 获取活动信息
    activity = get_activity(db, activity_id)
    if not activity:
        raise ValueError("活动未找到")
    
    # 获取运动员信息
    from ..athletes.models import Athlete
    athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
    if not athlete:
        raise ValueError("运动员未找到")
    
    # 检查必要的参数
    if zone_type == "power" and not athlete.ftp:
        raise ValueError("运动员未设置FTP，无法计算功率区间")
    if zone_type == "heart_rate" and not athlete.max_hr:
        raise ValueError("运动员未设置最大心率，无法计算心率区间")
    
    # 获取活动的流数据
    stream_data = stream_crud._get_or_parse_stream_data(db, activity)
    if not stream_data:
        return schemas.ZoneDistribution(
            distribution_buckets=[],
            type=zone_type
        )
    
    # 获取数据
    if zone_type == "power":
        data = stream_data.power
    else:  # heart_rate
        data = stream_data.heart_rate
    
    if not data:
        return schemas.ZoneDistribution(
            distribution_buckets=[],
            type=zone_type
        )
    
    # 收集有效数据点
    all_data = []
    total_time = 0
    
    for value in data:
        if value is not None and value > 0:
            all_data.append(value)
            total_time += 1  # 每个有效数据点代表1秒
    
    if not all_data:
        return schemas.ZoneDistribution(
            distribution_buckets=[],
            type=zone_type
        )
    
    # 定义区间
    # 注意：你可以修改下面的区间名称来自定义显示
    if zone_type == "power":
        # 功率区间（基于FTP的7个区间）
        ftp = athlete.ftp
        zones = [
            (0, 0.55 * ftp, "动态恢复"),      # Zone 1: 0-55% FTP
            (0.55 * ftp, 0.75 * ftp, "耐力"),  # Zone 2: 55-75% FTP
            (0.75 * ftp, 0.90 * ftp, "节奏"),  # Zone 3: 75-90% FTP
            (0.90 * ftp, 1.05 * ftp, "阈值"),  # Zone 4: 90-105% FTP
            (1.05 * ftp, 1.20 * ftp, "最大摄氧量"),  # Zone 5: 105-120% FTP
            (1.20 * ftp, 1.50 * ftp, "厌氧"),  # Zone 6: 120-150% FTP
            (1.50 * ftp, float('inf'), "神经肌肉")  # Zone 7: >150% FTP
        ]
    else:  # heart_rate
        # 心率区间（基于最大心率的5个区间）
        max_hr = athlete.max_hr
        zones = [
            (0.5 * max_hr, 0.6 * max_hr, "耐力"),  # Zone 1: 50-60% Max HR
            (0.6 * max_hr, 0.7 * max_hr, "中等"),  # Zone 2: 60-70% Max HR
            (0.7 * max_hr, 0.8 * max_hr, "节奏"),  # Zone 3: 70-80% Max HR
            (0.8 * max_hr, 0.9 * max_hr, "阈值"),  # Zone 4: 80-90% Max HR
            (0.9 * max_hr, max_hr, "厌氧")         # Zone 5: 90-100% Max HR
        ]
    
    # 计算每个区间的时间
    buckets = []
    for i, (min_val, max_val, zone_name) in enumerate(zones):
        zone_time = 0
        for value in all_data:
            if min_val <= value < max_val:
                zone_time += 1
        
        if zone_time > 0:
            percentage = (zone_time / total_time) * 100
            buckets.append(schemas.ZoneBucket(
                min=min_val,
                max=max_val if max_val != float('inf') else -1,  # 使用-1表示无穷大
                time=zone_time,
                string=format_time(zone_time),
                percentage=f"{percentage:.1f}%",
                name=zone_name  # 使用默认区间名称
            ))
    
    return schemas.ZoneDistribution(
        distribution_buckets=buckets,
        type=zone_type
    ) 