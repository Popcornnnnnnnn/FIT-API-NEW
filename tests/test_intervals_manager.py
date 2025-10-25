"""测试 intervals_manager 模块

测试 intervals 数据的保存、读取和删除功能。
"""

import pytest
import json
from pathlib import Path
from app.infrastructure.intervals_manager import (
    save_intervals,
    load_intervals,
    delete_intervals,
    INTERVALS_DIR,
)


def test_save_and_load_intervals():
    """测试保存和读取 intervals 数据"""
    activity_id = 999999
    test_data = {
        "duration": 3600,
        "ftp": 250.0,
        "items": [
            {
                "start": 0,
                "end": 300,
                "duration": 300,
                "classification": "warmup",
                "average_power": 150.0,
                "peak_power": 200.0,
                "normalized_power": 160.0,
                "intensity_factor": 0.64,
                "power_ratio": 0.6,
                "time_above_95": 0.0,
                "time_above_106": 0.0,
                "time_above_120": 0.0,
                "time_above_150": 0.0,
                "heart_rate_avg": 120.0,
                "heart_rate_max": 140,
                "heart_rate_slope": 0.05,
                "metadata": {},
            }
        ],
        "preview_image": "artifacts/Pics/test.png",
        "zone_segments": None,
    }
    
    # 测试保存
    success = save_intervals(activity_id, test_data)
    assert success, "保存 intervals 数据失败"
    
    # 验证文件存在
    file_path = INTERVALS_DIR / f"{activity_id}.json"
    assert file_path.exists(), f"文件 {file_path} 不存在"
    
    # 测试读取
    loaded_data = load_intervals(activity_id)
    assert loaded_data is not None, "读取 intervals 数据失败"
    assert loaded_data["duration"] == test_data["duration"]
    assert loaded_data["ftp"] == test_data["ftp"]
    assert len(loaded_data["items"]) == len(test_data["items"])
    
    # 清理测试数据
    delete_success = delete_intervals(activity_id)
    assert delete_success, "删除 intervals 数据失败"
    assert not file_path.exists(), f"文件 {file_path} 仍然存在"


def test_load_nonexistent_intervals():
    """测试读取不存在的 intervals 数据"""
    activity_id = 888888
    
    # 确保文件不存在
    file_path = INTERVALS_DIR / f"{activity_id}.json"
    if file_path.exists():
        file_path.unlink()
    
    # 测试读取不存在的数据
    loaded_data = load_intervals(activity_id)
    assert loaded_data is None, "应该返回 None"


def test_delete_nonexistent_intervals():
    """测试删除不存在的 intervals 数据"""
    activity_id = 777777
    
    # 确保文件不存在
    file_path = INTERVALS_DIR / f"{activity_id}.json"
    if file_path.exists():
        file_path.unlink()
    
    # 测试删除不存在的数据（应该返回成功）
    success = delete_intervals(activity_id)
    assert success, "删除不存在的文件应该返回成功"


def test_intervals_dir_creation():
    """测试 intervals 目录自动创建"""
    # 如果目录不存在，save_intervals 应该自动创建
    activity_id = 666666
    test_data = {
        "duration": 1800,
        "ftp": 200.0,
        "items": [],
        "preview_image": None,
        "zone_segments": None,
    }
    
    # 保存数据（会自动创建目录）
    success = save_intervals(activity_id, test_data)
    assert success, "保存失败"
    assert INTERVALS_DIR.exists(), "目录应该被自动创建"
    
    # 清理
    delete_intervals(activity_id)


if __name__ == "__main__":
    print("运行 intervals_manager 测试...")
    test_save_and_load_intervals()
    print("✓ 测试保存和读取 intervals 数据")
    
    test_load_nonexistent_intervals()
    print("✓ 测试读取不存在的 intervals 数据")
    
    test_delete_nonexistent_intervals()
    print("✓ 测试删除不存在的 intervals 数据")
    
    test_intervals_dir_creation()
    print("✓ 测试 intervals 目录自动创建")
    
    print("\n所有测试通过！")

