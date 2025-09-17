"""测试/调试相关的轻量路由。"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..repositories.best_power_file_repo import load_best_curve


router = APIRouter(prefix="/test", tags=["测试"])


@router.get("/best_power/{athlete_id}")
async def get_athlete_best_power_curve(athlete_id: int) -> Dict[str, Any]:
    """返回指定运动员的全局最佳功率曲线（逐秒）。"""
    curve = load_best_curve(athlete_id)
    if curve is None:
        raise HTTPException(status_code=404, detail="未找到该运动员的最佳功率曲线记录")
    return {"athlete_id": athlete_id, "length": len(curve), "best_curve": curve}

