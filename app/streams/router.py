"""
本文件定义了数据流相关的API路由。

包含以下端点：
1. GET /activities/{id}/streams - 获取活动的流数据
2. GET /activities/{id}/streams/available - 获取可用的流数据类型
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from ..utils import get_db
from . import schemas, models
from .crud import stream_crud

router = APIRouter(prefix="/activities", tags=["streams"])

@router.get("/{activity_id}/streams", response_model=List[schemas.StreamResponse])
def get_activity_streams(
    activity_id: int,
    keys: List[str] = Query(..., description="请求的流数据类型列表（不包括distance和time）"),
    resolution: models.Resolution = Query(models.Resolution.HIGH, description="数据分辨率"),
    series_type: models.SeriesType = Query(models.SeriesType.NONE, description="采样方式，可选：distance、time、none")
):
    """
    获取活动的流数据
    
    Args:
        activity_id: 活动ID
        keys: 请求的流数据类型列表，支持：distance, altitude, cadence, heart_rate, speed, latitude, longitude, power, temperature
        resolution: 数据分辨率 (low, medium, high)
        
    Returns:
        List[StreamResponse]: 流数据列表
    """
    # 校验keys
    for key in keys:
        if key in ["distance", "time"]:
            raise HTTPException(status_code=400, detail="keys参数不能包含distance或time")
    db = next(get_db())
    try:
        streams = stream_crud.get_activity_streams(db, activity_id, keys, resolution, series_type)
        
        if not streams:
            raise HTTPException(
                status_code=404, 
                detail=f"活动 {activity_id} 未找到或没有可用的流数据"
            )
        
        return streams
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取流数据时发生错误: {str(e)}"
        )
    finally:
        db.close()

@router.get("/{activity_id}/streams/available")
def get_available_streams(activity_id: int):
    """
    获取活动可用的流数据类型
    
    Args:
        activity_id: 活动ID
        
    Returns:
        Dict: 可用的流类型列表
    """
    db = next(get_db())
    try:
        available_streams = stream_crud.get_available_streams(db, activity_id)
        
        if not available_streams:
            raise HTTPException(
                status_code=404, 
                detail=f"活动 {activity_id} 未找到或没有可用的流数据"
            )
        
        return {
            "activity_id": activity_id,
            "available_streams": available_streams,
            "total_streams": len(available_streams)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取可用流数据类型时发生错误: {str(e)}"
        )
    finally:
        db.close() 