from typing import List


def elevation_gain(altitude_data: List[float]) -> float:
    filtered = []
    for alt in altitude_data:
        if alt is None:
            continue
        if alt > 5000 or alt < -500:
            continue
        if filtered and abs(alt - filtered[-1]) > 100:
            continue
        filtered.append(alt)
    if len(filtered) < 2:
        return 0.0
    gain = 0.0
    for i in range(1, len(filtered)):
        d = filtered[i] - filtered[i - 1]
        if d > 0:
            gain += d
    return gain


def total_descent(altitude_data: List[int]) -> int:
    if not altitude_data:
        return 0
    total = 0.0
    descending = False
    start_alt = altitude_data[0]
    min_alt = altitude_data[0]
    for i in range(1, len(altitude_data)):
        prev, curr = altitude_data[i - 1], altitude_data[i]
        if curr < prev:
            if not descending:
                descending = True
                start_alt = prev
                min_alt = curr
            else:
                if curr < min_alt:
                    min_alt = curr
        else:
            if descending:
                total += start_alt - min_alt
                descending = False
    if descending:
        total += start_alt - min_alt
    return int(total)


def max_grade_percent(altitude: List[int], distance: List[float], interval_points: int = 5, min_distance_interval: float = 50.0) -> float:
    if not altitude or not distance:
        return 0.0
    n = min(len(altitude), len(distance))
    max_grade = 0.0
    for i in range(interval_points, n):
        a0, a1 = altitude[i - interval_points], altitude[i]
        d0, d1 = distance[i - interval_points], distance[i]
        if a0 is None or a1 is None or d0 is None or d1 is None:
            continue
        delta_alt = a1 - a0
        delta_dis = d1 - d0
        if delta_dis > min_distance_interval and delta_dis < 1000:
            g = (delta_alt / delta_dis) * 100.0
            if abs(g) <= 50:
                max_grade = max(max_grade, abs(g))
    return round(max_grade, 2)


def uphill_downhill_distance_km(altitude: List[int], distance: List[float], interval_points: int = 5, min_distance_interval: float = 50.0) -> (float, float):
    if not altitude or not distance:
        return 0.0, 0.0
    n = min(len(altitude), len(distance))
    uphill = 0.0
    downhill = 0.0
    for i in range(interval_points, n):
        a0, a1 = altitude[i - interval_points], altitude[i]
        d0, d1 = distance[i - interval_points], distance[i]
        if a0 is None or a1 is None or d0 is None or d1 is None:
            continue
        delta_alt = a1 - a0
        delta_dis = d1 - d0
        if delta_alt > 1 and delta_dis > min_distance_interval:
            uphill += delta_dis
        if delta_alt < -1 and delta_dis > min_distance_interval:
            downhill += delta_dis
    return round(uphill / 1000.0, 2), round(downhill / 1000.0, 2)

