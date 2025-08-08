"""
Activities模块的路由

包含活动相关的API端点。
"""

from tarfile import data_filter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import requests
import logging
from ..utils import get_db
from .schemas import ZoneRequest, ZoneResponse, ZoneData, DistributionBucket, ZoneType, OverallResponse, PowerResponse, HeartrateResponse, CadenceResponse, SpeedResponse, AltitudeResponse, TemperatureResponse, BestPowerResponse, TrainingEffectResponse, MultiStreamRequest, MultiStreamResponse, StreamDataItem, AllActivityDataResponse
from .crud import get_activity_athlete, get_activity_stream_data, get_activity_overall_info, get_activity_power_info, get_activity_heartrate_info, get_activity_cadence_info, get_activity_speed_info, get_activity_altitude_info, get_activity_temperature_info, get_activity_best_power_info, get_activity_training_effect_info, get_activity_power_zones, get_activity_heartrate_zones
from .zone_analyzer import ZoneAnalyzer
from .strava_analyzer import StravaAnalyzer
from ..streams.models import Resolution
from ..streams.crud import stream_crud
import json

router = APIRouter(prefix="/activities", tags=["活动"])

@router.get("/{activity_id}/zones", response_model=ZoneResponse)
async def get_activity_zones(
    activity_id: int,
    key: ZoneType = Query(..., description="区间类型：power（功率）或heartrate（心率）"),
    db: Session = Depends(get_db)
) -> ZoneResponse:
    try:
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            raise HTTPException(status_code=404, detail="活动或运动员信息不存在") 
        _, athlete = activity_athlete  
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            raise HTTPException(status_code=404, detail="活动流数据不存在")        
    
        if key == ZoneType.POWER:
            ftp = int(athlete.ftp)
            power_data = stream_data.get('power', [])
            if not power_data:
                raise HTTPException(status_code=400, detail="活动功率数据不存在")
            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
            zone_type = "power"      
        elif key == ZoneType.HEARTRATE:
            hr_data = stream_data.get('heartrate', [])
            if not hr_data:
                raise HTTPException(status_code=400, detail="活动心率数据不存在")
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

