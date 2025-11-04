"""
Athletes API routes

包含：
- POST /athletes/{athlete_id}/daily-state/update：更新运动员每日状态
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
import logging

from ..utils import get_db
from ..schemas.athletes import DailyStateUpdateResponse, DailyStateDetail
from ..services.daily_state_service import daily_state_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/athletes", tags=["运动员"])


@router.post("/{athlete_id}/daily-state/update", response_model=DailyStateUpdateResponse)
async def update_daily_state(
    athlete_id: int,
    date_param: Optional[str] = Query(None, alias="date", description="日期，格式：YYYY-MM-DD，不传则使用今天"),
    db: Session = Depends(get_db),
):
    """更新运动员的每日状态
    
    计算并更新指定运动员的健康度（fitness）、疲劳度（fatigue）和状态（status）：
    - fitness: 最近42天的平均TSS
    - fatigue: 最近7天的平均TSS
    - status: fitness - fatigue
    
    Args:
        athlete_id: 运动员ID（路径参数）
        date_param: 日期（查询参数，可选，格式：YYYY-MM-DD，不传则使用今天）
        
    Returns:
        DailyStateUpdateResponse: 更新结果
        
    Raises:
        HTTPException: 400 - 日期格式错误
        HTTPException: 500 - 服务器内部错误
    """
    try:
        # 解析日期参数
        target_date = None
        if date_param:
            try:
                target_date = date.fromisoformat(date_param)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"日期格式错误，应为 YYYY-MM-DD，收到：{date_param}"
                )
        
        # 调用服务层更新状态
        result = daily_state_service.update_daily_state(db, athlete_id, target_date)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "更新失败")
            )
        
        # 构造响应
        detail = DailyStateDetail(
            athlete_id=result["athlete_id"],
            date=result["date"],
            fitness=result["fitness"],
            fatigue=result["fatigue"],
            daily_status=result["daily_status"]
        )
        
        return DailyStateUpdateResponse(
            message=result["message"],
            status="success",
            data=detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[daily-state-api][error] athlete_id=%s", athlete_id)
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

