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


def parse_time_str(time_str: str) -> int:
    """Parse a time string like "45s", "mm:ss" or "hh:mm:ss" into seconds.

    Returns 0 if parsing fails.
    """
    try:
        s = (time_str or '').strip()
        if s.endswith('s'):
            return int(s[:-1])
        if ':' in s:
            parts = s.split(':')
            if len(parts) == 2:
                m, sec = int(parts[0]), int(parts[1])
                return m * 60 + sec
            if len(parts) == 3:
                h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
                return h * 3600 + m * 60 + sec
        return 0
    except Exception:
        return 0
