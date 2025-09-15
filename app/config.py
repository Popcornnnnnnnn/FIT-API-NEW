"""
应用配置中心（Configuration Center）

说明（强烈建议先快速浏览）：
- 本模块统一管理服务端的运行配置（数据库、缓存、日志、第三方接口等）
- 配置优先从环境变量中读取，避免硬编码敏感信息；必要时提供安全的默认值
- 读取顺序：环境变量（优先） > 配置文件开关（仅缓存） > 安全默认

常用环境变量（全部可选）：
1) 数据库连接（推荐直接设置 `DATABASE_URL`）
   - `DATABASE_URL`：完整连接串，如 mysql+pymysql://user:pass@127.0.0.1:3306/db
   - 或分拆变量：`DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`

2) 缓存与日志
   - `CACHE_ENABLED`：是否启用缓存，"true"/"false"（字符串，不分大小写）。
     若未设置，则会回退读取仓库根目录的 `.cache_config` 文件（内容：enabled=true/false）；
     两者都未设置时，默认启用缓存。
   - `CACHE_DIR`：缓存文件落盘目录，默认 `./data/activity_cache`
   - `LOG_LEVEL`：日志等级，默认 INFO（可选 DEBUG/INFO/WARN/ERROR 等）

3) Strava 相关
   - `STRAVA_TIMEOUT`：调用 Strava API 的超时时间（秒），默认 10

用法建议：
- 本地开发：在 shell 中临时导出环境变量，或在启动脚本中写死；
- 生产环境：统一由部署平台注入环境变量（Docker/K8s/进程管理器）。
"""

import os
from urllib.parse import quote_plus


def _is_cache_enabled_from_file() -> bool:
    """
    读取仓库根目录的 `.cache_config`，以兼容历史切换逻辑。

    文件格式示例：
        enabled=true  或  enabled=false

    返回：
        True/False，若文件不存在或读取/解析异常，则返回 False
    """
    try:
        if os.path.exists('.cache_config'):
            with open('.cache_config', 'r') as f:
                content = f.read().strip().lower()
                return 'enabled=true' in content
    except Exception:
        pass
    return False


# 日志（Logging）
# LOG_LEVEL 用于控制 logging 的根等级，详见 app/logging_config.py
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# 缓存（Cache）
# CACHE_DIR 为持久化缓存文件的根目录（活动聚合结果落盘路径）
CACHE_DIR = os.environ.get('CACHE_DIR', os.path.join(os.getcwd(), 'data', 'activity_cache'))

def is_cache_enabled() -> bool:
    """
    统一判断是否启用缓存。
    读取顺序：
        1. 环境变量 CACHE_ENABLED（优先）
        2. 本地 .cache_config 文件（兼容历史开关）
        3. 默认启用（True）

    注意：之前的实现用了 `_is_cache_enabled_from_file() or True`，
    会导致当文件为 `enabled=false` 时仍返回 True。这里修正为：
    若文件存在则按文件值返回；否则才回退 True。
    """
    env_val = os.environ.get('CACHE_ENABLED')
    if env_val is not None:
        return env_val.lower() == 'true'
    # 若存在配置文件，按文件值返回；否则默认启用
    if os.path.exists('.cache_config'):
        return _is_cache_enabled_from_file()
    return True


# Strava 调用配置
# STRAVA_TIMEOUT 为单次 HTTP 请求超时（秒）
STRAVA_TIMEOUT = int(os.environ.get('STRAVA_TIMEOUT', '10'))


# 数据库（Database）
def get_database_url() -> str:
    """
    获取数据库连接 URL。

    优先读取完整的 `DATABASE_URL`，示例：
        mysql+pymysql://user:pass@127.0.0.1:3306/ry-system

    若未设置，则使用拆分变量拼接：
        DB_HOST（默认 127.0.0.1:3306）
        DB_USER（默认 root）
        DB_PASSWORD（默认空串）
        DB_NAME（默认 ry-system）

    返回：
        SQLAlchemy 可识别的数据库连接串。
    """
    # 1) 优先使用完整 URL，便于一次性注入敏感信息
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url

    # 2) 否则从拆分变量拼接（对密码进行 URL 编码）
    host = os.environ.get('DB_HOST', '121.41.238.53:3306')
    user = os.environ.get('DB_USER', 'root')
    password = os.environ.get('DB_PASSWORD', '86230ce6558fd9a1')
    name = os.environ.get('DB_NAME', 'ry-system')
    encoded_password = quote_plus(password)
    return f"mysql+pymysql://{user}:{encoded_password}@{host}/{name}"
