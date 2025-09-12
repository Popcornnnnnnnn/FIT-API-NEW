"""
Activities模块的路由

包含活动相关的API端点。
"""


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
import requests
import logging
from ..utils import get_db
from .schemas import ZoneRequest, ZoneResponse, ZoneData, DistributionBucket, ZoneType, OverallResponse, PowerResponse, HeartrateResponse, CadenceResponse, SpeedResponse, AltitudeResponse, TemperatureResponse, BestPowerResponse, TrainingEffectResponse, MultiStreamRequest, MultiStreamResponse, StreamDataItem, AllActivityDataResponse
from .crud import get_activity_overall_info, get_activity_power_info, get_activity_heartrate_info, get_activity_cadence_info, get_activity_speed_info, get_activity_altitude_info, get_activity_temperature_info, get_activity_best_power_info, get_activity_training_effect_info, get_activity_power_zones, get_activity_heartrate_zones
from .zone_analyzer import ZoneAnalyzer
from .strava_analyzer import StravaAnalyzer
from ..streams.models import Resolution
from ..streams.crud import stream_crud
from .data_manager import activity_data_manager
from ..config import is_cache_enabled
from ..clients.strava_client import StravaClient, StravaApiError
logger = logging.getLogger(__name__)
import json

def _is_cache_enabled():
    """检查缓存是否启用（兼容原有函数名）"""
    return is_cache_enabled()

router = APIRouter(prefix="/activities", tags=["活动"])

