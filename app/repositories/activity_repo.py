from typing import Optional, Tuple, Any, Type
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import logging

from ..db.models import TbActivity, TbAthlete, TbAthleteDailyState

logger = logging.getLogger(__name__)


def get_activity_by_id(db: Session, activity_id: int) -> Optional[TbActivity]:
    try:
        return db.query(TbActivity).filter(TbActivity.id == activity_id).first()
    except Exception as e:
        logger.error("[db-error][activity-select] activity_id=%s err=%s", activity_id, e)
        return None


def get_athlete_by_id(db: Session, athlete_id: int) -> Optional[TbAthlete]:
    try:
        return db.query(TbAthlete).filter(TbAthlete.id == athlete_id).first()
    except Exception as e:
        logger.error("[db-error][athlete-select] athlete_id=%s err=%s", athlete_id, e)
        return None


def get_activity_athlete(db: Session, activity_id: int) -> Optional[Tuple[TbActivity, TbAthlete]]:
    try:
        activity = get_activity_by_id(db, activity_id)
        if not activity:
            logger.info("[db-error][activity-athlete] activity not found activity_id=%s", activity_id)
            return None
        athlete = get_athlete_by_id(db, activity.athlete_id)
        if not athlete:
            logger.info("[db-error][activity-athlete] athlete not found activity_id=%s athlete_id=%s", activity_id, getattr(activity, 'athlete_id', None))
            return None
        return activity, athlete
    except Exception as e:
        logger.error("[db-error][activity-athlete] activity_id=%s err=%s", activity_id, e)
        return None


def update_field(db: Session, table_class: Type[Any], record_id: int, field_name: str, value: Any) -> bool:
    try:
        record = db.query(table_class).filter(table_class.id == record_id).first()
        if not record or not hasattr(record, field_name):
            return False
        setattr(record, field_name, value)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False


def get_avg_tss_by_athlete(db: Session, athlete_id: int, start_date: datetime, end_date: datetime, days: int) -> float:
    """计算指定运动员在指定时间范围内的平均TSS（按天数平均）
    
    注意：这里计算的是"总TSS / 天数"，而不是"活动TSS的平均值"
    例如：7天内总TSS=700，则返回 700/7=100，而不是 700/活动数量
    
    实现方式与 activity_service.py 中的 _update_athlete_status 保持一致：
    - 查询条件：start_date >= start_date AND start_date <= end_date（设置上限）
    - 除以固定的天数（7.0 或 42.0），而不是计算时间差
    
    Args:
        db: 数据库会话
        athlete_id: 运动员ID
        start_date: 开始时间（例如：7天前或42天前）
        end_date: 结束时间（上限，例如：now 或 ref_date）
        days: 天数（用于计算平均值，例如：7 表示7天，42 表示42天）
        
    Returns:
        float: 平均TSS（总TSS除以天数），如果没有记录则返回0.0
    """
    try:
        if days <= 0:
            return 0.0
        
        # 使用 SUM 求和，查询条件包含上限
        # 与 activity_service.py 中的 _update_athlete_status 保持一致
        sum_result = db.query(func.sum(TbActivity.tss)).filter(
            TbActivity.athlete_id == athlete_id,
            TbActivity.start_date >= start_date,
            TbActivity.start_date <= end_date,
            TbActivity.tss.isnot(None),
            TbActivity.tss > 0,
        ).scalar()
        
        # 如果没有记录或总和为 None，返回 0.0
        if sum_result is None:
            return 0.0
        
        # 返回：总TSS / 天数（固定值，不是计算的时间差）
        return float(sum_result) / days
    except Exception as e:
        logger.error("[db-error][avg-tss] athlete_id=%s err=%s", athlete_id, e)
        return 0.0


def upsert_daily_state(db: Session, athlete_id: int, target_date: date, fitness: float, fatigue: float, status: float) -> bool:
    """插入或更新每日状态
    
    Args:
        db: 数据库会话
        athlete_id: 运动员ID
        target_date: 目标日期
        fitness: 健康度（最近42天平均TSS）
        fatigue: 疲劳度（最近7天平均TSS）
        status: 状态值（fitness - fatigue）
        
    Returns:
        bool: 是否成功
    """
    try:
        # 直接使用 date，不需要转换为 datetime
        from datetime import datetime as dt
        
        # 查找是否存在
        existing = db.query(TbAthleteDailyState).filter(
            and_(
                TbAthleteDailyState.athlete_id == athlete_id,
                TbAthleteDailyState.date == target_date
            )
        ).first()
        
        if existing:
            # 更新
            existing.fitness = int(fitness)
            existing.fatigue = int(fatigue)
            existing.status = int(status)
            existing.updated_at = dt.now()
        else:
            # 插入
            new_state = TbAthleteDailyState(
                athlete_id=athlete_id,
                date=target_date,
                fitness=int(fitness),
                fatigue=int(fatigue),
                status=int(status),
                updated_at=dt.now()
            )
            db.add(new_state)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error("[db-error][daily-state-upsert] athlete_id=%s date=%s err=%s", athlete_id, target_date, e)
        return False
