"""测试/调试相关的轻量路由。"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..repositories.best_power_file_repo import load_best_curve
from ..streams.fit_parser import FitParser
from ..core.analytics.interval_detection import (
    IntervalSummary,
    detect_intervals,
    render_interval_preview,
)


router = APIRouter(prefix="/test", tags=["测试"])


@router.get("/best_power/{athlete_id}")
async def get_athlete_best_power_curve(athlete_id: int) -> Dict[str, Any]:
    """返回指定运动员的全局最佳功率曲线（逐秒）。"""
    curve = load_best_curve(athlete_id)
    if curve is None:
        raise HTTPException(status_code=404, detail="未找到该运动员的最佳功率曲线记录")
    return {"athlete_id": athlete_id, "length": len(curve), "best_curve": curve}


def _interval_summary_to_dict(summary: IntervalSummary) -> Dict[str, Any]:
    """将 IntervalSummary 转为可 JSON 序列化的字典。"""

    def _convert(value: Any) -> Any:
        if isinstance(value, (int, float, bool, str)) or value is None:
            return value
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_convert(v) for v in value]
        try:
            return float(value)
        except Exception:
            return str(value)

    metadata = _convert(summary.metadata) if summary.metadata else {}
    return {
        "start": int(summary.start),
        "end": int(summary.end),
        "duration": int(summary.duration),
        "classification": summary.classification,
        "average_power": float(summary.average_power),
        "peak_power": float(summary.peak_power),
        "normalized_power": float(summary.normalized_power),
        "intensity_factor": float(summary.intensity_factor),
        "power_ratio": float(summary.power_ratio),
        "time_above_95": float(summary.time_above_95),
        "time_above_106": float(summary.time_above_106),
        "time_above_120": float(summary.time_above_120),
        "time_above_150": float(summary.time_above_150),
        "heart_rate_avg": float(summary.heart_rate_avg) if summary.heart_rate_avg is not None else None,
        "heart_rate_max": int(summary.heart_rate_max) if summary.heart_rate_max is not None else None,
        "heart_rate_slope": float(summary.heart_rate_slope) if summary.heart_rate_slope is not None else None,
        "metadata": metadata,
    }


@router.post("/intervals/preview")
async def preview_intervals_from_fit(
    file: UploadFile = File(..., description="FIT 文件"),
    ftp: float = Form(..., description="用于分析的 FTP"),
    lthr: Optional[float] = Form(None, description="阈值心率（可选）"),
    hr_max: Optional[float] = Form(None, description="最大心率（可选）"),
) -> Dict[str, Any]:
    """上传 FIT 文件并生成功率区间可视化。"""

    if ftp <= 0:
        raise HTTPException(status_code=400, detail="FTP 必须大于 0")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="未读取到有效的 FIT 文件内容")

    parser = FitParser()
    try:
        stream = parser.parse_fit_file(file_bytes, athlete_info={"ftp": ftp})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"解析 FIT 文件失败: {exc}") from exc

    power: List[int] = stream.power or []
    if not power:
        raise HTTPException(status_code=400, detail="FIT 文件中缺少功率数据，无法分析区间")

    timestamps = stream.timestamp or list(range(len(power)))
    if len(timestamps) != len(power):
        timestamps = list(range(len(power)))

    heart_rate: Optional[List[int]] = stream.heart_rate or None

    detection = detect_intervals(
        timestamps,
        power,
        ftp,
        heart_rate=heart_rate,
        lthr=lthr,
        hr_max=hr_max,
    )

    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    preview_path = artifacts_dir / "my_fit_preview.png"
    try:
        render_interval_preview(detection, timestamps, power, str(preview_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成预览图失败: {exc}") from exc

    intervals = [_interval_summary_to_dict(summary) for summary in detection.intervals]
    repeats = [
        {
            "start": block.start,
            "end": block.end,
            "classification": block.classification,
            "cycles": block.cycles,
        }
        for block in detection.repeats
    ]

    return {
        "duration": int(detection.duration),
        "ftp": float(detection.ftp),
        "preview_image": str(preview_path),
        "intervals": intervals,
        "repeats": repeats,
    }
