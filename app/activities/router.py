"""
Activities模块的路由

包含活动相关的API端点。
"""


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
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
import json

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
        # 如果传入了 access_token，调用 Strava API
        if access_token:
            try:
                # 调用 Strava API，使用 activity_id 作为 external_id
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                activity_response = requests.get(
                    f"https://www.strava.com/api/v3/activities/{activity_id}", 
                    headers=headers, 
                    timeout=10)
                stream_response = requests.get(
                    f"https://www.strava.com/api/v3/activities/{activity_id}/streams?keys=time,distance,latlng,altitude,velocity_smooth,heartrate,cadence,watts,temp,moving,grade_smooth&key_by_type=true&resolution={resolution}", 
                    headers=headers, 
                    timeout=10)
                athlete_response = requests.get( 
                    "https://www.strava.com/api/v3/athlete",
                    headers=headers,
                    timeout=10
                )
                if athlete_response.status_code != 200:
                    raise HTTPException(
                        status_code=athlete_response.status_code,
                        detail=f"Strava API 运动员信息获取失败: {athlete_response.text}"
                    )
                if activity_response.status_code != 200:
                    raise HTTPException(
                        status_code=activity_response.status_code,
                        detail=f"Strava API 活动信息获取失败: {activity_response.text}"
                    )
                if stream_response.status_code != 200:
                    raise HTTPException(
                        status_code=stream_response.status_code,
                        detail=f"Strava API 流数据获取失败: {stream_response.text}"
                    )
                activity_data = activity_response.json()
                stream_data = stream_response.json()
                athlete_data = athlete_response.json()
                # print(athlete_data["ftp"])

                # 处理 keys 参数：如果为空则返回所有字段，否则按逗号分割
                if keys:
                    keys_list = [key.strip() for key in keys.split(',') if key.strip()]
                else:
                    # 如果 keys 为空，返回所有可用的字段
                    keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam'] # ! 去掉 lating、moving、grade_smooth，将 velocity_smooth 改成 speed
                return StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)
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
            print(f"获取流数据时发生错误: {str(e)}")
            response_data["streams"] = None
        
        # 构建响应
        return AllActivityDataResponse(**response_data)
        
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
        activity_data_manager.clear_cache(activity_id)
        return {"message": f"活动 {activity_id} 的缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")

@router.delete("/cache")
async def clear_all_cache(
    db: Session = Depends(get_db)
):
    """清除所有活动的缓存数据"""
    try:
        activity_data_manager.clear_cache()
        return {"message": "所有缓存已清除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存时发生错误: {str(e)}")

@router.get("/cache/stats")
async def get_cache_stats(
    db: Session = Depends(get_db)
):
    """获取缓存统计信息"""
    try:
        stats = activity_data_manager.get_cache_stats()
        return {
            "message": "获取缓存统计信息成功",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取缓存统计信息时发生错误: {str(e)}")


