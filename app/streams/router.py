"""
本文件定义了数据流相关的API路由。

包含以下端点：
1. GET /activities/{activity_id}/available - 获取活动可用的流数据类型
2. GET /activities/{activity_id}/streams - 获取活动的流数据
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..utils import get_db
from . import schemas, models
from .crud import stream_crud

router = APIRouter(prefix="/activities", tags=["streams"])

@router.get("/{activity_id}/available")
def get_available_streams(activity_id: int, db: Session = Depends(get_db)):
    try:
        result = stream_crud.get_available_streams(db, activity_id)
        return {
            "activity_id"      : activity_id,
            "available_streams": result["available_streams"],
            "total_streams"    : result["total_streams"],
            "message"          : result["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取可用流数据类型时发生错误: {str(e)}"
        )

@router.get("/{activity_id}/streams")
def get_activity_streams(
    activity_id: int,
    key: str = Query(...),
    resolution: models.Resolution = Query(models.Resolution.HIGH),
    db: Session = Depends(get_db)
):
    try:
        result = stream_crud.get_available_streams(db, activity_id)
        available_streams = result["available_streams"]
        
        if key not in available_streams:
            return []
        
        return stream_crud.get_activity_streams(db, activity_id, [key], resolution)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取流数据时发生错误: {str(e)}"
        ) 