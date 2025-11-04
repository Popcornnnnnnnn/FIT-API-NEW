"""
FIT文件分析API主应用文件。

本文件是FastAPI应用的入口点，负责：
1. 创建FastAPI应用实例
2. 注册各个模块的路由
3. 配置API文档标签
"""

from fastapi import FastAPI
from .logging_config import setup_logging
from .config import LOG_LEVEL

from .api.streams import router as streams_router
from .api.activities import router as activities_router
from .api.legacy.activities_legacy import router as activities_legacy_router
from .api.athletes import router as athletes_router
from .api.test import router as test_router

setup_logging(LOG_LEVEL)
app = FastAPI(title="FIT 文件分析 API")

# 路由注册
app.include_router(streams_router, tags=["数据流"])
app.include_router(activities_router, tags=["活动"])
app.include_router(activities_legacy_router, tags=["活动-历史"])
app.include_router(athletes_router, tags=["运动员"])
app.include_router(test_router, tags=["测试"])
