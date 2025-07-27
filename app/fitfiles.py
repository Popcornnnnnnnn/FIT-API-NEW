from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from . import crud, schemas, models
from .utils import get_db
# from fitparse import FitFile  # 解析库，后续实现
import os

router = APIRouter()

UPLOAD_DIR = "uploads"  # 临时存储目录
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=schemas.Activity)
def upload_fit_file(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    # 创建活动记录
    activity_in = schemas.ActivityCreate(user_id=user_id)
    activity = crud.create_activity(db, activity_in)
    # TODO: 解析FIT文件，存储分析结果
    # TODO: 后台队列处理预留
    return activity

# TODO: 解析接口、流数据接口、后台队列接口预留 