# 这个文件（crud.py）是项目的数据操作层（CRUD：Create, Read, Update, Delete），
# 主要负责对数据库进行增删查改等操作。它通过SQLAlchemy的Session对象与数据库交互。
# 
# crud.py 里的每个函数都对应一种数据库操作，比如获取用户、创建用户、添加用户指标、创建活动等。
# 这些操作都是围绕 models.py 里定义的ORM模型（User, UserMetric, Activity）进行的。
# 
# models.py 负责定义数据库表结构（ORM模型），而 crud.py 负责具体的数据操作逻辑。
# 也就是说，models.py 定义“数据长什么样”，crud.py 负责“怎么查、怎么存、怎么改这些数据”。
# 
# 例如：create_user 会根据 schemas.UserCreate（Pydantic模型）创建 models.User（ORM模型）对象，
# 然后通过Session写入数据库。create_activity、create_user_metric等同理。


from sqlalchemy.orm import Session
from sqlalchemy import select
from . import models, schemas

def get_user(db: Session, user_id: int):
    """
    获取指定ID的用户对象，找不到则返回None
    """
    stmt = select(models.User).where(models.User.id == user_id)
    result = db.execute(stmt).scalar_one_or_none()
    return result

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    获取用户列表，支持分页
    """
    stmt = select(models.User).offset(skip).limit(limit)
    result = db.execute(stmt).scalars().all()
    return result

def create_user(db: Session, user: schemas.UserCreate):
    """
    创建新用户并返回用户对象

    """
    db_user = models.User(
        name=user.name,
        ftp=user.ftp,
        max_hr=user.max_hr,
        weight=user.weight
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    # print("db_user", vars(db_user))  # 推荐这样打印属性
    return db_user

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    """
    更新用户信息（只更新有传递的字段），返回更新后的用户对象
    """
    stmt = select(models.User).where(models.User.id == user_id)
    db_user = db.execute(stmt).scalar_one_or_none()
    if db_user is None:
        return None

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)

    db.commit()
    db.refresh(db_user)
    return db_user

# 用户指标相关

def create_user_metric(db: Session, metric: schemas.UserMetricCreate, user_id: int):
    """
    为指定用户添加新的指标记录
    """
    db_metric = models.UserMetric(**metric.model_dump(), user_id=user_id)
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

# 活动相关

def create_activity(db: Session, activity: schemas.ActivityCreate):
    """
    创建新的活动记录
    """
    db_activity = models.Activity(**activity.model_dump())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity