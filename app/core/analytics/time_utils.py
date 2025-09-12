from typing import Optional


def format_time(seconds: int) -> Optional[str]:
    try:
        seconds = int(seconds)
        if seconds < 0:
            seconds = 0
        if seconds < 60:
            return f"{seconds}s"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours == 0:
            return f"{minutes}:{secs:02d}"
        return f"{hours}:{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return None

