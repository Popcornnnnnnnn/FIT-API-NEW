"""
Daily State Service（每日状态服务）

职责：
- 计算运动员的健康度（fitness）、疲劳度（fatigue）和状态（status）
- 更新 tb_athlete_daily_state 表
"""

from typing import Optional
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
import logging

from ..repositories.activity_repo import (
    get_athlete_by_id,
    upsert_daily_state
)

logger = logging.getLogger(__name__)


class DailyStateService:
    """每日状态服务"""
    
    def update_daily_state(
        self,
        db: Session,
        athlete_id: int,
        target_date: Optional[date] = None
    ) -> dict:
        """更新指定运动员的每日状态
        
        Args:
            db: 数据库会话
            athlete_id: 运动员ID
            target_date: 目标日期，不传则使用今天
            
        Returns:
            dict: 包含更新结果的字典，格式：
            {
                "success": bool,
                "athlete_id": int,
                "date": str,
                "fitness": float,
                "fatigue": float,
                "daily_status": float,
                "message": str
            }
        """
        # 使用今天作为默认日期
        if target_date is None:
            target_date = date.today()
        
        # 验证运动员是否存在
        athlete = get_athlete_by_id(db, athlete_id)
        if not athlete:
            logger.warning("[daily-state][athlete-not-found] athlete_id=%s", athlete_id)
            return {
                "success": False,
                "athlete_id": athlete_id,
                "date": target_date.isoformat(),
                "message": f"运动员 {athlete_id} 不存在"
            }
        
        try:
            # 计算时间范围（与 activity_service.py 中的 _update_athlete_status 完全一致）
            # 如果 target_date 是今天，使用当前时间；否则使用 target_date 的 23:59:59
            if target_date == date.today():
                now = datetime.now()
            else:
                now = datetime.combine(target_date, datetime.max.time())
            
            seven_days_ago = now - timedelta(days=7)
            forty_two_days_ago = now - timedelta(days=42)
            
            # 直接使用 SQLAlchemy 查询，与 _update_athlete_status 逻辑完全一致
            from sqlalchemy import func
            from ..db.models import TbActivity
            
            # 查询条件：start_date >= seven_days_ago AND start_date <= now（设置上限）
            sum_tss_7 = db.query(func.sum(TbActivity.tss)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= seven_days_ago,
                TbActivity.start_date <= now,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            
            # 查询条件：start_date >= forty_two_days_ago AND start_date <= now（设置上限）
            sum_tss_42 = db.query(func.sum(TbActivity.tss)).filter(
                TbActivity.athlete_id == athlete_id,
                TbActivity.start_date >= forty_two_days_ago,
                TbActivity.start_date <= now,
                TbActivity.tss.isnot(None),
                TbActivity.tss > 0,
            ).scalar()
            
            # 转为 float 再做除法，避免 Decimal 与 float 混算报错（与 _update_athlete_status 一致）
            sum7 = float(sum_tss_7 or 0)
            sum42 = float(sum_tss_42 or 0)

            print(f"sum7: {sum7} sum42: {sum42}")
            
            # 除以固定的天数（与 _update_athlete_status 一致）
            fatigue = sum7 / 7.0
            fitness = sum42 / 42.0
            
            # 计算状态值
            status = fitness - fatigue
            
            # 写入数据库
            success = upsert_daily_state(db, athlete_id, target_date, fitness, fatigue, status)
            
            if not success:
                logger.error("[daily-state][upsert-failed] athlete_id=%s date=%s", athlete_id, target_date)
                return {
                    "success": False,
                    "athlete_id": athlete_id,
                    "date": target_date.isoformat(),
                    "message": "数据库更新失败"
                }
            
            logger.info(
                "[daily-state][updated] athlete_id=%s date=%s fitness=%.2f fatigue=%.2f status=%.2f",
                athlete_id, target_date, fitness, fatigue, status
            )
            
            return {
                "success": True,
                "athlete_id": athlete_id,
                "date": target_date.isoformat(),
                "fitness": fitness,
                "fatigue": fatigue,
                "daily_status": status,
                "message": "更新成功"
            }
            
        except Exception as e:
            logger.exception("[daily-state][error] athlete_id=%s date=%s", athlete_id, target_date)
            return {
                "success": False,
                "athlete_id": athlete_id,
                "date": target_date.isoformat(),
                "message": f"更新失败: {str(e)}"
            }


# 创建单例实例
daily_state_service = DailyStateService()

