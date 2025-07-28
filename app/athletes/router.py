"""
本文件定义了运动员相关的API路由。

提供以下API端点：
1. GET / - 获取运动员列表
2. GET /{athlete_id} - 获取单个运动员信息
3. POST / - 创建新运动员
4. PUT /{athlete_id} - 更新运动员信息
5. POST /{athlete_id}/metrics - 添加运动员指标
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import crud, schemas
from ..utils import get_db

router = APIRouter()

@router.get("/", response_model=list[schemas.Athlete])
def read_athletes(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取运动员列表"""
    return crud.get_athletes(db, skip=skip, limit=limit)

@router.get("/{athlete_id}", response_model=schemas.Athlete)
def read_athlete(athlete_id: int, db: Session = Depends(get_db)):
    """获取单个运动员信息"""
    db_athlete = crud.get_athlete(db, athlete_id=athlete_id)
    if db_athlete is None:
        raise HTTPException(status_code=404, detail="运动员未找到")
    return db_athlete

@router.post("/", response_model=schemas.Athlete)
def create_athlete(athlete: schemas.AthleteCreate, db: Session = Depends(get_db)):
    """创建新运动员"""
    return crud.create_athlete(db, athlete)

@router.put("/{athlete_id}", response_model=schemas.Athlete)
def update_athlete(athlete_id: int, athlete_update: schemas.AthleteUpdate, db: Session = Depends(get_db)):
    """更新运动员信息（FTP、最大心率、体重等）"""
    db_athlete = crud.update_athlete(db, athlete_id, athlete_update)
    if db_athlete is None:
        raise HTTPException(status_code=404, detail="运动员未找到")
    return db_athlete

@router.post("/{athlete_id}/metrics", response_model=schemas.AthleteMetric)
def add_athlete_metric(athlete_id: int, metric: schemas.AthleteMetricCreate, db: Session = Depends(get_db)):
    """添加运动员指标"""
    return crud.create_athlete_metric(db, metric, athlete_id) 