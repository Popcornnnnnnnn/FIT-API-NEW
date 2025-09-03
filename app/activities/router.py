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
import json

def _is_cache_enabled():
    """检查缓存是否启用"""
    import os
    
    # 优先检查配置文件
    if os.path.exists('.cache_config'):
        try:
            with open('.cache_config', 'r') as f:
                content = f.read().strip()
                return "enabled=true" in content
        except:
            pass
    
    # 检查环境变量
    return os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'

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

        # 针对 Strava（带 access_token）场景，将 external_id 映射为内部 tb_activity.id 作为缓存ID
        cache_activity_id = activity_id
        if access_token:
            try:
                from ..streams.models import TbActivity
                _internal = db.query(TbActivity).filter(TbActivity.external_id == activity_id).first()
                if _internal and _internal.id:
                    cache_activity_id = _internal.id
            except Exception as _:
                # 映射失败则回退使用传入的 activity_id
                cache_activity_id = activity_id

        # 生成缓存键 - 包含数据精度和字段信息
        cache_key = activity_cache_manager.generate_cache_key(
            activity_id=cache_activity_id,
            resolution=resolution,
            keys=keys
        )
        
        # 尝试从缓存获取数据
        if _is_cache_enabled():
            cached_data = activity_cache_manager.get_cache(db, cache_activity_id, cache_key)
            if cached_data:
                print(f"🟢 [缓存命中] 活动{cache_activity_id}的所有数据")
                return AllActivityDataResponse(**cached_data)
        else:
            print(f"🔴 [缓存已禁用] 跳过缓存查询")
        
        print(f"🔴 [缓存未命中] 活动{cache_activity_id}的所有数据 - 正在计算...")

        # 如果传入了 access_token，调用 Strava API
        if access_token:
            try:
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                # 根据活动时长动态选择精度，避免超过10000个数据点
                activity_response = requests.get(
                    f"https://www.strava.com/api/v3/activities/{activity_id}", 
                    headers=headers, 
                    timeout=10)
                
                if activity_response.status_code != 200:
                    raise HTTPException(
                        status_code=activity_response.status_code,
                        detail=f"Strava API 活动信息获取失败: {activity_response.text}"
                    )
                
                activity_data = activity_response.json()
                
                # 计算活动时长（秒）并决定API精度
                moving_time = activity_data.get("moving_time", 0)
                # 如果活动时长超过10000秒（约2.78小时），使用低精度API
                # 低精度：每20秒一个数据点，高精度：每1秒一个数据点
                if moving_time > 10000:
                    api_resolution = "medium"
                    print(f"活动时长 {moving_time}秒，使用低精度API避免数据截断")
                else:
                    api_resolution = "high"
                
                stream_response = requests.get(
                    f"https://www.strava.com/api/v3/activities/{activity_id}/streams?keys=time,distance,latlng,altitude,velocity_smooth,heartrate,cadence,watts,temp,moving,grade_smooth&key_by_type=true&resolution={api_resolution}", 
                    headers=headers, 
                    timeout=5)
                athlete_response = requests.get( 
                    "https://www.strava.com/api/v3/athlete",
                    headers=headers,
                    timeout=5
                )
                if athlete_response.status_code != 200:
                    raise HTTPException(
                        status_code=athlete_response.status_code,
                        detail=f"Strava API 运动员信息获取失败: {athlete_response.text}"
                    )
                if stream_response.status_code != 200:
                    raise HTTPException(
                        status_code=stream_response.status_code,
                        detail=f"Strava API 流数据获取失败: {stream_response.text}"
                    )
                stream_data = stream_response.json()
                athlete_data = athlete_response.json()
                # print(athlete_data["ftp"])

                # 检查Strava数据有效性
                if (activity_data.get("distance", 0) <= 0 or 
                    activity_data.get("average_speed", 0) <= 0 or 
                    activity_data.get("moving_time", 0) <= 0 or
                    activity_data.get("max_speed", 0) <= 0):
                    print(f"⚠️ [数据无效] 活动{activity_id}的Strava数据无效，返回全null响应")
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
                    # 如果 keys 为空，返回所有可用的字段
                    keys_list = ['time', 'distance', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp',  'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam'] # ! 去掉 lating、moving、grade_smooth，将 velocity_smooth 改成 speed
                
                response_data = StravaAnalyzer.analyze_activity_data(activity_data, stream_data, athlete_data, activity_id, db, keys_list, resolution)
                
                # 更新最佳成绩记录（Strava API数据）
                best_efforts_result = None
                try:
                    print(f"🔄 [最佳成绩检查] 开始检查活动{activity_id}的Strava最佳成绩...")
                    # external_id -> internal_id，并用数据管理器获取 (activity, athlete)
                    from ..streams.models import TbActivity
                    internal_activity = db.query(TbActivity).filter(TbActivity.external_id == activity_id).first()
                    if not internal_activity:
                        raise Exception("未找到对应的本地活动记录")

                    # 通过全局数据管理器获取 (activity, athlete)，保证统一返回值和缓存
                    local_activity, local_athlete = activity_data_manager.get_athlete_info(db, internal_activity.id)
                    if not local_activity or not local_athlete:
                        raise Exception("本地活动或运动员信息不存在，无法更新最佳成绩")

                    best_efforts_result = activity_data_manager.update_best_efforts(db, local_activity.id)
                except Exception as e:
                    print(f"⚠️ [最佳成绩检查失败] 活动{activity_id}: {str(e)}")
                    best_efforts_result = {
                        "success": False,
                        "new_records": {"power_records": {}, "speed_records": {}},
                        "message": f"最佳成绩检查失败: {str(e)}"
                    }
                
                # 如果有新的最佳成绩记录，添加到响应中
                if best_efforts_result and best_efforts_result.get("success") and best_efforts_result.get("new_records"):
                    new_records = best_efforts_result["new_records"]
                    if new_records["power_records"] or new_records["speed_records"]:
                        # 将最佳成绩信息添加到响应中
                        if hasattr(response_data, 'dict'):
                            response_dict = response_data.dict()
                        else:
                            response_dict = response_data
                        response_dict["best_efforts_update"] = {
                            "success": True,
                            "new_records": new_records,
                            "message": best_efforts_result.get("message", "最佳成绩已更新")
                        }
                        response_data = AllActivityDataResponse(**response_dict)
                
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
                    activity_cache_manager.set_cache(db, cache_activity_id, cache_key, response_dict, metadata)
                    print(f"✅ [缓存设置] 活动{activity_id}的Strava API数据已缓存（补齐后）")
                elif not _is_cache_enabled():
                    print(f"🔴 [缓存已禁用] 跳过Strava API数据缓存")
                
                return response_data
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
        
        # 更新最佳成绩记录（仅在本地数据库查询时执行，避免重复更新）
        best_efforts_result = None
        try:
            print(f"🔄 [最佳成绩检查] 开始检查活动{activity_id}的最佳成绩...")
            best_efforts_result = activity_data_manager.update_best_efforts(db, activity_id)
        except Exception as e:
            print(f"⚠️ [最佳成绩检查失败] 活动{activity_id}: {str(e)}")
            best_efforts_result = {
                "success": False,
                "new_records": {"power_records": {}, "speed_records": {}},
                "message": f"最佳成绩检查失败: {str(e)}"
            }
        
        # 构建响应
        final_response = AllActivityDataResponse(**response_data)
        
        # 如果有新的最佳成绩记录，添加到响应中
        if best_efforts_result and best_efforts_result.get("success") and best_efforts_result.get("new_records"):
            new_records = best_efforts_result["new_records"]
            if new_records["power_records"] or new_records["speed_records"]:
                # 将最佳成绩信息添加到响应中
                response_data["best_efforts_update"] = {
                    "success": True,
                    "new_records": new_records,
                    "message": best_efforts_result.get("message", "最佳成绩已更新")
                }
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
                print(f"✅ [缓存设置] 活动{activity_id}的本地数据库数据已缓存")
            except Exception as e:
                print(f"⚠️ [缓存失败] 活动{activity_id}的本地数据库数据缓存失败: {e}")
        else:
            print(f"🔴 [缓存已禁用] 跳过本地数据库数据缓存")
        
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
        from .models import TbActivityCache
        
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
        from .models import TbActivityCache
        
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
            # 同步清空内存缓存（ActivityDataManager）
            try:
                from .data_manager import activity_data_manager
                activity_data_manager.clear_cache()
                print("🧹 [缓存清空] 已清空内存中的活动/会话/运动员缓存")
            except Exception as ce:
                print(f"⚠️ [缓存清空失败] {ce}")
        
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

@router.post("/{activity_id}/update-best-efforts")
async def update_activity_best_efforts(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """手动更新指定活动的最佳成绩记录"""
    try:
        print(f"🔄 [手动触发] 开始更新活动{activity_id}的最佳成绩...")
        result = activity_data_manager.update_best_efforts(db, activity_id)
        
        if result.get("success"):
            return {
                "message": f"活动 {activity_id} 的最佳成绩更新成功",
                "data": {
                    "activity_id": activity_id,
                    "status": "success",
                    "new_records": result.get("new_records", {})
                }
            }
        else:
            return {
                "message": result.get("message", f"活动 {activity_id} 未刷新任何最佳成绩记录"),
                "data": {
                    "activity_id": activity_id,
                    "status": "no_new_records",
                    "new_records": result.get("new_records", {})
                }
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新最佳成绩时发生错误: {str(e)}")

@router.get("/{athlete_id}/athlete-best-efforts")
async def get_athlete_best_efforts(
    athlete_id: int,
    db: Session = Depends(get_db)
):
    """按 athlete_id 获取运动员的最佳成绩记录"""
    try:
        # 查询最佳成绩记录
        from ..streams.models import TbAthleteBestEfforts, TbAthlete
        # 可选：校验运动员存在
        athlete = db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first()
        if not athlete:
            raise HTTPException(status_code=404, detail="运动员不存在")

        best_efforts = db.query(TbAthleteBestEfforts).filter(
            TbAthleteBestEfforts.athlete_id == athlete_id
        ).first()
        
        if not best_efforts:
            return {
                "message": "该运动员暂无最佳成绩记录",
                "data": {
                    "athlete_id": athlete_id,
                    "best_efforts": None
                }
            }
        
        # 构建响应数据
        power_records = {}
        speed_records = {}
        
        # 分段时间功率记录
        time_intervals = ['5s', '10s', '15s', '20s', '30s', '40s', '60s', '2m', '3m', '5m', '10m', '15m', '20m', '30m', '40m', '1h', '2h', '3h', '4h']
        for interval in time_intervals:
            power_field = f"best_power_{interval}"
            activity_field = f"best_power_{interval}_activity_id"
            
            power_value = getattr(best_efforts, power_field, None)
            activity_id_value = getattr(best_efforts, activity_field, None)
            
            if power_value is not None:
                power_records[interval] = {
                    "power": int(power_value),
                    "activity_id": int(activity_id_value) if activity_id_value is not None else None
                }
        
        # 分段距离速度记录
        distance_intervals = ['5km', '10km', '20km', '30km', '40km', '50km', '60km', '70km', '80km', '90km', '100km']
        for distance in distance_intervals:
            speed_field = f"best_speed_{distance}"
            activity_field = f"best_speed_{distance}_activity_id"
            
            speed_value = getattr(best_efforts, speed_field, None)
            activity_id_value = getattr(best_efforts, activity_field, None)
            
            if speed_value is not None:
                speed_records[distance] = {
                    "speed": float(speed_value),
                    "activity_id": int(activity_id_value) if activity_id_value is not None else None
                }
        
        return {
            "message": "获取最佳成绩记录成功",
            "data": {
                "athlete_id": athlete_id,
                "power_records": power_records,
                "speed_records": speed_records,
                "created_at": best_efforts.created_at,
                "updated_at": best_efforts.updated_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取最佳成绩记录时发生错误: {str(e)}")




