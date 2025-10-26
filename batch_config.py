# 批量处理运动员43活动的配置文件

# 数据库连接配置
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "password",  # 请修改为实际密码
    "database": "fit_api_db"
}

# API服务器配置
API_CONFIG = {
    "base_url": "http://localhost:8000",
    "access_token": "5a173da68c14d5a5598477e617bd0349f6ae11ac"
}

# 处理配置
PROCESSING_CONFIG = {
    "delay_seconds": 1.0,  # 每次请求间隔时间（秒）
    "timeout_seconds": 60,  # 请求超时时间（秒）
    "max_activities": None,  # 最大处理活动数，None表示处理所有
    "athlete_id": 43  # 目标运动员ID
}
