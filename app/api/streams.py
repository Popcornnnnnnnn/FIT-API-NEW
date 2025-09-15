"""
数据流 API 路由（从 app/streams/router.py 迁移到此，以统一到 api 目录）

包含：
- GET /activities/{activity_id}/available：获取活动可用的流数据类型；
- GET /activities/{activity_id}/streams：按 key 获取指定活动的某一类流数据。

说明：
- 路由仅做参数校验与调用 stream_crud；
- 返回格式尽量与前端期望保持一致，若 key 不可用，返回空列表。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..utils import get_db
from ..streams import schemas, models
from ..streams.crud import stream_crud


router = APIRouter(prefix="/activities", tags=["streams"])


@router.get("/{activity_id}/available")
def get_available_streams(activity_id: int, db: Session = Depends(get_db)):
    try:
        result = stream_crud.get_available_streams(db, activity_id)
        return {
            "activity_id": activity_id,
            "available_streams": result["available_streams"],
            "total_streams": result["total_streams"],
            "message": result["message"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取可用流数据类型时发生错误: {str(e)}",
        )


@router.get("/{activity_id}/streams")
def get_activity_streams(
    activity_id: int,
    key: str = Query(...),
    resolution: models.Resolution = Query(models.Resolution.HIGH),
    db: Session = Depends(get_db),
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
            detail=f"获取流数据时发生错误: {str(e)}",
        )

