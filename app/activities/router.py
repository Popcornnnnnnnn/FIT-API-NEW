"""
Activities模块的路由

包含活动相关的API端点。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..utils import get_db
from .schemas import ZoneRequest, ZoneResponse, ZoneData, DistributionBucket, ZoneType, OverallResponse, PowerResponse, HeartrateResponse, CadenceResponse, SpeedResponse, AltitudeResponse, TemperatureResponse, BestPowerResponse, TrainingEffectResponse, MultiStreamRequest, MultiStreamResponse, StreamDataItem
from .crud import get_activity_athlete, get_activity_stream_data, get_activity_overall_info, get_activity_power_info, get_activity_heartrate_info, get_activity_cadence_info, get_activity_speed_info, get_activity_altitude_info, get_activity_temperature_info, get_activity_best_power_info, get_activity_training_effect_info
from .zone_analyzer import ZoneAnalyzer
from ..streams.models import Resolution
from ..streams.crud import stream_crud
import logging

router = APIRouter(prefix="/activities", tags=["活动"])

@router.get("/{activity_id}/zones", response_model=ZoneResponse)
async def get_activity_zones(
    activity_id: int,
    key: ZoneType = Query(..., description="区间类型：power（功率）或heartrate（心率）"),
    db: Session = Depends(get_db)
):
    """
    获取活动的区间分析数据
    """
    try:
        # 获取活动和运动员信息
        activity_athlete = get_activity_athlete(db, activity_id)
        if not activity_athlete:
            raise HTTPException(status_code=404, detail="活动或运动员信息不存在")
        
        activity, athlete = activity_athlete
        
        # 获取流数据
        stream_data = get_activity_stream_data(db, activity_id)
        if not stream_data:
            raise HTTPException(status_code=404, detail="活动流数据不存在")
        
        # 根据区间类型进行分析
        if key == ZoneType.POWER:
            # athlete.ftp 可能为字符串，需要转为 int
            try:
                ftp = int(athlete.ftp)
            except (TypeError, ValueError):
                ftp = None
            if not ftp or ftp <= 0:
                raise HTTPException(status_code=400, detail="运动员FTP数据不存在或无效")
            
            power_data = stream_data.get('power', [])
            if not power_data:
                raise HTTPException(status_code=400, detail="活动功率数据不存在")
            
            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, ftp)
            zone_type = "power"
            
        elif key == ZoneType.HEARTRATE:
            if not athlete.max_heartrate or athlete.max_heartrate <= 0:
                raise HTTPException(status_code=400, detail="运动员最大心率数据不存在或无效")
            
            hr_data = stream_data.get('heart_rate', [])
            if not hr_data:
                raise HTTPException(status_code=400, detail="活动心率数据不存在")
            
            distribution_buckets = ZoneAnalyzer.analyze_heartrate_zones(hr_data, athlete.max_heartrate)
            zone_type = "heartrate"
        
        else:
            raise HTTPException(status_code=400, detail="不支持的区间类型")
        
        # 构建响应
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
    db: Session = Depends(get_db)  # @ db 是通过 FastAPI 的 Depends 依赖注入机制，从 get_db 函数获取的数据库会话（Session）对象
):
    """
    获取活动的总体信息
    
    返回活动的关键指标，包括距离、时间、速度、功率、心率等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动总体信息
        overall_info = get_activity_overall_info(db, activity_id)
        if not overall_info:
            raise HTTPException(status_code=404, detail="活动信息不存在或无法解析")
        
        # 构建响应
        return OverallResponse(**overall_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/power", response_model=PowerResponse)
async def get_activity_power(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的功率相关信息
    
    返回活动的功率相关指标，包括平均功率、最大功率、标准化功率、强度因子等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动功率信息
        power_info = get_activity_power_info(db, activity_id)
        if not power_info:
            raise HTTPException(status_code=404, detail="活动功率信息不存在或无法解析")
        
        # 构建响应
        return PowerResponse(**power_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/heartrate", response_model=HeartrateResponse)
async def get_activity_heartrate(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的心率相关信息
    
    返回活动的心率相关指标，包括平均心率、最大心率、效率指数、解耦率等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动心率信息
        heartrate_info = get_activity_heartrate_info(db, activity_id)
        if not heartrate_info:
            raise HTTPException(status_code=404, detail="活动心率信息不存在或无法解析")
        
        # 构建响应
        return HeartrateResponse(**heartrate_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/cadence", response_model=CadenceResponse)
async def get_activity_cadence(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的踏频相关信息
    
    返回活动的踏频相关指标，包括平均踏频、最大踏频、左右平衡、扭矩效率、踏板平顺度、总踩踏次数等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动踏频信息
        cadence_info = get_activity_cadence_info(db, activity_id)
        if not cadence_info:
            raise HTTPException(status_code=404, detail="活动踏频信息不存在或无法解析")
        
        # 构建响应
        return CadenceResponse(**cadence_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/speed", response_model=SpeedResponse)
async def get_activity_speed(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的速度相关信息
    
    返回活动的速度相关指标，包括平均速度、最大速度、移动时间、全程耗时、暂停时间、滑行时间等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动速度信息
        speed_info = get_activity_speed_info(db, activity_id)
        if not speed_info:
            raise HTTPException(status_code=404, detail="活动速度信息不存在或无法解析")
        
        # 构建响应
        return SpeedResponse(**speed_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/altitude", response_model=AltitudeResponse)
async def get_activity_altitude(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的海拔相关信息
    
    返回活动的海拔相关指标，包括爬升海拔、最高海拔、最大坡度、累计下降、最低海拔、上坡距离、下坡距离等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动海拔信息
        altitude_info = get_activity_altitude_info(db, activity_id)
        if not altitude_info:
            raise HTTPException(status_code=404, detail="活动海拔信息不存在或无法解析")
        
        # 构建响应
        return AltitudeResponse(**altitude_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 

@router.get("/{activity_id}/else", response_model=TemperatureResponse)
async def get_activity_temperature(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的温度相关信息
    
    返回活动的温度相关指标，包括最低温度、平均温度、最大温度。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动温度信息
        temperature_info = get_activity_temperature_info(db, activity_id)
        if not temperature_info:
            raise HTTPException(status_code=404, detail="活动温度信息不存在或无法解析")
        
        # 构建响应
        return TemperatureResponse(**temperature_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}") 

@router.get("/{activity_id}/bestpower", response_model=BestPowerResponse)
async def get_activity_best_power(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的最佳功率信息
    
    返回活动在不同时间区间的最佳功率数据，包括5秒、30秒、1分钟、5分钟、8分钟、20分钟、30分钟、1小时的最佳功率。
    如果活动时长不足某个时间区间，则不返回该区间的数据。
    """
    try:
        # 获取活动最佳功率信息
        best_power_info = get_activity_best_power_info(db, activity_id)
        if not best_power_info:
            raise HTTPException(status_code=404, detail="活动最佳功率信息不存在或无法解析")
        
        # 构建响应
        return BestPowerResponse(**best_power_info)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@router.get("/{activity_id}/training_effect", response_model=TrainingEffectResponse)
async def get_activity_training_effect(
    activity_id: int,
    db: Session = Depends(get_db)
):
    """
    获取活动的训练效果信息
    
    返回活动的训练效果相关指标，包括主要训练益处、有氧效果、无氧效果、训练负荷、碳水化合物消耗量等。
    优先使用FIT文件session段中的数据，如果没有则从流数据中计算。
    """
    try:
        # 获取活动训练效果信息
        training_effect_info = get_activity_training_effect_info(db, activity_id)
        if not training_effect_info:
            raise HTTPException(status_code=404, detail="活动训练效果信息不存在或无法解析")
        
        # 构建响应
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