@router.get("/{activity_id}/multi-streams", response_model=MultiStreamResponse)
async def get_activity_multi_streams(
    activity_id: int,
    request: MultiStreamRequest,
    db: Session = Depends(get_db)
):
    """
    获取活动的多个流数据
    
    接收一个字段数组和分辨率参数，返回指定格式的流数据。
    如果请求的字段不存在，则在data处返回None。
    """
    try:
        # 验证分辨率参数
        try:
            resolution = Resolution(request.resolution)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的分辨率参数，必须是 low、medium 或 high")
        
        
        # 获取流数据
        streams_data = stream_crud.get_activity_streams(db, activity_id, request.keys, resolution)
        
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
    """
    获取活动的所有数据
    
    按照 overall、power、heartrate、cadence、speed、training_effect、altitude、temp、zones、best_powers 的顺序返回所有子字段。
    如果某一个大的字段有缺失就在相应位置返回 None。
    
    参数说明：
    - 如果没有传入 access_token，将 activity_id 作为本地数据库ID进行查询
    - 如果传入了 access_token，将 activity_id 作为 Strava 的 external_id 调用 API
    - keys 参数只有在 access_token 存在且有效时才会被解析：
      * 格式：用逗号分隔的字符串，如：time,distance,watts,heartrate
      * 如果为空，则返回所有可用的流数据字段
      * 支持的字段：
        - 直接使用 Strava API 字段名：distance, altitude, cadence, heartrate, velocity_smooth, latlng, watts, temp, time, moving, grade_smooth 等
        - 特殊字段：
          * latitude/longitude: 从 latlng 中提取的经纬度数据
          * best_power: 最佳功率数据（计算得出）
          * power_hr_ratio: 功率心率比（功率/心率，计算得出）
          * torque: 扭矩数据（功率/踏频，计算得出）
          * spi: 速度功率指数（功率/踏频，计算得出）
          * w_balance: W平衡数据（基于功率的平衡计算）
          * vam: 垂直爬升速度（海拔变化率，计算得出）
    - resolution 参数控制数据分辨率：low, medium, high（默认：high）
    """
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
                    keys_list = ['time', 'distance', 'latlng', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth', 'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']
                
                return StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"调用 Strava API 时发生错误: {str(e)}")
        
        # 如果没有传入 access_token，进行本地数据库查询
        # 初始化响应数据
        response_data = {}
        
        # 获取总体信息
        try:
            overall_info = get_activity_overall_info(db, activity_id)
            if overall_info:
                response_data["overall"] = OverallResponse(**overall_info)
            else:
                response_data["overall"] = None
        except Exception:
            response_data["overall"] = None
        
        # 获取功率信息
        try:
            power_info = get_activity_power_info(db, activity_id)
            if power_info:
                response_data["power"] = PowerResponse(**power_info)
            else:
                response_data["power"] = None
        except Exception:
            response_data["power"] = None
        
        # 获取心率信息
        try:
            heartrate_info = get_activity_heartrate_info(db, activity_id)
            if heartrate_info:
                response_data["heartrate"] = HeartrateResponse(**heartrate_info)
            else:
                response_data["heartrate"] = None
        except Exception:
            response_data["heartrate"] = None
        
        # 获取踏频信息
        try:
            cadence_info = get_activity_cadence_info(db, activity_id)
            if cadence_info:
                response_data["cadence"] = CadenceResponse(**cadence_info)
            else:
                response_data["cadence"] = None
        except Exception:
            response_data["cadence"] = None
        
        # 获取速度信息
        try:
            speed_info = get_activity_speed_info(db, activity_id)
            if speed_info:
                response_data["speed"] = SpeedResponse(**speed_info)
            else:
                response_data["speed"] = None
        except Exception:
            response_data["speed"] = None
        
        # 获取训练效果信息
        try:
            training_effect_info = get_activity_training_effect_info(db, activity_id)
            if training_effect_info:
                response_data["training_effect"] = TrainingEffectResponse(**training_effect_info)
            else:
                response_data["training_effect"] = None
        except Exception:
            response_data["training_effect"] = None
        
        # 获取海拔信息
        try:
            altitude_info = get_activity_altitude_info(db, activity_id)
            if altitude_info:
                response_data["altitude"] = AltitudeResponse(**altitude_info)
            else:
                response_data["altitude"] = None
        except Exception:
            response_data["altitude"] = None
        
        # 获取温度信息
        try:
            temperature_info = get_activity_temperature_info(db, activity_id)
            if temperature_info:
                response_data["temp"] = TemperatureResponse(**temperature_info)
            else:
                response_data["temp"] = None
        except Exception:
            response_data["temp"] = None
        
        # 获取区间分析信息（功率和心率区间）
        try:
            zones_data = []
            
            # 获取功率区间数据
            try:
                power_zones = get_activity_power_zones(db, activity_id)
                if power_zones:
                    zones_data.append(ZoneData(**power_zones))
            except Exception:
                pass
            
            # 获取心率区间数据
            try:
                heartrate_zones = get_activity_heartrate_zones(db, activity_id)
                if heartrate_zones:
                    zones_data.append(ZoneData(**heartrate_zones))
            except Exception:
                pass
            
            if zones_data:
                response_data["zones"] = zones_data
            else:
                response_data["zones"] = None
        except Exception:
            response_data["zones"] = None
        
        # 获取最佳功率信息
        try:
            best_power_info = get_activity_best_power_info(db, activity_id)
            if best_power_info:
                response_data["best_powers"] = best_power_info["best_powers"]
            else:
                response_data["best_powers"] = None
        except Exception:
            response_data["best_powers"] = None
        
        # 获取流数据
        try:
            # 直接调用streams模块的CRUD函数，避免循环导入
            from ..streams.crud import stream_crud
            from ..streams.models import Resolution
            
            # 获取可用的流数据类型
            available_result = stream_crud.get_available_streams(db, activity_id)
            if available_result["status"] == "success":
                available_streams = available_result["available_streams"]
                
                # 设置分辨率
                resolution_enum = Resolution.HIGH
                if resolution == "low":
                    resolution_enum = Resolution.LOW
                elif resolution == "medium":
                    resolution_enum = Resolution.MEDIUM
                
                # 获取流数据
                streams_data = stream_crud.get_activity_streams(db, activity_id, available_streams, resolution_enum)
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


