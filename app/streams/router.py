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
        
        # 根据状态返回不同的响应
        if result["status"] == "not_found":
            raise HTTPException(
                status_code=404, 
                detail=result["message"]
            )
        elif result["status"] == "no_file":
            raise HTTPException(
                status_code=404, 
                detail=result["message"]
            )
        elif result["status"] == "parse_error":
            raise HTTPException(
                status_code=500, 
                detail=result["message"]
            )
        
        return {
            "activity_id": activity_id,
            "available_streams": result["available_streams"],
            "total_streams": result["total_streams"],
            "message": result["message"]
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
    key: str = Query(..., description="请求的流数据类型"),
    resolution: models.Resolution = Query(
        models.Resolution.HIGH, 
        description="数据分辨率，可选值：low, medium, high"
    ),
    db: Session = Depends(get_db)
):
    """
    获取活动的流数据
    
    Args:
        activity_id: 活动ID
        key: 请求的流数据类型
        resolution: 数据分辨率 (low, medium, high)
        
    Returns:
        List: 流数据数组，每个元素包含 type, data, series_type, original_size, resolution
    """
    try:
        # 首先检查该活动是否有这个stream
        result = stream_crud.get_available_streams(db, activity_id)
        
        # 如果活动不存在或没有文件，直接返回错误
        if result["status"] in ["not_found", "no_file"]:
            raise HTTPException(
                status_code=404, 
                detail=result["message"]
            )
        elif result["status"] == "parse_error":
            raise HTTPException(
                status_code=500, 
                detail=result["message"]
            )
        
        available_streams = result["available_streams"]
        
        if key not in available_streams:
            return []
        
        # 获取流数据，使用 get_activity_streams 方法返回新格式
        streams_data = stream_crud.get_activity_streams(db, activity_id, [key], resolution)
        
        return streams_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"获取流数据时发生错误: {str(e)}"
        ) 