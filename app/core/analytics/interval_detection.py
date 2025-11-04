"""Interval detection utilities for cycling activities.

This module implements a multi-stage pipeline that operates on 1 Hz power and
heart-rate series.  The logic is shared between FIT ingestion and Strava
streams, and ultimately returns fully classified intervals covering the entire
activity duration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


@dataclass
class IntervalDetectionConfig:
    """Configuration knobs controlling the detection pipeline."""

    fast_window: int = 7      # 5–9 s moving average (fast channel)
    slow_window: int = 30     # 25–35 s moving average (slow channel)
    baseline_window: int = 150  # 150 s rolling median
    start_hysteresis: int = 5
    stop_hysteresis: int = 9
    merge_gap: int = 10
    merge_ratio_delta: float = 0.10
    sprint_ratio: float = 1.5
    sprint_duration: int = 6
    sprint_peak_ratio: float = 1.8
    sprint_peak_duration: int = 3
    zero_fill_window: int = 3


@dataclass
class IntervalSummary:
    start: int
    end: int
    classification: str
    average_power: float
    peak_power: float
    normalized_power: float
    intensity_factor: float
    power_ratio: float
    time_above_95: float
    time_above_106: float
    time_above_120: float
    time_above_150: float
    heart_rate_avg: Optional[float]
    heart_rate_max: Optional[int]
    heart_rate_slope: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> int:
        return self.end - self.start


@dataclass
class RepeatBlock:
    start: int
    end: int
    cycles: List[Dict[str, Any]]

    @property
    def classification(self) -> str:
        return "z2-z1-repeats"


@dataclass
class IntervalDetectionResult:
    duration: int
    ftp: float
    intervals: List[IntervalSummary]
    repeats: List[RepeatBlock]


def detect_intervals(
    timestamps: Sequence[int],
    power: Sequence[Optional[float]],
    ftp: Optional[float],
    heart_rate: Optional[Sequence[Optional[float]]] = None,
    cadence: Optional[Sequence[Optional[float]]] = None,
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
    config: Optional[IntervalDetectionConfig] = None,
) -> IntervalDetectionResult:
    if not ftp or ftp <= 0:
        return IntervalDetectionResult(duration=0, ftp=0.0, intervals=[], repeats=[])

    cfg = config or IntervalDetectionConfig()
    ts, pw, hr = _prepare_inputs(timestamps, power, heart_rate, cfg)
    if not pw.size:
        return IntervalDetectionResult(duration=0, ftp=float(ftp), intervals=[], repeats=[])

    duration = int(ts[-1]) if ts.size else int(pw.size)
    fast, slow = _compute_channels(pw, cfg)
    baseline = _rolling_median(slow, cfg.baseline_window)
    theta = _compute_theta(fast, baseline, ftp)
    raw_segments = _segment_intervals(fast, slow, baseline, theta, ftp, cfg)
    sprint_segments = _detect_sprint_overrides(pw, ftp, cfg)
    candidates = _merge_and_adjust_segments(raw_segments + sprint_segments, pw, slow, ftp, cfg)
    ratio_segments = _detect_ratio_segments(slow, candidates, ftp)

    interval_summaries = [
        _summarize_interval(seg, pw, hr, ftp, lthr, hr_max)
        for seg in candidates
        if seg[1] - seg[0] >= 3
    ]
    for start, end, label in ratio_segments:
        summary = _summarize_interval((start, end), pw, hr, ftp, lthr, hr_max)
        summary.classification = label
        meta = dict(summary.metadata)
        meta['source'] = 'ratio'
        summary.metadata = meta
        interval_summaries.append(summary)

    classified = [
        summary
        for summary in (
            _classify_interval(summary, ftp)
            for summary in interval_summaries
        )
    ]

    coverage = np.full(pw.size, "", dtype=object)
    priority = {
        "recovery": 0,
        "endurance": 1,
        "tempo": 2,
        "threshold": 3,
        "vo2max": 4,
        "anaerobic": 5,
        "sprint": 6,
    }

    def _assign_segment(start: int, end: int, label: str) -> None:
        if label not in priority:
            return
        s = max(0, int(start))
        e = min(int(end), pw.size)
        if s >= e:
            return
        for idx in range(s, e):
            current = coverage[idx]
            if not current or priority[label] >= priority.get(current, -1):
                coverage[idx] = label

    for summary in classified:
        _assign_segment(summary.start, summary.end, summary.classification)

    ratios = pw / ftp if ftp else np.zeros_like(pw)
    for idx, label in enumerate(coverage):
        if label:
            continue
        coverage[idx] = _classification_from_ratio(float(ratios[idx]))

    segments = _build_segments_from_coverage(coverage)
    ratios = pw / ftp if ftp else np.zeros_like(pw)
    segments = _simplify_segments(segments, ratios, default_min_length=30)

    final_intervals: List[IntervalSummary] = []
    for start, end, label in segments:
        summary = _summarize_interval((start, end), pw, hr, ftp, lthr, hr_max)
        summary.classification = label
        final_intervals.append(summary)

    repeats = _detect_z2_z1_repeats(pw, ftp, ts)

    return IntervalDetectionResult(
        duration=duration,
        ftp=float(ftp),
        intervals=final_intervals,
        repeats=repeats,
    )


def _prepare_inputs(
    timestamps: Sequence[int],
    power: Sequence[Optional[float]],
    heart_rate: Optional[Sequence[Optional[float]]],
    cfg: IntervalDetectionConfig,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
    if timestamps is None or power is None:
        return np.array([]), np.array([]), None
    if len(timestamps) == 0 or len(power) == 0:
        return np.array([]), np.array([]), None

    ts = np.asarray(timestamps, dtype=int)
    if ts.ndim != 1:
        ts = ts.flatten()
    order = np.argsort(ts)
    ts = ts[order]

    pw_raw = np.asarray(power, dtype=float)
    if pw_raw.ndim != 1:
        pw_raw = pw_raw.flatten()
    pw_raw = pw_raw[order[: pw_raw.shape[0]]]

    if ts.size == pw_raw.size and np.all(np.diff(ts) <= 1):
        timeline = ts
        pw_series = pw_raw
    else:
        timeline, pw_series = _resample_to_1hz(ts, pw_raw)

    pw_series = np.clip(pw_series, 0, 1600)
    pw_series = _fill_short_zero_gaps(pw_series, cfg.zero_fill_window)

    hr_series = None
    if heart_rate:
        raw = np.asarray(list(heart_rate), dtype=float)
        raw = raw[order[: raw.shape[0]]] if raw.size else raw
        if raw.size == timeline.size:
            hr_series = raw
        else:
            hr_series = _resample_auxiliary(timeline, ts, raw)

    return timeline, pw_series, hr_series


def _resample_to_1hz(
    timestamps: np.ndarray,
    series: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    if not timestamps.size:
        return np.array([]), np.array([])
    start, end = int(timestamps[0]), int(timestamps[-1])
    timeline = np.arange(start, end + 1)
    mapping: Dict[int, float] = {}
    for ts, val in zip(timestamps, series):
        if math.isnan(val):
            continue
        mapping[int(ts)] = float(val)
    filled = np.zeros_like(timeline, dtype=float)
    last = 0.0
    for idx, sec in enumerate(timeline):
        if sec in mapping:
            last = mapping[sec]
        filled[idx] = last
    return timeline, filled


def _resample_auxiliary(
    target_ts: np.ndarray,
    original_ts: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    mapping: Dict[int, float] = {}
    for ts, val in zip(original_ts, values):
        if math.isnan(val):
            continue
        mapping[int(ts)] = float(val)
    filled = np.zeros_like(target_ts, dtype=float)
    last = np.nan
    for idx, sec in enumerate(target_ts):
        if sec in mapping:
            last = mapping[sec]
        filled[idx] = last if not math.isnan(last) else 0.0
    return filled


def _fill_short_zero_gaps(series: np.ndarray, max_len: int) -> np.ndarray:
    result = series.copy()
    zero_start = None
    for idx, val in enumerate(result):
        if val <= 1e-6:
            if zero_start is None:
                zero_start = idx
        else:
            if zero_start is not None:
                length = idx - zero_start
                if 0 < length <= max_len:
                    fill_val = result[zero_start - 1] if zero_start > 0 else result[idx]
                    result[zero_start:idx] = fill_val
            zero_start = None
    return result


def _compute_channels(series: np.ndarray, cfg: IntervalDetectionConfig) -> Tuple[np.ndarray, np.ndarray]:
    fast = _moving_average(series, cfg.fast_window)
    slow = _moving_average(series, cfg.slow_window)
    return fast, slow


def _moving_average(series: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or series.size < window:
        return series.astype(float)
    pad_left = window // 2
    pad_right = window - 1 - pad_left
    padded = np.pad(series, (pad_left, pad_right), mode="edge")
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(padded, kernel, mode="valid")


def _rolling_median(series: np.ndarray, window: int) -> np.ndarray:
    if series.size == 0:
        return np.array([])
    if window <= 1:
        return series.astype(float)
    half = window // 2
    padded = np.pad(series, (half, half), mode="edge")
    medians = np.empty(series.size, dtype=float)
    for idx in range(series.size):
        segment = padded[idx : idx + window]
        medians[idx] = float(np.median(segment))
    return medians


def _compute_theta(fast: np.ndarray, baseline: np.ndarray, ftp: float) -> float:
    residual = fast - baseline
    sigma = float(np.std(residual)) if residual.size else 0.0
    return max(0.2 * ftp, 0.75 * sigma)


def _segment_intervals(
    fast: np.ndarray,
    slow: np.ndarray,
    baseline: np.ndarray,
    theta: float,
    ftp: float,
    cfg: IntervalDetectionConfig,
) -> List[Tuple[int, int]]:
    if fast.size == 0:
        return []
    E = fast - (baseline + theta)
    ratio = slow / ftp if ftp else np.zeros_like(slow)
    start_idx: Optional[int] = None
    pos_count = 0
    neg_count = 0
    segments: List[Tuple[int, int]] = []
    for idx, value in enumerate(E):
        if start_idx is None:
            if value > 0:
                pos_count += 1
                if pos_count >= cfg.start_hysteresis:
                    start_idx = idx - cfg.start_hysteresis + 1
                    neg_count = 0
            else:
                pos_count = 0
        else:
            if value < -0.5 * theta and ratio[idx] < 0.85:
                neg_count += 1
                if neg_count >= cfg.stop_hysteresis:
                    end_idx = idx - cfg.stop_hysteresis + 1
                    if end_idx > start_idx:
                        segments.append((start_idx, end_idx))
                    start_idx = None
                    pos_count = 0
                    neg_count = 0
            else:
                neg_count = 0
    if start_idx is not None:
        segments.append((start_idx, fast.size - 1))
    return segments


def _detect_sprint_overrides(
    power: np.ndarray,
    ftp: float,
    cfg: IntervalDetectionConfig,
) -> List[Tuple[int, int]]:
    segments: List[Tuple[int, int]] = []
    n = power.size
    idx = 0
    while idx < n:
        if power[idx] >= cfg.sprint_ratio * ftp:
            start = idx
            high_counter = 0
            peak_counter = 0
            while idx < n and power[idx] >= 0.8 * ftp:
                if power[idx] >= cfg.sprint_ratio * ftp:
                    high_counter += 1
                if power[idx] >= cfg.sprint_peak_ratio * ftp:
                    peak_counter += 1
                idx += 1
            end = idx
            if high_counter >= cfg.sprint_duration or peak_counter >= cfg.sprint_peak_duration:
                segments.append((start, end))
        else:
            idx += 1
    return segments


def _merge_and_adjust_segments(
    segments: List[Tuple[int, int]],
    power: np.ndarray,
    slow_channel: np.ndarray,
    ftp: float,
    cfg: IntervalDetectionConfig,
) -> List[Tuple[int, int]]:
    if not segments:
        return []
    segments = sorted(segments, key=lambda x: x[0])
    merged: List[Tuple[int, int]] = []
    curr_start, curr_end = segments[0]

    def _segment_mean(start: int, end: int) -> float:
        return float(np.mean(power[start:end])) if end > start else 0.0

    for start, end in segments[1:]:
        gap = start - curr_end
        mean_curr = _segment_mean(curr_start, curr_end)
        mean_next = _segment_mean(start, end)
        if gap < cfg.merge_gap and abs(mean_curr - mean_next) <= cfg.merge_ratio_delta * ftp:
            curr_end = max(curr_end, end)
        else:
            merged.append((curr_start, curr_end))
            curr_start, curr_end = start, end
    merged.append((curr_start, curr_end))

    adjusted: List[Tuple[int, int]] = []
    for start, end in merged:
        adjusted_start = _tune_boundary(start, -1, slow_channel)
        adjusted_end = _tune_boundary(end, 1, slow_channel)
        adjusted.append((max(0, adjusted_start), min(power.size, adjusted_end)))
    return adjusted


def _tune_boundary(index: int, direction: int, reference: np.ndarray, window: int = 4) -> int:
    idx = index
    candidate = idx
    ref_val = reference[idx] if 0 <= idx < reference.size else None
    for offset in range(1, window + 1):
        test_idx = idx + direction * offset
        if 0 <= test_idx < reference.size:
            test_val = reference[test_idx]
            if ref_val is None or test_val < ref_val:
                ref_val = test_val
                candidate = test_idx
    return candidate


def _detect_ratio_segments(
    slow: np.ndarray,
    existing: List[Tuple[int, int]],
    ftp: float,
) -> List[Tuple[int, int, str]]:
    if slow.size == 0 or not ftp:
        return []
    assigned = np.zeros(slow.size, dtype=bool)
    for start, end in existing:
        assigned[start:end] = True

    ratio = slow / ftp
    definitions = [
        ("anaerobic", 1.21, float("inf"), 1),
        ("vo2max", 1.06, 1.20, 1),
        ("threshold", 0.95, 1.05, 1),
        ("tempo", 0.76, 0.94, 1),
        ("endurance", 0.56, 0.75, 1),
        ("recovery", 0.0, 0.55, 1),
    ]

    segments: List[Tuple[int, int, str]] = []
    unavailable = assigned.copy()
    for label, lower, upper, min_len in definitions:
        eps = 0.01
        mask = (~unavailable) & (ratio >= (lower - eps)) & (ratio <= (upper + eps))
        if not np.any(mask):
            continue
        mask = _fill_short_false(mask, max_gap=5)
        for start, end in _iter_segments(mask, min_len):
            segments.append((start, end, label))
            unavailable[start:end] = True
    return segments


def _fill_short_false(mask: np.ndarray, max_gap: int) -> np.ndarray:
    result = mask.copy()
    gap_start: Optional[int] = None
    for idx, val in enumerate(result):
        if not val:
            if gap_start is None:
                gap_start = idx
        else:
            if gap_start is not None and idx - gap_start <= max_gap:
                result[gap_start:idx] = True
            gap_start = None
    if gap_start is not None and len(result) - gap_start <= max_gap:
        result[gap_start:] = True
    return result


def _iter_segments(mask: np.ndarray, min_length: int) -> List[Tuple[int, int]]:
    segments: List[Tuple[int, int]] = []
    start: Optional[int] = None
    for idx, val in enumerate(mask):
        if val and start is None:
            start = idx
        elif not val and start is not None:
            if idx - start >= min_length:
                segments.append((start, idx))
            start = None
    if start is not None and len(mask) - start >= min_length:
        segments.append((start, len(mask)))
    return segments


def _classification_from_ratio(ratio: float) -> str:
    if ratio >= 1.21:
        return "anaerobic"
    if ratio >= 1.06:
        return "vo2max"
    if ratio >= 0.95:
        return "threshold"
    if ratio >= 0.76:
        return "tempo"
    if ratio >= 0.56:
        return "endurance"
    return "recovery"


def _build_segments_from_coverage(coverage: np.ndarray) -> List[Tuple[int, int, str]]:
    segments: List[Tuple[int, int, str]] = []
    idx = 0
    n = coverage.size
    while idx < n:
        label = coverage[idx] or "recovery"
        start = idx
        idx += 1
        while idx < n and coverage[idx] == label:
            idx += 1
        segments.append((start, idx, label))
    return segments


def _segment_mean_ratio(ratios: np.ndarray, start: int, end: int) -> float:
    if end <= start:
        return 0.0
    return float(np.mean(ratios[start:end]))


def _simplify_segments(
    segments: List[Tuple[int, int, str]],
    ratios: np.ndarray,
    default_min_length: int,
) -> List[Tuple[int, int, str]]:
    if not segments:
        return []

    merged = _merge_adjacent_same_class(segments)

    min_length_map = {
        "recovery": 90,
        "endurance": 75,
        "tempo": 50,
        "threshold": 40,
        "vo2max": 25,
        "anaerobic": 15,
        "sprint": 6,
    }

    changed = True
    while changed and len(merged) > 1:
        changed = False
        i = 0
        while i < len(merged):
            start, end, label = merged[i]
            min_length = min_length_map.get(label, default_min_length)
            if end - start >= min_length or len(merged) == 1:
                i += 1
                continue

            changed = True
            if i == 0:
                next_start, next_end, next_label = merged[1]
                merged[1] = (start, next_end, next_label)
                merged.pop(0)
            elif i == len(merged) - 1:
                prev_start, prev_end, prev_label = merged[i - 1]
                merged[i - 1] = (prev_start, end, prev_label)
                merged.pop()
            else:
                prev_start, prev_end, prev_label = merged[i - 1]
                next_start, next_end, next_label = merged[i + 1]
                short_mean = _segment_mean_ratio(ratios, start, end)
                prev_mean = _segment_mean_ratio(ratios, prev_start, prev_end)
                next_mean = _segment_mean_ratio(ratios, next_start, next_end)
                if abs(short_mean - prev_mean) <= abs(short_mean - next_mean):
                    merged[i - 1] = (prev_start, end, prev_label)
                    merged.pop(i)
                    i -= 1
                else:
                    merged[i + 1] = (start, next_end, next_label)
                    merged.pop(i)
            merged = _merge_adjacent_same_class(merged)

    return merged


def _merge_adjacent_same_class(segments: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str]]:
    if not segments:
        return []
    merged: List[Tuple[int, int, str]] = [segments[0]]
    for start, end, label in segments[1:]:
        last_start, last_end, last_label = merged[-1]
        if label == last_label:
            merged[-1] = (last_start, end, label)
        else:
            merged.append((start, end, label))
    return merged


def _summarize_interval(
    segment: Tuple[int, int],
    power: np.ndarray,
    heart_rate: Optional[np.ndarray],
    ftp: float,
    lthr: Optional[float],
    hr_max: Optional[float],
) -> IntervalSummary:
    start, end = segment
    slice_power = power[start:end]
    duration = end - start
    if duration <= 0 or slice_power.size == 0:
        return IntervalSummary(
            start=start,
            end=end,
            classification="recovery",
            average_power=0.0,
            peak_power=0.0,
            normalized_power=0.0,
            intensity_factor=0.0,
            power_ratio=0.0,
            time_above_95=0.0,
            time_above_106=0.0,
            time_above_120=0.0,
            time_above_150=0.0,
            heart_rate_avg=None,
            heart_rate_max=None,
            heart_rate_slope=None,
        )

    avg_power = float(np.mean(slice_power))
    peak_power = float(np.max(slice_power))
    norm_power = _normalized_power(slice_power)
    intensity = norm_power / ftp if ftp else 0.0
    ratio = avg_power / ftp if ftp else 0.0

    fractions = _time_above_thresholds(slice_power, ftp)
    hr_avg: Optional[float] = None
    hr_max_val: Optional[int] = None
    hr_slope: Optional[float] = None
    slice_hr: Optional[np.ndarray] = None
    if heart_rate is not None and heart_rate.size >= end:
        slice_hr = heart_rate[start:end]
        valid = slice_hr[slice_hr > 0]
        if valid.size:
            hr_avg = float(np.mean(valid))
            hr_max_val = int(np.max(valid))
            hr_slope = float((valid[-1] - valid[0]) / duration) if duration > 0 else 0.0

    metadata: Dict[str, Any] = {}
    if lthr and slice_hr is not None and duration > 0:
        metadata['time_over_lthr'] = float(np.sum(slice_hr >= lthr) / duration)
    if hr_max and hr_avg is not None and hr_max > 0:
        metadata['hr_percent_max'] = hr_avg / hr_max

    return IntervalSummary(
        start=start,
        end=end,
        classification="unclassified",
        average_power=avg_power,
        peak_power=peak_power,
        normalized_power=norm_power,
        intensity_factor=intensity,
        power_ratio=ratio,
        time_above_95=fractions['gt_95'],
        time_above_106=fractions['gt_106'],
        time_above_120=fractions['gt_120'],
        time_above_150=fractions['gt_150'],
        heart_rate_avg=hr_avg,
        heart_rate_max=hr_max_val,
        heart_rate_slope=hr_slope,
        metadata=metadata,
    )


def _normalized_power(series: np.ndarray) -> float:
    if series.size == 0:
        return 0.0
    window = 30
    if series.size <= window:
        return float(np.mean(series))
    moving = _moving_average(series, window)
    fourth = np.power(np.maximum(moving, 0), 4)
    return float(np.power(np.mean(fourth), 0.25))


def _time_above_thresholds(series: np.ndarray, ftp: float) -> Dict[str, float]:
    if series.size == 0 or not ftp:
        return {"gt_95": 0.0, "gt_106": 0.0, "gt_120": 0.0, "gt_150": 0.0}
    duration = series.size
    ratios = series / ftp
    return {
        "gt_95": float(np.sum(ratios > 0.95) / duration),
        "gt_106": float(np.sum(ratios > 1.06) / duration),
        "gt_120": float(np.sum(ratios > 1.20) / duration),
        "gt_150": float(np.sum(ratios > 1.50) / duration),
    }


def _classify_interval(summary: IntervalSummary, ftp: float) -> IntervalSummary:
    if summary.classification != "unclassified":
        return summary
    dur = summary.duration
    ratio = summary.power_ratio
    peak_ratio = summary.peak_power / ftp if ftp else 0.0
    time_gt_95 = summary.time_above_95
    time_gt_106 = summary.time_above_106
    time_gt_120 = summary.time_above_120
    time_gt_150 = summary.time_above_150
    sustained_over_150 = (time_gt_150 * dur) >= 6

    classification = "recovery"
    if (
        (peak_ratio >= 1.8 and dur >= 3)
        or (ratio >= 1.6 and 3 <= dur <= 15)
        or (sustained_over_150 and dur <= 40 and ratio >= 1.3)
    ):
        classification = "sprint"
    elif ratio >= 1.21 or time_gt_120 >= 0.70:
        classification = "anaerobic"
    elif ratio >= 1.06 or time_gt_106 >= 0.60:
        classification = "vo2max"
    elif ratio >= 0.95 or time_gt_95 >= 0.70:
        classification = "threshold"
    elif ratio >= 0.76:
        classification = "tempo"
    elif ratio >= 0.56:
        classification = "endurance"
    else:
        classification = "recovery"

    summary.classification = classification
    return summary


def _detect_z2_z1_repeats(power: np.ndarray, ftp: float, timestamps: np.ndarray) -> List[RepeatBlock]:
    if power.size == 0 or not ftp:
        return []
    ratios = power / ftp
    segments = _extract_ratio_segments(ratios, timestamps)
    candidate_groups: List[RepeatBlock] = []
    idx = 0
    while idx < len(segments) - 3:
        if segments[idx][2] != "Z2":
            idx += 1
            continue
        group: List[Tuple[int, int, str, float]] = []
        j = idx
        while j < len(segments):
            seg = segments[j]
            if not group:
                if seg[2] != "Z2":
                    break
                group.append(seg)
            else:
                expected = "Z1" if group[-1][2] == "Z2" else "Z2"
                if seg[2] != expected:
                    break
                if seg[0] - group[-1][1] > 60:
                    break
                group.append(seg)
            j += 1
        pairs = len(group) // 2
        if pairs >= 2:
            z2_durations = [seg[1] - seg[0] for seg in group if seg[2] == "Z2"]
            z1_durations = [seg[1] - seg[0] for seg in group if seg[2] == "Z1"]
            if not z2_durations or not z1_durations:
                idx += 1
                continue
            cv_z2 = _coefficient_of_variation(z2_durations)
            cv_z1 = _coefficient_of_variation(z1_durations)
            avg_ratio_z2 = np.mean([seg[3] for seg in group if seg[2] == "Z2"])
            avg_ratio_z1 = np.mean([seg[3] for seg in group if seg[2] == "Z1"])
            if cv_z2 <= 0.25 and cv_z1 <= 0.25 and (avg_ratio_z2 - avg_ratio_z1) >= 0.10:
                block = RepeatBlock(
                    start=group[0][0],
                    end=group[-1][1],
                    cycles=[
                        {
                            "work": {
                                "start": group[k][0],
                                "end": group[k][1],
                                "avg_ratio": group[k][3],
                            },
                            "rest": {
                                "start": group[k + 1][0],
                                "end": group[k + 1][1],
                                "avg_ratio": group[k + 1][3],
                            },
                        }
                        for k in range(0, len(group) - 1, 2)
                    ],
                )
                candidate_groups.append(block)
                idx = j
                continue
        idx += 1
    return candidate_groups


def _extract_ratio_segments(
    ratios: np.ndarray,
    timestamps: np.ndarray,
) -> List[Tuple[int, int, str, float]]:
    segments: List[Tuple[int, int, str, float]] = []
    n = ratios.size
    idx = 0
    while idx < n:
        ratio = ratios[idx]
        zone: Optional[str] = None
        if 0.60 <= ratio <= 0.75:
            zone = "Z2"
        elif 0.40 <= ratio <= 0.55:
            zone = "Z1"
        if zone is None:
            idx += 1
            continue
        start_idx = idx
        while idx < n and ((zone == "Z2" and 0.58 <= ratios[idx] <= 0.78) or (zone == "Z1" and 0.38 <= ratios[idx] <= 0.60)):
            idx += 1
        end_idx = idx
        duration = timestamps[end_idx - 1] - timestamps[start_idx] + 1 if end_idx > start_idx else 0
        if duration >= 60:
            avg_ratio = float(np.mean(ratios[start_idx:end_idx]))
            segments.append((int(timestamps[start_idx]), int(timestamps[end_idx - 1] + 1), zone, avg_ratio))
    return segments


def _coefficient_of_variation(values: Iterable[int]) -> float:
    values_list = list(values)
    if not values_list:
        return float('inf')
    mean_val = float(np.mean(values_list))
    if mean_val == 0:
        return float('inf')
    return float(np.std(values_list) / mean_val)


def render_interval_preview(
    result: IntervalDetectionResult,
    timestamps: Sequence[int],
    power: Sequence[float],
    output_path: str,
) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    if timestamps is None or power is None:
        return
    if len(timestamps) == 0 or len(power) == 0:
        return

    ts = np.asarray(timestamps, dtype=int)
    pw = np.asarray(power, dtype=float)
    if pw.size != ts.size:
        ts = np.arange(pw.size)

    fig, ax = plt.subplots(figsize=(12, 3.5))

    colour_map = {
        "recovery": "#a6c8ff",
        "endurance": "#6dd17c",
        "tempo": "#ffd166",
        "threshold": "#ffa94d",
        "vo2max": "#ff6f59",
        "anaerobic": "#e63946",
        "sprint": "#9d4edd",
    }

    ftp = max(result.ftp, 1.0)
    for interval in result.intervals:
        label = interval.classification
        colour = colour_map.get(label, "#cccccc")
        avg_ratio = max(interval.power_ratio, 0.02)
        height = min(max(avg_ratio, 0.02), 1.6)

        start_idx = max(0, int(interval.start))
        end_idx = max(start_idx + 1, int(interval.end))
        if start_idx < ts.size:
            start_time = float(ts[start_idx])
        else:
            start_time = float(start_idx)
        if end_idx - 1 < ts.size:
            end_time = float(ts[end_idx - 1] + 1)
        else:
            end_time = float(end_idx)
        width = max(end_time - start_time, 1.0)

        ax.bar(
            start_time,
            height,
            width=width,
            align='edge',
            color=colour,
            edgecolor='none',
            alpha=0.9,
        )

    if result.intervals:
        ratios = np.clip(pw / ftp, 0, 1.6)
        window = min(max(len(ratios) // 80, 9), 150)
        if window % 2 == 0:
            window += 1
        smoothed = _moving_average(ratios, window) if len(ratios) > window else ratios
        ax.plot(ts[: len(smoothed)], smoothed[: len(ts)], color="#6c757d", alpha=0.1, linewidth=1.2)

    ax.set_ylim(0, 1.8)
    ax.set_xlim(float(ts[0]) if ts.size else 0.0, float(ts[-1] + 1) if ts.size else len(pw))
    ax.set_yticks([])
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Intensity")
    ax.grid(alpha=0.1, axis='y', linestyle='--')
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def summarize_window(
    power: Sequence[float],
    heart_rate: Optional[Sequence[float]],
    ftp: float,
    start: int,
    end: int,
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
) -> IntervalSummary:
    pw = np.asarray(power, dtype=float)
    hr = None
    if heart_rate is not None:
        hr = np.asarray(list(heart_rate), dtype=float)
    start_idx = max(0, min(int(start), pw.size))
    end_idx = max(start_idx, min(int(end), pw.size))
    return _summarize_interval((start_idx, end_idx), pw, hr, ftp, lthr, hr_max)


# ============================================================================
# 基于心率的区间检测函数
# ============================================================================


def _resolve_lthr_value(
    lthr: Optional[float],
    hr_max: Optional[float],
) -> Optional[float]:
    """
    解析阈值心率值
    
    优先级：
    1. 直接提供的 lthr
    2. 如果 lthr 不存在，使用 hr_max * 0.9 作为估算值
    
    Args:
        lthr: 阈值心率
        hr_max: 最大心率
        
    Returns:
        阈值心率值，如果都不可用则返回 None
    """
    if lthr and lthr > 0:
        return float(lthr)
    if hr_max and hr_max > 0:
        # 使用最大心率的90%作为阈值心率估算
        estimated_lthr = hr_max * 0.9
        return float(estimated_lthr)
    return None


def _prepare_heartrate_inputs(
    timestamps: Sequence[int],
    heart_rate: Sequence[Optional[float]],
    cfg: IntervalDetectionConfig,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    准备心率数据用于检测
    
    类似_prepare_inputs，但只处理心率数据
    
    Args:
        timestamps: 时间戳序列
        heart_rate: 心率序列
        cfg: 配置对象
        
    Returns:
        (时间戳数组, 心率数组) - 已重采样到1Hz
    """
    if timestamps is None or heart_rate is None:
        return np.array([]), np.array([])
    if len(timestamps) == 0 or len(heart_rate) == 0:
        return np.array([]), np.array([])
    
    ts = np.asarray(timestamps, dtype=int)
    if ts.ndim != 1:
        ts = ts.flatten()
    order = np.argsort(ts)
    ts = ts[order]
    
    hr_raw = np.asarray(heart_rate, dtype=float)
    if hr_raw.ndim != 1:
        hr_raw = hr_raw.flatten()
    hr_raw = hr_raw[order[: hr_raw.shape[0]]]
    
    # 重采样到1Hz
    if ts.size == hr_raw.size and np.all(np.diff(ts) <= 1):
        timeline = ts
        hr_series = hr_raw
    else:
        timeline, hr_series = _resample_to_1hz(ts, hr_raw)
    
    # 将无效值（0或负数）设为NaN
    hr_series = np.where(hr_series > 0, hr_series, 0)
    
    # 填充短时缺失值
    hr_series = _fill_short_zero_gaps(hr_series, cfg.zero_fill_window)
    
    return timeline, hr_series


