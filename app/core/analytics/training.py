from typing import Optional


def calculate_training_load(avg_power: int, ftp: int, duration_seconds: int) -> int:
    if not ftp or ftp <= 0 or not avg_power or avg_power <= 0 or duration_seconds <= 0:
        return 0
    intensity_factor = avg_power / ftp
    duration_hours = duration_seconds / 3600.0
    training_load = (intensity_factor ** 2) * duration_hours
    return int(training_load * 100)


def estimate_calories_with_power(avg_power: int, duration_seconds: int, weight_kg: int) -> Optional[int]:
    try:
        # Simplified: power (W) over time + small BMR component
        power_calories = avg_power * duration_seconds / 3600  # Wh approx to kcal (roughly comparable)
        bmr_per_minute = 1.2
        bmr_calories = bmr_per_minute * duration_seconds / 60
        total = power_calories + bmr_calories
        return int(total)
    except Exception:
        return None


def estimate_calories_with_heartrate(avg_heartrate: int, duration_seconds: int, weight_kg: int) -> Optional[int]:
    try:
        # Keytel-like rough estimate for moderate intensity (male, approximated constants)
        return round((duration_seconds / 60) * (0.6309 * avg_heartrate + 0.1988 * weight_kg + 6 - 55.0969) / 4.184, 0)
    except Exception:
        return None

