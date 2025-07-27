# FIT 文件分析 API

基于 FastAPI + MySQL 的 FIT 文件分析后端接口。

## 主要功能
- 用户信息管理（不含注册/登录）
- 用户运动指标管理
- FIT 文件上传与解析（预留后台队列/临时存储接口）
- 活动数据分析API（摘要、流数据、高级指标等）
- 自动API文档（/docs）

## 依赖安装
```bash
pip install -r requirements.txt
```

## 数据库初始化
1. 修改 `app/utils.py` 中的数据库连接配置，或设置 `DATABASE_URL` 环境变量。
2. 使用 Alembic 或手动建表（见 `app/models.py`）。

## 启动开发服务器
```bash
uvicorn app.main:app --reload
```

## 目录结构
- app/main.py         # FastAPI入口
- app/models.py       # SQLAlchemy模型
- app/schemas.py      # Pydantic数据模型
- app/crud.py         # 数据库操作
- app/users.py        # 用户API
- app/fitfiles.py     # FIT文件API
- app/analysis.py     # 数据分析API
- app/utils.py        # 工具函数

## 说明
- 后台队列、临时存储等功能已预留接口，后续可扩展。
- 测试与文档可后续补充。 