def _classification_from_heartrate_ratio(ratio: float) -> str:
    """
    根据心率比值（HR/LTHR）分类区间
    
    对应功率区间的七个区间，基于 Intervals.icu/Friel 七区模型：
    - recovery: < 0.81
    - endurance: 0.81-0.89
    - tempo: 0.90-0.93
    - threshold: 0.94-0.99
    - vo2max: 1.00-1.02
    - anaerobic: 1.03-1.06
    - sprint: > 1.06
    
    Args:
        ratio: 心率/阈值心率的比值
        
    Returns:
        区间分类标签
    """
    if ratio >= 1.06:
        return "sprint"
    if ratio >= 1.03:
        return "anaerobic"
    if ratio >= 1.00:
        return "vo2max"
    if ratio >= 0.94:
        return "threshold"
    if ratio >= 0.90:
        return "tempo"
    if ratio >= 0.81:
        return "endurance"
    return "recovery"


def _summarize_interval_by_heartrate(
    segment: Tuple[int, int],
    heart_rate: np.ndarray,
    threshold_hr: float,
    hr_max: Optional[float],
) -> IntervalSummary:
    """
    基于心率数据生成区间摘要
    
    类似_summarize_interval，但基于心率数据计算
    
    Args:
        segment: 区间范围 (start, end)
        heart_rate: 心率数组
        threshold_hr: 阈值心率
        hr_max: 最大心率（可选）
        
    Returns:
        区间摘要对象
    """
    start, end = segment
    slice_hr = heart_rate[start:end]
    duration = end - start
    
    if duration <= 0 or slice_hr.size == 0:
        return IntervalSummary(
            start=start,
            end=end,
            classification="recovery",
            average_power=0.0,
            peak_power=0.0,
            normalized_power=0.0,
            intensity_factor=0.0,
            power_ratio=0.0,
            time_above_95=0.0,
            time_above_106=0.0,
            time_above_120=0.0,
            time_above_150=0.0,
            heart_rate_avg=None,
            heart_rate_max=None,
            heart_rate_slope=None,
        )
    
    # 计算心率统计
    valid_hr = slice_hr[slice_hr > 0]
    if valid_hr.size == 0:
        hr_avg = 0.0
        hr_max_val = 0
        hr_slope = 0.0
        avg_ratio = 0.0
    else:
        hr_avg = float(np.mean(valid_hr))
        hr_max_val = int(np.max(valid_hr))
        hr_slope = float((valid_hr[-1] - valid_hr[0]) / duration) if duration > 0 and valid_hr.size > 1 else 0.0
        avg_ratio = hr_avg / threshold_hr if threshold_hr > 0 else 0.0
    
    # 计算超过阈值的时间占比
    hr_ratios = slice_hr / threshold_hr if threshold_hr > 0 else np.zeros_like(slice_hr)
    time_above_95 = float(np.sum(hr_ratios >= 0.95) / duration) if duration > 0 else 0.0
    time_above_106 = float(np.sum(hr_ratios >= 1.06) / duration) if duration > 0 else 0.0
    
    # 元数据
    metadata: Dict[str, Any] = {}
    if hr_max and hr_avg > 0 and hr_max > 0:
        metadata['hr_percent_max'] = hr_avg / hr_max
    if threshold_hr > 0:
        metadata['hr_percent_threshold'] = avg_ratio
    metadata['data_source'] = 'heartrate'
    
    # 注意：功率相关字段设为0或使用心率比值映射（保持接口兼容）
    return IntervalSummary(
        start=start,
        end=end,
        classification="unclassified",
        average_power=0.0,
        peak_power=0.0,
        normalized_power=0.0,
        intensity_factor=avg_ratio,
        power_ratio=avg_ratio,  # 使用心率比值作为"功率比值"（保持兼容）
        time_above_95=time_above_95,
        time_above_106=time_above_106,
        time_above_120=0.0,
        time_above_150=0.0,
        heart_rate_avg=hr_avg,
        heart_rate_max=hr_max_val,
        heart_rate_slope=hr_slope,
        metadata=metadata,
    )


