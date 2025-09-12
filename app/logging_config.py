"""
日志初始化（Logging Bootstrap）

说明：
- 统一初始化根日志记录器（root logger），设置格式与日志等级；
- 等级从显式传入 `level` 或环境变量 `LOG_LEVEL` 读取，默认 INFO；
- 建议在 app/main.py 启动时调用一次。
"""

import logging
import os


def setup_logging(level: str = None) -> None:
    """
    初始化全局日志配置。

    参数：
        level: 可选的日志等级（字符串）。若未提供，则读取环境变量 LOG_LEVEL（默认 INFO）。
    """
    log_level = (level or os.environ.get('LOG_LEVEL', 'INFO')).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )
