"""
历史遗留的活动相关接口（从 app/api/activities.py 中拆分）

说明：
- 为了与现有接口在代码层解耦，但保持原有功能与路径不变；
- 将单项获取的接口集中在此文件中统一维护。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from ...utils import get_db
from ...schemas.activities import (
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
)
from ...core.analytics import zones as ZoneAnalyzer
from ...streams.models import Resolution
from ...infrastructure.data_manager import activity_data_manager


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/activities", tags=["活动-历史"])



@router.get("/{activity_id}/zones", response_model=ZoneResponse)
async def get_activity_zones(
    activity_id: int,
    key: ZoneType = Query(..., description="区间类型：power（功率）或heartrate（心率）"),
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> ZoneResponse:
    try:
        from ...infrastructure.cache_manager import activity_cache_manager
        
        # 如果使用缓存，从缓存中读取 zones 数据
        if not force_recalculate:
            zones_list = activity_cache_manager.get_cached_metric(db, activity_id, "zones")
            if zones_list is not None and isinstance(zones_list, list):
                # zones_list 是 List[ZoneData] 格式，需要根据 key 过滤
                # 处理 key 的多种可能值
                if key == ZoneType.POWER:
                    target_type = "power"
                else:  # HEARTRATE 或 HEART_RATE
                    target_type = "heartrate"
                
                # 从缓存中找到对应类型的 zone
                matched_zone = None
                for zone in zones_list:
                    if not isinstance(zone, dict):
                        continue
                    zone_type = zone.get('type', '')
                    # 匹配 power 或 heartrate（兼容 heart_rate）
                    if zone_type == target_type or (target_type == "heartrate" and zone_type in ("heartrate", "heart_rate")):
                        matched_zone = zone
                        break
                
                if matched_zone:
                    return ZoneResponse(zones=[ZoneData(**matched_zone)])
            
            # 缓存不存在
            if not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
        
        # 强制重新计算：从缓存中的 streams 数据重新计算 zones
        streams_list = activity_cache_manager.get_cached_metric(db, activity_id, "streams")
        
        if not streams_list or not isinstance(streams_list, list):
            raise HTTPException(
                status_code=404,
                detail=f"活动 {activity_id} 缓存中没有流数据，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
            )
        
        _, athlete = activity_data_manager.get_athlete_info(db, activity_id)
        
        if key == ZoneType.POWER:
            # 从 streams 中查找 power 数据（缓存中可能是 "watts" 或 "power"）
            stream_item = next((s for s in streams_list if s.get('type') in ('watts', 'power')), None)
            if not stream_item or not stream_item.get('data'):
                raise HTTPException(status_code=400, detail="活动功率数据不存在")
            
            power_data = stream_item.get('data', [])
            ftp = int(athlete.ftp)
            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
            zone_type = "power"
            
        elif key in (ZoneType.HEARTRATE, ZoneType.HEART_RATE):
            # 从 streams 中查找 heartrate 数据
            stream_item = next((s for s in streams_list if s.get('type') == 'heartrate'), None)
            if not stream_item or not stream_item.get('data'):
                raise HTTPException(status_code=400, detail="活动心率数据不存在")
            
            hr_data = stream_item.get('data', [])
            valid_hr_count = len([h for h in hr_data if h is not None and h > 0]) if isinstance(hr_data, list) else 0
            
            if valid_hr_count == 0:
                raise HTTPException(status_code=400, detail="活动心率数据为空或无效")
            
            # 若启用阈值心率且阈值存在且>0，则按 LTHR 分区（返回7个区间）；否则按最大心率分区（返回5个区间）
            try:
                use_threshold = int(getattr(athlete, 'is_threshold_active', 0) or 0) == 1
            except Exception:
                use_threshold = False
            lthr = None
            if use_threshold and getattr(athlete, 'threshold_heartrate', None):
                try:
                    lthr = int(athlete.threshold_heartrate)
                    if lthr <= 0:
                        lthr = None
                except Exception:
                    lthr = None
            max_hr = None
            if getattr(athlete, 'max_heartrate', None):
                try:
                    max_hr = int(athlete.max_heartrate)
                except Exception:
                    max_hr = None
            
            if use_threshold and lthr and lthr > 0:
                # 使用阈值心率分区，返回7个区间
                distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones_lthr(hr_data, lthr, max_hr)
            elif max_hr and max_hr > 0:
                # 使用最大心率分区，返回5个区间
                distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(hr_data, max_hr)
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="无法计算心率区间：需要配置最大心率(max_heartrate)或阈值心率(threshold_heartrate且is_threshold_active=1)"
                )
            
            if not distribution_buckets:
                raise HTTPException(status_code=400, detail="心率区间计算结果为空，请检查心率数据和配置")
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
async def get_activity_overall(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> OverallResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_overall(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动信息不存在或无法解析")
        return OverallResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/power", response_model=PowerResponse)
async def get_activity_power(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> PowerResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_power(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动功率信息不存在或无法解析")
        return PowerResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/heartrate", response_model=HeartrateResponse)
async def get_activity_heartrate(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> HeartrateResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_heartrate(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动心率信息不存在或无法解析")
        return HeartrateResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/cadence", response_model=CadenceResponse)
async def get_activity_cadence(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> CadenceResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_cadence(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动踏频信息不存在或无法解析")
        return CadenceResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/speed", response_model=SpeedResponse)
async def get_activity_speed(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> SpeedResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_speed(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动速度信息不存在或无法解析")
        return SpeedResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/altitude", response_model=AltitudeResponse)
async def get_activity_altitude(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> AltitudeResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_altitude(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动海拔信息不存在或无法解析")
        return AltitudeResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/training_effect", response_model=TrainingEffectResponse)
async def get_activity_training_effect(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> TrainingEffectResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        info = activity_service.get_training_effect(db, activity_id, use_cache=use_cache)
        
        if not info:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
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


@router.get("/{activity_id}/temp", response_model=TemperatureResponse)
async def get_activity_temperature(
    activity_id: int,
    force_recalculate: bool = Query(False, description="是否强制重新计算，true=重新计算，false=优先使用缓存"),
    db: Session = Depends(get_db),
) -> TemperatureResponse:
    try:
        from ...services.activity_service import activity_service
        from ...infrastructure.cache_manager import activity_cache_manager
        
        use_cache = not force_recalculate
        data = activity_service.get_temperature(db, activity_id, use_cache=use_cache)
        
        if not data:
            if use_cache and not activity_cache_manager.has_cache(db, activity_id):
                raise HTTPException(
                    status_code=404,
                    detail=f"活动 {activity_id} 尚未缓存，请先调用 /activities/{activity_id}/all 接口生成缓存数据"
                )
            raise HTTPException(status_code=404, detail="活动温度信息不存在或无法解析")
        return TemperatureResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get("/{activity_id}/best_power", response_model=BestPowerResponse)
async def get_activity_best_power(activity_id: int, db: Session = Depends(get_db)) -> BestPowerResponse:
    try:
        from ...services.activity_crud import get_activity_best_power_info
        info = get_activity_best_power_info(db, activity_id)
        if not info:
            raise HTTPException(status_code=404, detail="活动最佳功率信息不存在或无法解析")
        return BestPowerResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")
