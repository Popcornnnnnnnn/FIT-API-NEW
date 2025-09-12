"""
Activities API routes (moved from app/activities/router.py)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ..utils import get_db
from ..schemas.activities import (
    ZoneType,
    ZoneResponse,
    ZoneData,
    OverallResponse,
    PowerResponse,
    HeartrateResponse,
    CadenceResponse,
    SpeedResponse,
    AltitudeResponse,
    TemperatureResponse,
    BestPowerResponse,
    TrainingEffectResponse,
    MultiStreamRequest,
    MultiStreamResponse,
    StreamDataItem,
    AllActivityDataResponse,
)
from ..core.analytics import zones as ZoneAnalyzer
from ..streams.models import Resolution
from ..infrastructure.data_manager import activity_data_manager
from ..config import is_cache_enabled

logger = logging.getLogger(__name__)


def _is_cache_enabled():
    return is_cache_enabled()


router = APIRouter(prefix="/activities", tags=["活动"])


@router.get("/{activity_id}/zones", response_model=ZoneResponse)
async def get_activity_zones(
    activity_id: int,
    key: ZoneType = Query(..., description="区间类型：power（功率）或heartrate（心率）"),
    db: Session = Depends(get_db),
) -> ZoneResponse:
    try:
        _, athlete = activity_data_manager.get_athlete_info(db, activity_id)
        stream_data = activity_data_manager.get_activity_stream_data(db, activity_id)
        if key == ZoneType.POWER:
            ftp = int(athlete.ftp)
            power_data = stream_data.get('power', [])
            if not power_data:
                raise HTTPException(status_code=400, detail="活动功率数据不存在")
            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
            zone_type = "power"
        elif key in (ZoneType.HEARTRATE, ZoneType.HEART_RATE):
            hr_data = stream_data.get('heart_rate', [])
            distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(hr_data, athlete.max_heartrate)
            zone_type = "heartrate"
        else:
            distribution_buckets = []
            zone_type = key.value
        return ZoneResponse(zones=[ZoneData(distribution_buckets=distribution_buckets, type=zone_type)])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/overall", response_model=OverallResponse)
async def get_activity_overall(activity_id: int, db: Session = Depends(get_db)) -> OverallResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_overall(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动信息不存在或无法解析")
        return OverallResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/power", response_model=PowerResponse)
async def get_activity_power(activity_id: int, db: Session = Depends(get_db)) -> PowerResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_power(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动功率信息不存在或无法解析")
        return PowerResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/heartrate", response_model=HeartrateResponse)
async def get_activity_heartrate(activity_id: int, db: Session = Depends(get_db)) -> HeartrateResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_heartrate(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动心率信息不存在或无法解析")
        return HeartrateResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/cadence", response_model=CadenceResponse)
async def get_activity_cadence(activity_id: int, db: Session = Depends(get_db)) -> CadenceResponse:
    try:
        raise HTTPException(status_code=404, detail="活动踏频信息不存在或无法解析")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/speed", response_model=SpeedResponse)
async def get_activity_speed(activity_id: int, db: Session = Depends(get_db)) -> SpeedResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_speed(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动速度信息不存在或无法解析")
        return SpeedResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/altitude", response_model=AltitudeResponse)
async def get_activity_altitude(activity_id: int, db: Session = Depends(get_db)) -> AltitudeResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_altitude(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动海拔信息不存在或无法解析")
        return AltitudeResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/temp", response_model=TemperatureResponse)
async def get_activity_temperature(activity_id: int, db: Session = Depends(get_db)) -> TemperatureResponse:
    try:
        from ..services.activity_service import activity_service
        data = activity_service.get_temperature(db, activity_id)
        if not data:
            raise HTTPException(status_code=404, detail="活动温度信息不存在或无法解析")
        return TemperatureResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/best_power", response_model=BestPowerResponse)
async def get_activity_best_power(activity_id: int, db: Session = Depends(get_db)) -> BestPowerResponse:
    try:
        from ..services.activity_crud import get_activity_best_power_info
        info = get_activity_best_power_info(db, activity_id)
        if not info:
            raise HTTPException(status_code=404, detail="活动最佳功率信息不存在或无法解析")
        return BestPowerResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/training_effect", response_model=TrainingEffectResponse)
async def get_activity_training_effect(activity_id: int, db: Session = Depends(get_db)) -> TrainingEffectResponse:
    try:
        from ..services.activity_service import activity_service
        info = activity_service.get_training_effect(db, activity_id)
        if not info:
            raise HTTPException(status_code=404, detail="活动训练效果信息不存在或无法解析")
        return TrainingEffectResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.post("/{activity_id}/multi-streams", response_model=MultiStreamResponse)
async def get_activity_multi_streams(activity_id: int, request: MultiStreamRequest, db: Session = Depends(get_db)):
    try:
        try:
            resolution = Resolution(request.resolution)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的分辨率参数，必须是 low、medium 或 high")
        streams_data = activity_data_manager.get_activity_streams(db, activity_id, request.keys, resolution)
        response_data = []
        for field in request.keys:
            stream_item = next((item for item in streams_data if item["type"] == field), None)
            if stream_item and stream_item["data"]:
                response_data.append(StreamDataItem(type=field, data=stream_item["data"]))
            else:
                response_data.append(StreamDataItem(type=field, data=None))
        return MultiStreamResponse(response_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


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
                payload = result.dict() if hasattr(result, 'dict') else result
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