def _classify_interval_by_heartrate(
    summary: IntervalSummary,
    threshold_hr: float,
) -> IntervalSummary:
    """
    基于心率数据分类区间
    
    类似_classify_interval，但基于心率比值
    
    Args:
        summary: 区间摘要对象
        threshold_hr: 阈值心率
        
    Returns:
        已分类的区间摘要对象
    """
    if summary.classification != "unclassified":
        return summary
    
    dur = summary.duration
    ratio = summary.power_ratio  # 实际是心率比值
    hr_max_val = summary.heart_rate_max or 0
    peak_ratio = hr_max_val / threshold_hr if threshold_hr > 0 else 0.0
    time_gt_95 = summary.time_above_95
    time_gt_106 = summary.time_above_106
    
    classification = "recovery"
    
    # 基于心率比值的分类逻辑
    # 注意：心率的峰值识别不如功率准确，冲刺判断需要更保守
    if ratio >= 1.06 or time_gt_106 >= 0.70:
        classification = "anaerobic"
    elif ratio >= 1.00 or time_gt_95 >= 0.60:
        classification = "vo2max"
    elif ratio >= 0.94 or time_gt_95 >= 0.70:
        classification = "threshold"
    elif ratio >= 0.90:
        classification = "tempo"
    elif ratio >= 0.81:
        classification = "endurance"
    else:
        classification = "recovery"
    
    summary.classification = classification
    return summary


