from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import requests

from app.core.analytics.interval_detection import detect_intervals, render_interval_preview
try:
    from app.streams.fit_parser import FitParser
except ModuleNotFoundError:  # pragma: no cover
    FitParser = None  # type: ignore


def test_detects_simple_sprint_interval():
    ftp = 250.0
    duration = 300
    timestamps = np.arange(duration)
    power = np.full(duration, 150.0)
    power[120:135] = 420.0  # 1.68 * FTP for 15 s

    result = detect_intervals(timestamps, power, ftp)

    sprint_labels = [interval.classification for interval in result.intervals]
    assert "sprint" in sprint_labels


def test_detects_z2_z1_repeats_pattern():
    ftp = 220.0
    z2 = np.full(300, ftp * 0.65)
    z1 = np.full(100, ftp * 0.50)
    pattern = np.concatenate([z2, z1, z2, z1])
    timestamps = np.arange(pattern.size)

    result = detect_intervals(timestamps, pattern, ftp)

    assert result.repeats, "Expected at least one repeat block"
    block = result.repeats[0]
    assert block.classification == "z2-z1-repeats"
    assert len(block.cycles) >= 2


def run_interval_detection_from_url(
    fit_url: str,
    ftp: float,
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
    preview_path: str = "artifacts/url_fit_preview.png",
    timeout: int = 30,
) -> Tuple[object, str]:
    """Download a FIT file and run interval detection with preview generation.

    Returns the detection result and the preview image path for ad-hoc debugging.
    """

    if ftp <= 0:
        raise ValueError("FTP must be greater than zero")

    response = requests.get(fit_url, timeout=timeout)
    response.raise_for_status()

    if FitParser is None:
        raise ImportError("fitparse is not installed; unable to parse FIT files")

    parser = FitParser()
    stream = parser.parse_fit_file(response.content, athlete_info={"ftp": ftp})

    power = stream.power or []
    if not power:
        raise ValueError("FIT file contains no power data")

    timestamps = stream.timestamp or list(range(len(power)))
    if len(timestamps) != len(power):
        timestamps = list(range(len(power)))

    heart_rate = stream.heart_rate or None

    detection = detect_intervals(
        timestamps,
        power,
        ftp,
        heart_rate=heart_rate,
        lthr=lthr,
        hr_max=hr_max,
    )

    preview_file = Path(preview_path)
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    render_interval_preview(detection, timestamps, power, str(preview_file))

    return detection, str(preview_file)


def run_interval_detection_for_fixture(
    fit_filename: str,
    ftp: float,
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
    preview_dir: str = "artifacts/tests",
) -> Tuple[object, str]:
    """Run interval detection for a FIT file stored under tests/fits."""

    if ftp <= 0:
        raise ValueError("FTP must be greater than zero")

    fit_path = Path("tests/fits") / fit_filename
    if not fit_path.exists():
        raise FileNotFoundError(f"Fixture FIT file not found: {fit_path}")

    if FitParser is None:
        raise ImportError("fitparse is not installed; unable to parse FIT files")

    parser = FitParser()
    stream = parser.parse_fit_file(fit_path.read_bytes(), athlete_info={"ftp": ftp})

    power = stream.power or []
    if not power:
        raise ValueError("FIT file contains no power data")

    timestamps = stream.timestamp or list(range(len(power)))
    if len(timestamps) != len(power):
        timestamps = list(range(len(power)))

    heart_rate = stream.heart_rate or None

    detection = detect_intervals(
        timestamps,
        power,
        ftp,
        heart_rate=heart_rate,
        lthr=lthr,
        hr_max=hr_max,
    )

    preview_root = Path(preview_dir)
    preview_root.mkdir(parents=True, exist_ok=True)
    preview_file = preview_root / f"{fit_path.stem}_preview.png"
    render_interval_preview(detection, timestamps, power, str(preview_file))

    return detection, str(preview_file)


def run_interval_detection_for_all_fixtures(
    ftp: float,
    lthr: Optional[float] = None,
    hr_max: Optional[float] = None,
    preview_dir: str = "artifacts/tests",
) -> Iterable[Tuple[str, object, str]]:
    """Run interval detection for every FIT file in tests/fits."""

    fixtures_dir = Path("tests/fits")
    if not fixtures_dir.exists():
        raise FileNotFoundError("tests/fits directory does not exist")

    for fit_path in sorted(fixtures_dir.glob("*.fit")):
        detection, preview = run_interval_detection_for_fixture(
            fit_path.name,
            ftp=ftp,
            lthr=lthr,
            hr_max=hr_max,
            preview_dir=preview_dir,
        )
        yield fit_path.name, detection, preview
