# 这个文件（schemas.py）定义了Pydantic模型（数据验证和序列化用的"数据结构"），
# 主要用于API的请求体、响应体的数据格式校验和转换。
# 
# 它和 models.py、crud.py 的关系如下：
# - models.py 定义数据库ORM模型（描述数据库表结构，直接和数据库交互）。
# - schemas.py 定义Pydantic模型（描述接口输入输出的数据结构，和数据库无关，专注于数据校验和序列化）。
# - crud.py 负责具体的数据操作逻辑（用models.py的ORM模型和数据库交互，输入输出通常用schemas.py的Pydantic模型）。
# 
# 例如，API收到请求时会用schemas.py里的模型校验和解析数据，存储到数据库时会用models.py的ORM模型，
# 数据库操作由crud.py实现，最后响应时再用schemas.py的模型把ORM对象转换成JSON返回。

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
import datetime

class UserBase(BaseModel):
    name: str
    ftp: Optional[float] = None
    max_hr: Optional[int] = None
    weight: Optional[float] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    ftp: Optional[float] = None
    max_hr: Optional[int] = None
    weight: Optional[float] = None

class User(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class UserMetricBase(BaseModel):
    metric_name: str
    metric_value: float

class UserMetricCreate(UserMetricBase):
    pass

class UserMetric(UserMetricBase):
    id: int
    user_id: int
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

class ActivityBase(BaseModel):
    user_id: int

class ActivityCreate(ActivityBase):
    pass

class Activity(ActivityBase):
    id: int
    file_path: str
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True) 