@router.get("/{activity_id}/zones", response_model=ZoneResponse)
async def get_activity_zones(
    activity_id: int,
    key: ZoneType = Query(..., description="区间类型：power（功率）或heartrate（心率）"),
    db: Session = Depends(get_db)
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
        elif key == ZoneType.HEARTRATE or key == ZoneType.HEART_RATE:
            hr_data = stream_data.get('heart_rate', [])
            distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(hr_data, athlete.max_heartrate)
            zone_type = "heartrate"       
        zone_data = ZoneData(
            distribution_buckets=distribution_buckets,
            type=zone_type
        )   
        return ZoneResponse(zones=[zone_data])
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/overall", response_model=OverallResponse)
async def get_activity_overall(
    activity_id: int,
    db: Session = Depends(get_db)
) -> OverallResponse:
    try:
        overall_info = get_activity_overall_info(db, activity_id)
        if not overall_info:
            raise HTTPException(status_code=404, detail="活动信息不存在或无法解析")
        return OverallResponse(**overall_info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/power", response_model=PowerResponse)
async def get_activity_power(
    activity_id: int,
    db: Session = Depends(get_db)
) -> PowerResponse:
    try:
        power_info = get_activity_power_info(db, activity_id)
        if not power_info:
            raise HTTPException(status_code=404, detail="活动功率信息不存在或无法解析")
        return PowerResponse(**power_info)     
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/heartrate", response_model=HeartrateResponse)
async def get_activity_heartrate(
    activity_id: int,
    db: Session = Depends(get_db)
) -> HeartrateResponse:
    try:
        heartrate_info = get_activity_heartrate_info(db, activity_id)
        if not heartrate_info:
            raise HTTPException(status_code=404, detail="活动心率信息不存在或无法解析")
        return HeartrateResponse(**heartrate_info)      
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/cadence", response_model=CadenceResponse)
async def get_activity_cadence(
    activity_id: int,
    db: Session = Depends(get_db)
) -> CadenceResponse:
    try:
        cadence_info = get_activity_cadence_info(db, activity_id)
        if not cadence_info:
            raise HTTPException(status_code=404, detail="活动踏频信息不存在或无法解析")
        return CadenceResponse(**cadence_info)       
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/speed", response_model=SpeedResponse)
async def get_activity_speed(
    activity_id: int,
    db: Session = Depends(get_db)
) -> SpeedResponse:
    try:
        speed_info = get_activity_speed_info(db, activity_id)
        if not speed_info:
            raise HTTPException(status_code=404, detail="活动速度信息不存在或无法解析")
        return SpeedResponse(**speed_info)     
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/altitude", response_model=AltitudeResponse)
async def get_activity_altitude(
    activity_id: int,
    db: Session = Depends(get_db)
) -> AltitudeResponse:
    try:
        altitude_info = get_activity_altitude_info(db, activity_id)
        if not altitude_info:
            raise HTTPException(status_code=404, detail="活动海拔信息不存在或无法解析")
        return AltitudeResponse(**altitude_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 

@router.get("/{activity_id}/temp", response_model=TemperatureResponse)
async def get_activity_temperature(
    activity_id: int,
    db: Session = Depends(get_db)
) -> TemperatureResponse:
    try:
        temperature_info = get_activity_temperature_info(db, activity_id)
        if not temperature_info:
            raise HTTPException(status_code=404, detail="活动温度信息不存在或无法解析")
        return TemperatureResponse(**temperature_info)   
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 

@router.get("/{activity_id}/best_power", response_model=BestPowerResponse)
async def get_activity_best_power(
    activity_id: int,
    db: Session = Depends(get_db)
) -> BestPowerResponse:
    try:
        best_power_info = get_activity_best_power_info(db, activity_id)
        if not best_power_info:
            raise HTTPException(status_code=404, detail="活动最佳功率信息不存在或无法解析")
        return BestPowerResponse(**best_power_info) 
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/training_effect", response_model=TrainingEffectResponse)
async def get_activity_training_effect(
    activity_id: int,
    db: Session = Depends(get_db)
) -> TrainingEffectResponse:
    try:
        training_effect_info = get_activity_training_effect_info(db, activity_id)
        if not training_effect_info:
            raise HTTPException(status_code=404, detail="活动训练效果信息不存在或无法解析")
        return TrainingEffectResponse(**training_effect_info)     
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.post("/{activity_id}/multi-streams", response_model=MultiStreamResponse)
async def get_activity_multi_streams(
    activity_id: int,
    request: MultiStreamRequest,
    db: Session = Depends(get_db)
):
    try:
        # 验证分辨率参数
        try:
            resolution = Resolution(request.resolution)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的分辨率参数，必须是 low、medium 或 high")
        
        
        # 使用全局数据管理器获取流数据
        streams_data = activity_data_manager.get_activity_streams(db, activity_id, request.keys, resolution)
        
        # 构建响应数据
        response_data = []
        
        # 为每个请求的字段创建响应项
        for field in request.keys:
            # 查找对应的流数据
            stream_item = next((item for item in streams_data if item["type"] == field), None)
            
            if stream_item and stream_item["data"]:
                # 字段存在且有数据
                response_data.append(StreamDataItem(
                    type=field,
                    data=stream_item["data"]
                ))
            else:
                # 字段不存在或没有数据
                response_data.append(StreamDataItem(
                    type=field,
                    data=None
                ))
        
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
    db: Session = Depends(get_db)
):
    try:
        # 导入缓存管理器
        from .cache_manager import activity_cache_manager
        
        # 生成缓存键 - 包含数据精度和字段信息
        cache_key = activity_cache_manager.generate_cache_key(
            activity_id=activity_id,
            resolution=resolution,
            keys=keys
        )
        
        # 尝试从缓存获取数据
        if _is_cache_enabled():
            cached_data = activity_cache_manager.get_cache(db, activity_id, cache_key)
            if cached_data:
                logger.info(f"[cache-hit] all activity data id={activity_id}")
                return AllActivityDataResponse(**cached_data)
        else:
            logger.info("[cache-disabled] skip cache lookup")
        logger.info(f"[cache-miss] computing all data for activity id={activity_id}")

        # 使用 service 层统一获取数据（Strava 或本地）
        final_response = activity_service.get_all_data(db, activity_id, access_token, keys, resolution)

        # 缓存响应数据
        try:
            if _is_cache_enabled():
                response_dict = final_response.dict() if hasattr(final_response, 'dict') else final_response
                metadata = {
                    "source": "strava_api" if access_token else "local_database",
                    "keys": keys,
                    "resolution": resolution,
                    "data_upsampled": bool(access_token),
                    "api_resolution": None,
                    "moving_time": None,
                }
                activity_cache_manager.set_cache(db, activity_id, cache_key, response_dict, metadata)
                logger.info(f"[cache-set] activity id={activity_id} cached")
        except Exception as e:
            logger.warning(f"[cache-failed] cache set failed for id={activity_id}: {e}")

        return final_response

        # 如果传入了 access_token，调用 Strava API
        if access_token:
            try:
                client = StravaClient(access_token)
                keys_list_all = [
                    'time', 'distance', 'latlng', 'altitude', 'velocity_smooth',
                    'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth'
                ]
                full = client.fetch_full(activity_id, keys=keys_list_all, resolution=None)
                activity_data = full['activity']
                stream_data = full['streams']
                athlete_data = full['athlete']
                api_resolution = full['resolution']
                moving_time = activity_data.get('moving_time', 0)

                # 检查Strava数据有效性
                if (activity_data.get("distance", 0) <= 0 or 
                    activity_data.get("average_speed", 0) <= 0 or 
                    activity_data.get("moving_time", 0) <= 0 or
                    activity_data.get("max_speed", 0) <= 0):
                    logger.warning(f"[invalid-strava] activity_id={activity_id}, returning null response")
                    # 返回全null的响应
                    null_response = AllActivityDataResponse(
                        overall=None,
                        power=None,
                        heartrate=None,
                        cadence=None,
                        speed=None,
                        training_effect=None,
                        altitude=None,
                        temp=None,
                        zones=None,
                        best_powers=None,
                        streams=None
                    )
                    return null_response

                # 处理 keys 参数：如果为空则返回所有字段，否则按逗号分割
                if keys:
                    keys_list = [key.strip() for key in keys.split(',') if key.strip()]
                else:
                    keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']
                
                response_data = StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)
                
                # 缓存响应数据 - 包含补齐后的高精度数据
                if response_data and _is_cache_enabled():
                    response_dict = response_data.dict() if hasattr(response_data, 'dict') else response_data
                    metadata = {
                        "source": "strava_api",
                        "keys": keys,
                        "resolution": resolution,
                        "data_upsampled": True,  # 标记数据已补齐到高精度
                        "api_resolution": api_resolution,  # 记录原始API精度
                        "moving_time": moving_time  # 记录实际运动时长
                    }
                    activity_cache_manager.set_cache(db, activity_id, cache_key, response_dict, metadata)
                    logger.info(f"[cache-set] strava activity id={activity_id} cached")
                elif not _is_cache_enabled():
                    logger.info("[cache-disabled] skip strava cache set")
                
                return response_data
            except StravaApiError as e:
                raise HTTPException(status_code=e.status_code, detail=e.message)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"调用 Strava API 时发生错误: {str(e)}")
        
        # 如果没有传入 access_token，进行本地数据库查询
        # 初始化响应数据
        response_data = {}
        
        # 本地数据库查询整合
        info_funcs = [
            ("overall", get_activity_overall_info, OverallResponse),
            ("power", get_activity_power_info, PowerResponse),
            ("heartrate", get_activity_heartrate_info, HeartrateResponse),
            ("cadence", get_activity_cadence_info, CadenceResponse),
            ("speed", get_activity_speed_info, SpeedResponse),
            ("training_effect", get_activity_training_effect_info, TrainingEffectResponse),
            ("altitude", get_activity_altitude_info, AltitudeResponse),
            ("temp", get_activity_temperature_info, TemperatureResponse),
        ]
        for key, func, resp_cls in info_funcs:
            try:
                info = func(db, activity_id)
                response_data[key] = resp_cls(**info) if info else None
            except Exception:
                response_data[key] = None

        # 区间分析（功率区间和心率区间）
        try:
            zones_data = []
            try:
                power_zones = get_activity_power_zones(db, activity_id)
                if power_zones:
                    zones_data.append(ZoneData(**power_zones))
            except Exception:
                pass
            try:
                heartrate_zones = get_activity_heartrate_zones(db, activity_id)
                if heartrate_zones:
                    zones_data.append(ZoneData(**heartrate_zones))
            except Exception:
                pass
            response_data["zones"] = zones_data if zones_data else None
        except Exception:
            response_data["zones"] = None

        # 最佳功率
        try:
            best_power_info = get_activity_best_power_info(db, activity_id)
            response_data["best_powers"] = best_power_info["best_powers"] if best_power_info else None
        except Exception:
            response_data["best_powers"] = None
        
        # 获取流数据 - 使用全局数据管理器
        try:
            # 获取可用的流数据类型
            available_result = stream_crud.get_available_streams(db, activity_id)
            if available_result["status"] == "success":
                available_streams = available_result["available_streams"]

                # 移除 left_right_balance 流
                available_streams = [s for s in available_streams if s != "left_right_balance" and s != "position_lat" and s != "position_long"]

                # 设置分辨率
                resolution_enum = Resolution.HIGH
                if resolution == "low":
                    resolution_enum = Resolution.LOW
                elif resolution == "medium":
                    resolution_enum = Resolution.MEDIUM

                # print(available_streams)
                # 使用全局数据管理器获取流数据
                streams_data = activity_data_manager.get_activity_streams(db, activity_id, available_streams, resolution_enum)

                # 字段重命名（仅对返回的部分）
                if streams_data:
                    for stream in streams_data:
                        if stream["type"] == "temperature":
                            stream["type"] = "temp"
                        if stream["type"] == "heart_rate":
                            stream["type"] = "heartrate"
                        if stream["type"] == "power":
                            stream["type"] = "watts"
                        if stream["type"] == "timestamp":
                            stream["type"] = "time"

                response_data["streams"] = streams_data
            else:
                response_data["streams"] = None
        except Exception as e:
            logger.error(f"get streams error: {str(e)}")
            response_data["streams"] = None
        
        # 构建响应
        final_response = AllActivityDataResponse(**response_data)
        
        # 缓存响应数据 - 本地数据库查询结果
        if _is_cache_enabled():
            try:
                response_dict = final_response.dict() if hasattr(final_response, 'dict') else final_response
                metadata = {
                    "source": "local_database",
                    "keys": keys,
                    "resolution": resolution,
                    "data_upsampled": False,  # 本地数据不需要补齐
                    "api_resolution": None,  # 本地数据没有API精度
                    "moving_time": None  # 本地数据没有运动时长信息
                }
                activity_cache_manager.set_cache(db, activity_id, cache_key, response_dict, metadata)
                logger.info(f"[cache-set] local activity id={activity_id} cached")
            except Exception as e:
                logger.warning(f"[cache-failed] local cache set failed for id={activity_id}: {e}")
        else:
            logger.info("[cache-disabled] skip local cache set")
        
        return final_response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

