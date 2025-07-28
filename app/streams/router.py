"""
本文件定义了数据流相关的API路由。

提供以下API端点：
1. GET /{activity_id} - 获取活动流数据
2. POST /batch - 批量获取多种流数据
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from . import schemas
from ..utils import get_db

router = APIRouter()

@router.get("/{activity_id}", response_model=schemas.StreamResponse)
def get_activity_stream(
    activity_id: int, 
    stream_type: str = Query("power", description="流数据类型"),
    sample_rate: int = Query(1, description="采样率"),
    db: Session = Depends(get_db)
):
    """获取活动流数据"""
    # TODO: 实现流数据查询和处理
    mock_data = []
    for i in range(0, 100, sample_rate):
        mock_data.append({
            "timestamp": i,
            "power": 200 + i % 10,
            "heart_rate": 150 + i % 5
        })
    
    return {
        "activity_id": activity_id,
        "stream_type": stream_type,
        "data": mock_data,
        "sample_rate": sample_rate
    }

@router.post("/batch", response_model=List[schemas.StreamResponse])
def get_multiple_streams(
    request: schemas.StreamRequest,
    db: Session = Depends(get_db)
):
    """批量获取多种流数据"""
    # TODO: 实现批量流数据查询
    responses = []
    for stream_type in request.stream_types:
        mock_data = []
        for i in range(0, 50, request.sample_rate):
            mock_data.append({
                "timestamp": i,
                "power": 200 + i % 10 if stream_type == "power" else None,
                "heart_rate": 150 + i % 5 if stream_type == "heart_rate" else None
            })
        
        responses.append({
            "activity_id": request.activity_id,
            "stream_type": stream_type,
            "data": mock_data,
            "sample_rate": request.sample_rate
        })
    
    return responses 