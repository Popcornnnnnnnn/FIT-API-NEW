"""
FIT文件分析API主应用文件。

本文件是FastAPI应用的入口点，负责：
1. 创建FastAPI应用实例
2. 注册各个模块的路由
3. 配置API文档标签
4. 预留扩展功能接口
"""

from fastapi import FastAPI

from .streams.router import router as streams_router

app = FastAPI(title="FIT 文件分析 API")

# 路由注册
app.include_router(streams_router, tags=["数据流"])

# 预留：后台队列、临时存储等功能接口
# TODO: Celery/RQ任务队列集成
# TODO: 临时文件清理定时任务

# 启动命令（开发环境）
# uvicorn app.main:app --reload 