# 添加缓存管理接口
@router.delete("/cache/{activity_id}")
async def clear_activity_cache(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """清除指定活动的缓存数据"""
    try:
        from .cache_manager import activity_cache_manager
        success = activity_cache_manager.invalidate_cache(db, activity_id)
        if success:
            return {"message": f"活动 {activity_id} 的缓存已清除"}
        else:
            raise HTTPException(status_code=500, detail="清除缓存失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")

@router.delete("/cache")
async def clear_all_cache(
    db: Session = Depends(get_db)
):
    """清除所有活动的缓存数据"""
    try:
        from .cache_manager import activity_cache_manager
        from ..db.models import TbActivityCache
        
        # 批量清除所有缓存
        deleted_count = db.query(TbActivityCache).delete()
        db.commit()
        
        return {
            "message": f"批量清除缓存成功",
            "data": {
                "deleted_count": deleted_count,
                "status": "success"
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")

@router.get("/cache/stats")
async def get_cache_stats(
    db: Session = Depends(get_db)
):
    """获取缓存统计信息"""
    try:
        from .cache_manager import activity_cache_manager
        # 查询缓存统计信息
        from sqlalchemy import func
        from ..db.models import TbActivityCache
        
        total_cache = db.query(func.count(TbActivityCache.id)).scalar()
        active_cache = db.query(func.count(TbActivityCache.id)).filter(TbActivityCache.is_active == 1).scalar()
        
        # 由于缓存永久有效，expired_cache 始终为 0
        expired_cache = 0
        
        # 获取缓存来源统计
        strava_cache = db.query(func.count(TbActivityCache.id)).filter(
            and_(
                TbActivityCache.is_active == 1,
                TbActivityCache.cache_metadata.like('%"source": "strava_api"%')
            )
        ).scalar()
        
        local_cache = db.query(func.count(TbActivityCache.id)).filter(
            and_(
                TbActivityCache.is_active == 1,
                TbActivityCache.cache_metadata.like('%"source": "local_database"%')
            )
        ).scalar()
        
        stats = {
            "total_cache": total_cache,
            "active_cache": active_cache,
            "expired_cache": expired_cache,
            "strava_api_cache": strava_cache,
            "local_database_cache": local_cache
        }
        
        return {
            "message": "获取缓存统计信息成功",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计信息时发生错误: {str(e)}")

@router.post("/cache/toggle")
async def toggle_cache_status(
    enable: bool = Query(..., description="是否启用缓存：true为启用，false为禁用"),
    db: Session = Depends(get_db)
):
    """启用或禁用缓存功能"""
    try:
        import os
        cache_config_file = ".cache_config"
        
        if enable:
            # 启用缓存
            with open(cache_config_file, 'w') as f:
                f.write("enabled=true")
            os.environ['CACHE_ENABLED'] = 'true'
            status = "启用"
        else:
            # 禁用缓存
            with open(cache_config_file, 'w') as f:
                f.write("enabled=false")
            os.environ['CACHE_ENABLED'] = 'false'
            status = "禁用"
        
        return {
            "message": f"缓存功能已{status}",
            "data": {
                "cache_enabled": enable,
                "status": "success",
                "method": "environment_variable"
            }
        }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换缓存状态时发生错误: {str(e)}")

@router.get("/cache/status")
async def get_cache_status(
    db: Session = Depends(get_db)
):
    """获取当前缓存功能状态"""
    try:
        cache_enabled = _is_cache_enabled()
        
        return {
            "message": "获取缓存状态成功",
            "data": {
                "cache_enabled": cache_enabled,
                "status": "enabled" if cache_enabled else "disabled"
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存状态时发生错误: {str(e)}")

