"""
Activities模块的路由

包含活动相关的API端点。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ..utils import get_db
from .schemas import ZoneRequest, ZoneResponse, ZoneData, DistributionBucket, ZoneType
from .crud import get_activity_athlete, get_activity_stream_data
from .zone_analyzer import ZoneAnalyzer

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
            if not athlete.ftp or athlete.ftp <= 0:
                raise HTTPException(status_code=400, detail="运动员FTP数据不存在或无效")
            
            power_data = stream_data.get('power', [])
            if not power_data:
                raise HTTPException(status_code=400, detail="活动功率数据不存在")
            
            distribution_buckets = ZoneAnalyzer.analyze_power_zones(power_data, athlete.ftp)
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