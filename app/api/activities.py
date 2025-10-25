"""
Activities API routes (moved from app/activities/router.py)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
import logging
import os
from time import perf_counter

from ..utils import get_db
from ..schemas.activities import AllActivityDataResponse, IntervalsResponse, SimplifiedIntervalsResponse
from ..config import is_cache_enabled

logger = logging.getLogger(__name__)


def _is_cache_enabled():
    return is_cache_enabled()


router = APIRouter(prefix="/activities", tags=["活动"])

# 用来测试接口性能，log输出
def log_perf_timeline(
    tag: str,
    activity_id: int,
    marks: List[Tuple[str, float]],
    extra: Optional[str] = None,
) -> None:
    if not marks or len(marks) < 2:
        return
    segments = []
    prev = marks[0][1]
    for label, ts in marks[1:]:
        segments.append(f"{label}={(ts - prev) * 1000:.1f}ms")
        prev = ts
    total = (marks[-1][1] - marks[0][1]) * 1000
    suffix = f" {extra}" if extra else ""
    logger.info(
        "[perf][%s] activity_id=%s total=%.1fms %s%s",
        tag,
        activity_id,
        total,
        " | ".join(segments),
        suffix,
    )

@router.get("/{activity_id}/all", response_model=AllActivityDataResponse)
async def get_activity_all_data(
    activity_id: int,
    access_token: Optional[str] = Query(None, description="Strava API访问令牌"),
    keys: Optional[str] = Query(None, description="需要返回的流数据字段，用逗号分隔，如：time,distance,watts,heartrate。如果为空则返回所有字段"),
    resolution: Optional[str] = Query("high", description="数据分辨率：low, medium, high"),
    db: Session = Depends(get_db),
):
    perf_enabled = bool(access_token)
    perf_marks: List[Tuple[str, float]] = []
    if perf_enabled:
        perf_marks.append(("start", perf_counter()))
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
        # if perf_enabled:
        #     perf_marks.append(("service_call", perf_counter()))
        result = activity_service.get_all_data(db, activity_id, access_token, keys, resolution)
        # if perf_enabled:
        #     perf_marks.append(("service_done", perf_counter()))

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
        if perf_enabled:
            # perf_marks.append(("response", perf_counter()))
            log_perf_timeline("activities.all.strava", activity_id, perf_marks, extra="success")
            print()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/intervals", response_model=IntervalsResponse)
async def get_activity_intervals(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """获取活动的区间识别数据
    
    从 `/data/intervals/{activity_id}.json` 文件中读取预先生成的 intervals 数据。
    该数据在调用 `/activities/{activity_id}/all` 接口时自动生成并保存。
    
    Args:
        activity_id: 活动ID
        
    Returns:
        IntervalsResponse: 区间识别结果
        
    Raises:
        HTTPException: 404 - 未找到intervals数据文件
        HTTPException: 500 - 读取或解析文件时发生错误
    """
    try:
        from ..infrastructure.intervals_manager import load_intervals
        
        intervals_data = load_intervals(activity_id)
        
        if not intervals_data:
            raise HTTPException(
                status_code=404, 
                detail=f"未找到活动 {activity_id} 的区间数据，请先调用 /activities/{activity_id}/all 接口生成数据"
            )
        
        return IntervalsResponse(**intervals_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[intervals][read-error] activity_id=%s", activity_id)
        raise HTTPException(status_code=500, detail=f"读取区间数据时发生错误: {str(e)}")


@router.get("/{activity_id}/intervals/simple", response_model=SimplifiedIntervalsResponse)
async def get_activity_intervals_simple(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """获取活动的简化区间识别数据（仅用于画图）
    
    返回简化的区间数据，只包含画图所需的基本信息，数值保留两位小数。
    
    Args:
        activity_id: 活动ID
        
    Returns:
        SimplifiedIntervalsResponse: 简化的区间识别结果
        
    Raises:
        HTTPException: 404 - 未找到intervals数据文件
        HTTPException: 500 - 读取或解析文件时发生错误
    """
    try:
        from ..infrastructure.intervals_manager import load_intervals
        
        intervals_data = load_intervals(activity_id)
        
        if not intervals_data:
            raise HTTPException(
                status_code=404, 
                detail=f"未找到活动 {activity_id} 的区间数据，请先调用 /activities/{activity_id}/all 接口生成数据"
            )
        
        # 转换为简化格式
        simplified_intervals = []
        for item in intervals_data.get('items', []):
            simplified_intervals.append({
                'start': item['start'],
                'end': item['end'],
                'duration': item['duration'],
                'classification': item['classification'],
                'avg_power': round(item['average_power'], 2),
                'power_ratio': round(item['power_ratio'], 2)
            })
        
        return SimplifiedIntervalsResponse(
            duration=intervals_data['duration'],
            ftp=round(intervals_data['ftp'], 2),
            intervals=simplified_intervals
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[intervals-simple][read-error] activity_id=%s", activity_id)
        raise HTTPException(status_code=500, detail=f"读取简化区间数据时发生错误: {str(e)}")


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
