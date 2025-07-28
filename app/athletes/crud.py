"""
本文件包含运动员相关的数据库操作函数（CRUD操作）。

提供以下功能：
1. 运动员的增删改查操作
2. 运动员指标的创建操作
3. 数据库事务管理
"""

from sqlalchemy.orm import Session
from . import models, schemas

def get_athlete(db: Session, athlete_id: int):
    """根据ID获取单个运动员信息"""
    return db.query(models.Athlete).filter(models.Athlete.id == athlete_id).first()

def get_athletes(db: Session, skip: int = 0, limit: int = 100):
    """获取运动员列表，支持分页"""
    return db.query(models.Athlete).offset(skip).limit(limit).all()

def create_athlete(db: Session, athlete: schemas.AthleteCreate):
    """创建新运动员"""
    db_athlete = models.Athlete(
        name=athlete.name,
        ftp=athlete.ftp,
        max_hr=athlete.max_hr,
        weight=athlete.weight
    )
    db.add(db_athlete)
    db.commit()
    db.refresh(db_athlete)
    return db_athlete

def update_athlete(db: Session, athlete_id: int, athlete_update: schemas.AthleteUpdate):
    """更新运动员信息"""
    db_athlete = db.query(models.Athlete).filter(models.Athlete.id == athlete_id).first()
    if db_athlete is None:
        return None
    
    # 只更新提供的字段
    update_data = athlete_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_athlete, field, value)
    
    db.commit()
    db.refresh(db_athlete)
    return db_athlete

def create_athlete_metric(db: Session, metric: schemas.AthleteMetricCreate, athlete_id: int):
    """为运动员创建新的指标记录"""
    db_metric = models.AthleteMetric(**metric.model_dump(), athlete_id=athlete_id)
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric 