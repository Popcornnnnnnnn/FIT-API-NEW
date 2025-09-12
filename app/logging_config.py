import logging
import os


def setup_logging(level: str = None) -> None:
    """Setup root logger with a simple, consistent format.

    Args:
        level: Optional logging level name. If not provided, reads LOG_LEVEL or defaults to INFO.
    """
    log_level = (level or os.environ.get('LOG_LEVEL', 'INFO')).upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
    )