def detect_intervals_by_heartrate(
    timestamps: Sequence[int],
    heart_rate: Sequence[Optional[float]],
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
    config: Optional[IntervalDetectionConfig] = None,
) -> IntervalDetectionResult:
    """
    基于心率数据的区间检测
    
    使用阈值心率（LTHR）作为基准，将心率数据映射到七个训练区间。
    如果LTHR不存在，使用最大心率的90%作为估算值。
    
    区间分类基于心率/LTHR比值，与功率区间对应：
    - Zone1 Recovery: < 81% LTHR
    - Zone2 Endurance: 81-89% LTHR
    - Zone3 Tempo: 90-93% LTHR
    - Zone4 Threshold: 94-99% LTHR
    - Zone5 VO2max: 100-102% LTHR
    - Zone6 Anaerobic: 103-106% LTHR
    - Zone7 Sprint: > 106% LTHR
    
    Args:
        timestamps: 时间戳序列（秒）
        heart_rate: 心率序列（bpm）
        lthr: 阈值心率（优先使用）
        hr_max: 最大心率（如果lthr不存在，使用hr_max * 0.9作为估算值）
        config: 配置对象（可选，使用默认配置）
        
    Returns:
        IntervalDetectionResult: 检测结果，包含intervals和repeats
        
    Note:
        - 如果心率数据不足或阈值无法确定，返回空结果
        - 区间分类基于心率/LTHR比值，与功率区间对应
        - ftp字段存储阈值心率值（保持接口兼容）
    """
    # 1. 解析阈值心率
    threshold_hr = _resolve_lthr_value(lthr, hr_max)
    if not threshold_hr or threshold_hr <= 0:
        return IntervalDetectionResult(
            duration=0,
            ftp=0.0,
            intervals=[],
            repeats=[]
        )
    
    # 2. 准备输入数据
    cfg = config or IntervalDetectionConfig()
    ts, hr_series = _prepare_heartrate_inputs(timestamps, heart_rate, cfg)
    if not hr_series.size:
        return IntervalDetectionResult(
            duration=0,
            ftp=float(threshold_hr),
            intervals=[],
            repeats=[]
        )
    
    duration = int(ts[-1]) if ts.size else int(hr_series.size)
    
    # 3. 计算心率比值（相对于阈值心率）
    hr_ratios = hr_series / threshold_hr if threshold_hr else np.zeros_like(hr_series)
    
    # 4. 使用类似功率检测的算法，但基于心率比值
    # 计算快慢通道
    fast_hr, slow_hr = _compute_channels(hr_series, cfg)
    baseline_hr = _rolling_median(slow_hr, cfg.baseline_window)
    theta_hr = _compute_theta(fast_hr, baseline_hr, threshold_hr)
    
    # 5. 检测区间段（基于心率变化）
    raw_segments = _segment_intervals(
        fast_hr, slow_hr, baseline_hr, theta_hr, threshold_hr, cfg
    )
    
    # 6. 检测高心率段（类似冲刺）
    sprint_segments = _detect_sprint_overrides(hr_series, threshold_hr, cfg)
    
    # 7. 合并和调整区间
    candidates = _merge_and_adjust_segments(
        raw_segments + sprint_segments, hr_series, slow_hr, threshold_hr, cfg
    )
    
    # 8. 基于比值检测额外区间
    ratio_segments = _detect_ratio_segments(slow_hr, candidates, threshold_hr)
    
    # 9. 生成区间摘要
    interval_summaries = [
        _summarize_interval_by_heartrate(seg, hr_series, threshold_hr, hr_max)
        for seg in candidates
        if seg[1] - seg[0] >= 3
    ]
    
    # 10. 添加比值区间
    for start, end, label in ratio_segments:
        summary = _summarize_interval_by_heartrate(
            (start, end), hr_series, threshold_hr, hr_max
        )
        summary.classification = label
        meta = dict(summary.metadata)
        meta['source'] = 'ratio'
        summary.metadata = meta
        interval_summaries.append(summary)
    
    # 11. 分类区间
    classified = [
        _classify_interval_by_heartrate(summary, threshold_hr)
        for summary in interval_summaries
    ]
    
    # 12. 构建覆盖率（基于心率比值）
    coverage = np.full(hr_series.size, "", dtype=object)
    priority = {
        "recovery": 0,
        "endurance": 1,
        "tempo": 2,
        "threshold": 3,
        "vo2max": 4,
        "anaerobic": 5,
        "sprint": 6,
    }
    
    def _assign_segment(start: int, end: int, label: str) -> None:
        if label not in priority:
            return
        s = max(0, int(start))
        e = min(int(end), hr_series.size)
        if s >= e:
            return
        for idx in range(s, e):
            current = coverage[idx]
            if not current or priority[label] >= priority.get(current, -1):
                coverage[idx] = label
    
    for summary in classified:
        _assign_segment(summary.start, summary.end, summary.classification)
    
    # 13. 填充未覆盖区域（基于心率比值）
    for idx, label in enumerate(coverage):
        if label:
            continue
        coverage[idx] = _classification_from_heartrate_ratio(float(hr_ratios[idx]))
    
    # 14. 构建最终区间
    segments = _build_segments_from_coverage(coverage)
    segments = _simplify_segments(segments, hr_ratios, default_min_length=30)
    
    # 15. 生成最终区间摘要
    final_intervals: List[IntervalSummary] = []
    for start, end, label in segments:
        summary = _summarize_interval_by_heartrate(
            (start, end), hr_series, threshold_hr, hr_max
        )
        summary.classification = label
        final_intervals.append(summary)
    
    # 16. 检测重复模式（Z2-Z1重复）
    repeats = _detect_z2_z1_repeats(hr_series, threshold_hr, ts)
    
    return IntervalDetectionResult(
        duration=duration,
        ftp=float(threshold_hr),  # 使用阈值心率作为"参考值"
        intervals=final_intervals,
        repeats=repeats,
    )


__all__ = [
    "IntervalDetectionConfig",
    "IntervalDetectionResult",
    "IntervalSummary",
    "RepeatBlock",
    "detect_intervals",
    "detect_intervals_by_heartrate",
    "render_interval_preview",
    "summarize_window",
]
