from fastapi import FastAPI

from . import users, fitfiles, analysis

app = FastAPI(title="FIT 文件分析 API")

# 路由注册
app.include_router(users.router, prefix="/users", tags=["用户"])
app.include_router(fitfiles.router, prefix="/fitfiles", tags=["FIT文件"])
app.include_router(analysis.router, prefix="/analysis", tags=["数据分析"])

# 预留：后台队列、临时存储等功能接口
# TODO: Celery/RQ任务队列集成
# TODO: 临时文件清理定时任务

# 启动命令（开发环境）
# uvicorn app.main:app --reload 