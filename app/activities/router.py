"""
本文件定义了活动相关的API路由。

提供以下API端点：
1. GET / - 获取活动列表
2. GET /{activity_id} - 获取单个活动详情
3. GET /{activity_id}/summary - 获取活动摘要信息
4. GET /{activity_id}/advanced - 获取高级指标
5. GET /{activity_id}/zones - 获取活动的功率或心率区间分布数据
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from . import schemas, crud
from ..utils import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.Activity])
def read_activities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取活动列表"""
    return crud.get_activities(db, skip=skip, limit=limit)

@router.get("/{activity_id}", response_model=schemas.Activity)
def read_activity(activity_id: int, db: Session = Depends(get_db)):
    """获取单个活动详情"""
    db_activity = crud.get_activity(db, activity_id=activity_id)
    if db_activity is None:
        raise HTTPException(status_code=404, detail="活动未找到")
    return db_activity

@router.get("/{activity_id}/summary", response_model=schemas.ActivitySummary)
def get_activity_summary(activity_id: int, db: Session = Depends(get_db)):
    """获取活动摘要信息"""
    # TODO: 实现活动摘要查询
    return {
        "activity_id": activity_id,
        "distance_km": 42.2,
        "duration_min": 180,
        "avg_power": 200,
        "avg_hr": 150,
        "max_power": 300,
        "max_hr": 180,
        "activity_type": "cycling"
    }

@router.get("/{activity_id}/advanced")
def get_advanced_metrics(activity_id: int, db: Session = Depends(get_db)):
    """获取高级指标（NP、IF、TSS等）"""
    # TODO: 实现高级指标计算
    return {
        "activity_id": activity_id,
        "NP": 220,
        "IF": 0.85,
        "TSS": 120,
        "hr_zones": {"zone1": 30, "zone2": 50, "zone3": 20}
    }

@router.get("/{activity_id}/zones", response_model=schemas.ZoneDistribution)
def get_activity_zones(
    activity_id: int, 
    type: str = Query(..., description="区间类型：power 或 heart_rate"),
    db: Session = Depends(get_db)
):
    """
    获取单个活动的功率或心率区间分布数据
    
    - **activity_id**: 活动ID
    - **type**: 区间类型，支持 "power" 或 "heart_rate"
    
    返回区间分布数据，包含每个区间的时间分布和百分比
    """
    if type not in ["power", "heart_rate"]:
        raise HTTPException(status_code=400, detail="区间类型必须是 'power' 或 'heart_rate'")
    
    try:
        return crud.get_activity_zones(db, activity_id, type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) 