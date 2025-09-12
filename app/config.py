"""
Centralized configuration for the FIT API service.

- Reads database and cache configuration from environment variables
  to avoid hard-coded credentials.
"""

import os
from urllib.parse import quote_plus


def _is_cache_enabled_from_file() -> bool:
    try:
        if os.path.exists('.cache_config'):
            with open('.cache_config', 'r') as f:
                content = f.read().strip().lower()
                return 'enabled=true' in content
    except Exception:
        pass
    return False


# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# Cache
CACHE_DIR = os.environ.get('CACHE_DIR', os.path.join(os.getcwd(), 'data', 'activity_cache'))

def is_cache_enabled() -> bool:
    env_val = os.environ.get('CACHE_ENABLED')
    if env_val is not None:
        return env_val.lower() == 'true'
    # fallback to .cache_config file switch
    return _is_cache_enabled_from_file() or True


# Strava
STRAVA_TIMEOUT = int(os.environ.get('STRAVA_TIMEOUT', '10'))


# Database
def get_database_url() -> str:
    # Prefer a fully-formed DATABASE_URL if provided
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url

    # Or build from parts
    host = os.environ.get('DB_HOST', '127.0.0.1:3306')
    user = os.environ.get('DB_USER', 'root')
    password = os.environ.get('DB_PASSWORD', '')
    name = os.environ.get('DB_NAME', 'ry-system')
    encoded_password = quote_plus(password)
    return f"mysql+pymysql://{user}:{encoded_password}@{host}/{name}"

