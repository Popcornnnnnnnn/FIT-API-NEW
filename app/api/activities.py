"""
Activities API routes (moved from app/activities/router.py)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging
import os

from ..utils import get_db
from ..schemas.activities import AllActivityDataResponse
from ..config import is_cache_enabled

logger = logging.getLogger(__name__)


def _is_cache_enabled():
    return is_cache_enabled()


router = APIRouter(prefix="/activities", tags=["活动"])


 




@router.get("/{activity_id}/all", response_model=AllActivityDataResponse)
async def get_activity_all_data(
    activity_id: int,
    access_token: Optional[str] = Query(None, description="Strava API访问令牌"),
    keys: Optional[str] = Query(None, description="需要返回的流数据字段，用逗号分隔，如：time,distance,watts,heartrate。如果为空则返回所有字段"),
    resolution: Optional[str] = Query("high", description="数据分辨率：low, medium, high"),
    db: Session = Depends(get_db),
):
    try:
        from ..infrastructure.cache_manager import activity_cache_manager
        cache_key = activity_cache_manager.generate_cache_key(
            activity_id=activity_id,
            resolution=resolution,
            keys=keys,
        )
        if _is_cache_enabled():
            cached = activity_cache_manager.get_cache(db, activity_id, cache_key)
            if cached:
                logger.info(f"[cache-hit] all activity data id={activity_id}")
                return AllActivityDataResponse(**cached)
        else:
            logger.info("[cache-disabled] skip cache lookup")

        from ..services.activity_service import activity_service
        result = activity_service.get_all_data(db, activity_id, access_token, keys, resolution)

        if _is_cache_enabled():
            try:
                metadata = {
                    "source": "strava_api" if access_token else "local_database",
                    "keys": keys,
                    "resolution": resolution,
                    "data_upsampled": bool(access_token),
                }
                payload = result.model_dump() if hasattr(result, 'model_dump') else result
                activity_cache_manager.set_cache(db, activity_id, cache_key, payload, metadata)
                logger.info(f"[cache-set] activity id={activity_id}")
            except Exception as ce:
                logger.warning(f"[cache-failed] id={activity_id}: {ce}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.delete("/cache/{activity_id}")
async def clear_activity_cache(activity_id: int, db: Session = Depends(get_db)):
    try:
        from ..infrastructure.cache_manager import activity_cache_manager
        success = activity_cache_manager.invalidate_cache(db, activity_id)
        if success:
            return {"message": f"活动 {activity_id} 的缓存已清除"}
        else:
            raise HTTPException(status_code=500, detail="清除缓存失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")


@router.delete("/cache")
async def clear_all_cache(db: Session = Depends(get_db)):
    try:
        from ..db.models import TbActivityCache
        deleted_count = db.query(TbActivityCache).delete()
        db.commit()
        return {"message": "批量清除缓存成功", "data": {"deleted_count": deleted_count, "status": "success"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")


@router.get("/cache/status")
async def get_cache_status(db: Session = Depends(get_db)):
    try:
        cache_enabled = _is_cache_enabled()
        return {"message": "获取缓存状态成功", "data": {"cache_enabled": cache_enabled, "status": "enabled" if cache_enabled else "disabled"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存状态时发生错误: {str(e)}")


@router.post("/cache/toggle")
async def toggle_cache(enable: bool = Query(..., description="true 开启，false 关闭")):
    try:
        os.environ["CACHE_ENABLED"] = "true" if enable else "false"
        try:
            with open('.cache_config', 'w') as f:
                f.write(f"enabled={'true' if enable else 'false'}")
        except Exception as fe:
            logger.warning(f"[cache-toggle] failed to persist .cache_config: {fe}")
        return {
            "message": f"缓存已{'开启' if enable else '关闭'}",
            "data": {"cache_enabled": enable, "status": "enabled" if enable else "disabled"}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换缓存开关失败: {str(e)}")
