from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import crud, schemas, models
from .utils import get_db

router = APIRouter()

@router.get("/", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    获取用户列表
    - 支持分页参数 skip（跳过多少条）和 limit（最多返回多少条）
    - 返回用户基本信息列表
    """
    return crud.get_users(db, skip=skip, limit=limit)

@router.get("/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    """
    获取指定用户的详细信息
    - user_id: 用户ID
    - 返回该用户的基本信息
    - 如果用户不存在，返回404错误
    """
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.post("/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    创建新用户
    - 接收用户基本信息（如姓名、FTP、最大心率、体重等）
    - 返回创建后的用户信息
    """
    return crud.create_user(db, user)

@router.post("/{user_id}/metrics", response_model=schemas.UserMetric)
def add_user_metric(user_id: int, metric: schemas.UserMetricCreate, db: Session = Depends(get_db)):
    """
    为指定用户添加一个新的用户指标（如体能测试结果、专项数值等）
    - user_id: 用户ID
    - metric: 指标名称和数值
    - 返回添加后的用户指标信息
    """
    return crud.create_user_metric(db, metric, user_id)

@router.put("/{user_id}", response_model=schemas.User)
def update_user_info(user_id: int, user_update: schemas.UserUpdate, db: Session = Depends(get_db)):
    """
    这个API用于更新指定用户的个人信息。
    - 通过用户ID（user_id）定位要更新的用户
    - 接收需要更新的字段（如FTP、最大心率、体重等，可以部分更新）
    - 如果用户存在，则更新并返回最新的用户信息
    - 如果用户不存在，返回404错误
    """
    db_user = crud.update_user(db, user_id, user_update)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user 