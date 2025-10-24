"""Utilities to aggregate stream data into zone-based histogram payloads."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple, Union

from .time_utils import format_time

MetricType = Literal["power", "heart_rate"]

POWER_ZONES: List[Tuple[str, str, float, float]] = [
    ("Z1", "Active Recovery", 0.00, 0.55),
    ("Z2", "Endurance", 0.55, 0.75),
    ("Z3", "Tempo", 0.75, 0.90),
    ("Z4", "Threshold", 0.90, 1.05),
    ("Z5", "VO2max", 1.05, 1.20),
    ("Z6", "Anaerobic Capacity", 1.20, 1.50),
    ("Z7", "Neuromuscular", 1.50, math.inf),
]

HEARTRATE_ZONES: List[Tuple[str, str, float, float]] = [
    ("Z1", "Recovery", 0.00, 0.85),
    ("Z2", "Aerobic", 0.85, 0.90),
    ("Z3", "Tempo", 0.90, 0.95),
    ("Z4", "Sub-threshold", 0.95, 1.00),
    ("Z5", "Super-threshold", 1.00, 1.03),
    ("Z6", "Aerobic Capacity", 1.03, 1.06),
    ("Z7", "Anaerobic", 1.06, math.inf),
]


def _prepare_power_zones(ftp: int) -> List[Dict[str, Any]]:
    if not ftp or ftp <= 0:
        raise ValueError("ftp must be a positive integer to compute power zones.")

    zones: List[Dict[str, Any]] = []
    previous_max: Optional[int] = None
    for zone_id, label, low_ratio, high_ratio in POWER_ZONES:
        min_value = 0 if low_ratio == 0 else int(round(ftp * low_ratio))
        if previous_max is not None and min_value < previous_max:
            min_value = previous_max

        if math.isinf(high_ratio):
            max_value: Optional[int] = None
            high_ratio_val: Optional[float] = None
        else:
            max_value = int(round(ftp * high_ratio))
            if max_value <= min_value:
                max_value = min_value + 1
            high_ratio_val = high_ratio

        zones.append(
            {
                "zone": zone_id,
                "label": label,
                "min_value": min_value,
                "max_value": max_value,
                "low_ratio": low_ratio,
                "high_ratio": high_ratio_val,
                "unit": "W",
            }
        )
        previous_max = max_value if max_value is not None else min_value
    return zones


def _prepare_heartrate_zones(lthr: int, max_hr: Optional[int]) -> List[Dict[str, Any]]:
    if not lthr or lthr <= 0:
        raise ValueError("lthr must be a positive integer to compute heart rate zones.")
    if max_hr is not None and max_hr < lthr:
        raise ValueError("max_hr should be greater than or equal to lthr.")

    zones: List[Dict[str, Any]] = []
    previous_max: Optional[int] = None
    for zone_id, label, low_ratio, high_ratio in HEARTRATE_ZONES:
        min_value = 0 if low_ratio == 0 else int(round(lthr * low_ratio))
        if previous_max is not None and min_value < previous_max:
            min_value = previous_max

        if math.isinf(high_ratio):
            max_value: Optional[int] = max_hr
            high_ratio_val: Optional[float] = None
        else:
            max_value = int(round(lthr * high_ratio))
            if previous_max is not None and max_value <= previous_max:
                max_value = previous_max + 1
            high_ratio_val = high_ratio
        zones.append(
            {
                "zone": zone_id,
                "label": label,
                "min_value": min_value,
                "max_value": max_value,
                "low_ratio": low_ratio,
                "high_ratio": high_ratio_val,
                "unit": "bpm",
            }
        )
        previous_max = max_value if max_value is not None else min_value
    return zones


def _clean_value(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or value <= 0:
        return None
    return value


def generate_zone_histogram_payload(
    stream: Sequence[Any],
    metric: MetricType,
    *,
    ftp: Optional[int] = None,
    lthr: Optional[int] = None,
    max_hr: Optional[int] = None,
    sample_interval: float = 1.0,
) -> Dict[str, Any]:
    """Aggregate stream data into a 7-zone histogram structure.

    Args:
        stream: Iterable sequence of numeric values (per-sample power or heart rate).
        metric: Either ``"power"`` or ``"heart_rate"``.
        ftp: Functional threshold power (required when ``metric`` is ``"power"``).
        lthr: Lactate threshold heart rate (required when ``metric`` is ``"heart_rate"``).
        max_hr: Maximum heart rate used to cap the last zone (optional but recommended).
        sample_interval: Interval between successive samples in seconds (default 1s).

    Returns:
        A dictionary containing ``chart`` data (category labels & values) and a
        per-zone breakdown that can be fed directly to a charting library.

    Raises:
        ValueError: When mandatory parameters for the chosen metric are missing.
    """

    if sample_interval <= 0:
        sample_interval = 1.0

    if metric == "power":
        zones = _prepare_power_zones(ftp if ftp is not None else 0)
        threshold_value = ftp
    elif metric == "heart_rate":
        zones = _prepare_heartrate_zones(
            lthr if lthr is not None else 0,
            max_hr,
        )
        threshold_value = lthr
    else:
        raise ValueError("metric must be 'power' or 'heart_rate'.")

    if threshold_value is None or threshold_value <= 0:
        raise ValueError("Missing threshold reference for metric aggregation.")

    zone_counts = [0 for _ in zones]
    total_samples = 0
    ignored_samples = 0

    for raw in stream:
        value = _clean_value(raw)
        if value is None:
            ignored_samples += 1
            continue
        total_samples += 1
        ratio = value / threshold_value
        assigned = False
        for idx, zone in enumerate(zones):
            low = zone["low_ratio"]
            high_ratio = zone["high_ratio"]
            upper = high_ratio if high_ratio is not None else float("inf")
            if low <= ratio < upper:
                zone_counts[idx] += 1
                assigned = True
                break
        if not assigned:
            zone_counts[-1] += 1  # fallback to final zone

    total_duration_seconds = total_samples * sample_interval
    zone_payload: List[Dict[str, Any]] = []
    chart_values: List[float] = []
    chart_labels: List[str] = []
    chart_tooltips: List[str] = []

    for idx, zone in enumerate(zones):
        samples = zone_counts[idx]
        duration_seconds = samples * sample_interval
        duration_minutes = duration_seconds / 60.0
        percentage = (samples / total_samples * 100.0) if total_samples else 0.0

        min_value = zone["min_value"]
        max_value = zone["max_value"]
        unit = zone["unit"]
        if max_value is None:
            range_display = f">= {min_value} {unit}"
        else:
            if max_value == min_value:
                range_display = f"{min_value} {unit}"
            else:
                range_display = f"{min_value}–{max_value} {unit}"

        zone_payload.append(
            {
                "zone": zone["zone"],
                "label": zone["label"],
                "range": range_display,
                "min_value": min_value,
                "max_value": max_value,
                "samples": samples,
                "duration_seconds": duration_seconds,
                "duration_minutes": round(duration_minutes, 2),
                "percentage": round(percentage, 2),
                "formatted_duration": format_time(int(round(duration_seconds))) or "0s",
            }
        )

        chart_labels.append(zone["zone"])
        chart_values.append(round(duration_minutes, 2))
        chart_tooltips.append(
            f"{zone['zone']} • {zone['label']} • {round(percentage, 1)}% • {format_time(int(round(duration_seconds))) or '0s'}"
        )

    return {
        "metric": metric,
        "total_samples": total_samples,
        "ignored_samples": ignored_samples,
        "sample_interval": sample_interval,
        "total_duration_seconds": total_duration_seconds,
        "chart": {
            "type": "bar",
            "unit": "minutes",
            "categories": chart_labels,
            "values": chart_values,
            "tooltips": chart_tooltips,
        },
        "zones": zone_payload,
    }


ZONE_COLORS: Dict[str, str] = {
    "Z1": "#4CAF50",
    "Z2": "#FFB74D",
    "Z3": "#FF8A65",
    "Z4": "#FF5252",
    "Z5": "#AB47BC",
    "Z6": "#5C6BC0",
    "Z7": "#424242",
}

ZONE_HEIGHT_RANGES: Dict[str, Tuple[float, float]] = {
    "Z1": (0.12, 0.32),
    "Z2": (0.32, 0.48),
    "Z3": (0.48, 0.62),
    "Z4": (0.62, 0.78),
    "Z5": (0.78, 0.88),
    "Z6": (0.88, 0.97),
    "Z7": (0.95, 1.05),
}


def _calculate_segment_height(segment: Dict[str, Any], reference_value: float) -> Tuple[float, float]:
    avg_value = segment.get("avg_value", 0.0)
    avg_ratio = segment.get("avg_ratio", 0.0)
    if reference_value > 0 and avg_value > 0:
        avg_ratio = avg_value / reference_value
    low_ratio = segment.get("low_ratio", 0.0)
    high_ratio = segment.get("high_ratio")
    range_min, range_max = ZONE_HEIGHT_RANGES.get(segment.get("zone", ""), (0.2, 0.9))
    if high_ratio is None:
        normalized = 1.0 if avg_ratio >= low_ratio else 0.0
    else:
        denom = high_ratio - low_ratio
        if denom <= 0:
            normalized = 1.0
        else:
            normalized = (avg_ratio - low_ratio) / denom
            normalized = max(0.0, min(1.0, normalized))
    height = range_min + normalized * (range_max - range_min)
    height = max(height, 0.02)
    return height, avg_ratio


def build_zone_segment_visuals(payload: Dict[str, Any], metric: MetricType) -> List[Dict[str, Any]]:
    reference_value = payload.get("reference_value") or 0.0
    visuals: List[Dict[str, Any]] = []
    for segment in payload.get("segments", []):
        height, ratio = _calculate_segment_height(segment, reference_value)
        visuals.append(
            {
                "metric": metric,
                "zone": segment.get("zone"),
                "label": segment.get("label"),
                "start_time": segment.get("start_time", 0.0),
                "end_time": segment.get("end_time", 0.0),
                "duration_seconds": segment.get("duration_seconds", 0.0),
                "height": height,
                "intensity_ratio": ratio,
                "average_value": segment.get("avg_value", 0.0),
            }
        )
    return visuals


def generate_zone_segments_payload(
    stream: Sequence[Any],
    metric: MetricType,
    *,
    ftp: Optional[int] = None,
    lthr: Optional[int] = None,
    max_hr: Optional[int] = None,
    sample_interval: float = 1.0,
    min_segment_seconds: float = 5.0,
) -> Dict[str, Any]:
    """Compress the raw stream into contiguous zone segments for step-style charts.

    Groups consecutive samples that fall in the same zone so that the caller can
    render a bar/step chart following the original curve trend without being
    overloaded by per-sample bars.
    """

    if sample_interval <= 0:
        sample_interval = 1.0

    if metric == "power":
        zones = _prepare_power_zones(ftp if ftp is not None else 0)
        threshold_value = ftp
    elif metric == "heart_rate":
        zones = _prepare_heartrate_zones(
            lthr if lthr is not None else 0,
            max_hr,
        )
        threshold_value = lthr
    else:
        raise ValueError("metric must be 'power' or 'heart_rate'.")

    if threshold_value is None or threshold_value <= 0:
        raise ValueError("Missing threshold reference for metric aggregation.")

    min_segment_samples = max(1, int(round(min_segment_seconds / sample_interval)))

    segments: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    total_samples = 0
    ignored_samples = 0

    def close_current() -> None:
        nonlocal current
        if current is not None:
            segments.append(current)
            current = None

    for index, raw in enumerate(stream):
        value = _clean_value(raw)
        if value is None:
            ignored_samples += 1
            close_current()
            continue
        total_samples += 1
        ratio = value / threshold_value
        zone_idx: Optional[int] = None
        for idx, zone in enumerate(zones):
            upper_ratio = zone["high_ratio"]
            upper = upper_ratio if upper_ratio is not None else float("inf")
            if zone["low_ratio"] <= ratio < upper:
                zone_idx = idx
                break
        if zone_idx is None:
            zone_idx = len(zones) - 1

        if current and current["zone_index"] == zone_idx:
            current["end_index"] = index
            current["sample_count"] += 1
            current["value_sum"] += value
        else:
            close_current()
            current = {
                "zone_index": zone_idx,
                "start_index": index,
                "end_index": index,
                "sample_count": 1,
                "value_sum": value,
            }

    close_current()

    # Merge very short segments into neighbours to avoid overly dense bars.
    merged: List[Dict[str, Any]] = []
    total_segment_count = len(segments)
    for idx, segment in enumerate(segments):
        if segment["sample_count"] < min_segment_samples and total_segment_count > 1:
            prev = merged[-1] if merged else None
            next_segment = segments[idx + 1] if idx + 1 < total_segment_count else None

            if prev and prev["zone_index"] == segment["zone_index"]:
                prev["end_index"] = segment["end_index"]
                prev["sample_count"] += segment["sample_count"]
                prev["value_sum"] += segment["value_sum"]
                continue

            if next_segment and next_segment["zone_index"] == segment["zone_index"]:
                next_segment["start_index"] = segment["start_index"]
                next_segment["sample_count"] += segment["sample_count"]
                next_segment["value_sum"] += segment["value_sum"]
                continue

            if prev:
                prev["end_index"] = segment["end_index"]
                prev["sample_count"] += segment["sample_count"]
                prev["value_sum"] += segment["value_sum"]
                continue

            if next_segment:
                next_segment["start_index"] = segment["start_index"]
                next_segment["sample_count"] += segment["sample_count"]
                next_segment["value_sum"] += segment["value_sum"]
                continue

        merged.append(segment)

    final_segments: List[Dict[str, Any]] = merged

    payload_segments: List[Dict[str, Any]] = []
    for seg in final_segments:
        zone = zones[seg["zone_index"]]
        samples = seg["sample_count"]
        duration_seconds = samples * sample_interval
        start_time = seg["start_index"] * sample_interval
        end_time = (seg["end_index"] + 1) * sample_interval
        avg_value = seg["value_sum"] / samples if samples else 0.0
        avg_ratio = avg_value / threshold_value if threshold_value else 0.0
        payload_segments.append(
            {
                "zone": zone["zone"],
                "label": zone["label"],
                "color": ZONE_COLORS.get(zone["zone"], "#999999"),
                "start_index": seg["start_index"],
                "end_index": seg["end_index"],
                "start_time": start_time,
                "end_time": end_time,
                "duration_seconds": duration_seconds,
                "formatted_duration": format_time(int(round(duration_seconds))) or "0s",
                "range": (
                    f"{zone['min_value']}–{zone['max_value']} {zone['unit']}"
                    if zone["max_value"] is not None
                    else f">= {zone['min_value']} {zone['unit']}"
                ),
                "avg_value": avg_value,
                "avg_ratio": avg_ratio,
                "low_ratio": zone["low_ratio"],
                "high_ratio": zone["high_ratio"],
            }
        )

    return {
        "metric": metric,
        "sample_interval": sample_interval,
        "total_samples": total_samples,
        "ignored_samples": ignored_samples,
        "total_duration_seconds": total_samples * sample_interval,
        "reference_value": threshold_value,
        "segments": payload_segments,
        "zones": [
            {
                "zone": zone["zone"],
                "label": zone["label"],
                "color": ZONE_COLORS.get(zone["zone"], "#999999"),
                "range": (
                    f"{zone['min_value']}–{zone['max_value']} {zone['unit']}"
                    if zone["max_value"] is not None
                    else f">= {zone['min_value']} {zone['unit']}"
                ),
                "min_value": zone["min_value"],
                "max_value": zone["max_value"],
                "low_ratio": zone["low_ratio"],
                "high_ratio": zone["high_ratio"],
            }
            for zone in zones
        ],
    }


def render_zone_segments_chart(
    stream: Sequence[Any],
    metric: MetricType,
    output_path: Union[str, "os.PathLike[str]"],
    *,
    ftp: Optional[int] = None,
    lthr: Optional[int] = None,
    max_hr: Optional[int] = None,
    sample_interval: float = 1.0,
    min_segment_seconds: float = 5.0,
    figsize: Tuple[float, float] = (10.0, 1.8),
    dpi: int = 160,
    precomputed_payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Render a horizontal stacked chart of zone segments and save to file."""
    payload = precomputed_payload or generate_zone_segments_payload(
        stream,
        metric,
        ftp=ftp,
        lthr=lthr,
        max_hr=max_hr,
        sample_interval=sample_interval,
        min_segment_seconds=min_segment_seconds,
    )
    segments = payload["segments"]
    total_duration = payload["total_duration_seconds"] or sample_interval
    reference_value = payload.get("reference_value") or 0.0

    from pathlib import Path
    import os

    output_path = Path(output_path)
    cache_dir = output_path.parent / ".mpl-cache"
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.set_facecolor("#f8f9fb")

    baseline = 0.0
    for seg in segments:
        width = seg["end_time"] - seg["start_time"]
        if width <= 0:
            continue
        height, _ = _calculate_segment_height(seg, reference_value)
        rect = Rectangle(
            (seg["start_time"], baseline),
            width,
            height,
            facecolor=seg["color"],
            edgecolor="none",
        )
        ax.add_patch(rect)

    ax.axhline(
        1.02,
        color="#b0b8c5",
        linewidth=1.0,
        linestyle=(0, (4, 4)),
    )

    ax.set_xlim(0, total_duration)
    ax.set_ylim(0, 1.1)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout(pad=0.2)
    fig.savefig(output_path, bbox_inches="tight", transparent=False)
    plt.close(fig)
    return str(output_path)
