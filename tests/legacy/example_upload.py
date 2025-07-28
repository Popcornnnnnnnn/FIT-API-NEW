#!/usr/bin/env python3
"""
文件上传接口使用示例

这个脚本演示如何使用新的POST /uploads接口上传FIT文件。
包含自定义文件上传方法和完整的测试流程。
"""

import requests
import json
import os
import io
import base64
from typing import Optional, Dict, Any

# API基础URL
BASE_URL = "http://localhost:8000"

def create_athlete():
    """创建测试运动员"""
    athlete_data = {
        "name": "测试运动员",
        "ftp": 250.0,
        "max_hr": 185,
        "weight": 70.5
    }
    
    response = requests.post(f"{BASE_URL}/athletes/", json=athlete_data)
    if response.status_code == 200:
        athlete = response.json()
        print(f"✅ 运动员创建成功: {athlete['name']} (ID: {athlete['id']})")
        return athlete['id']
    else:
        print(f"❌ 运动员创建失败: {response.text}")
        return None

def create_mock_fit_file(content: str = "mock fit file content", filename: str = "test.fit") -> io.BytesIO:
    """
    创建模拟的FIT文件
    
    Args:
        content: 文件内容
        filename: 文件名
    
    Returns:
        BytesIO对象，包含模拟的FIT文件数据
    """
    # 创建模拟的FIT文件头部（简化版）
    fit_header = b'\x0E\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    fit_content = content.encode('utf-8')
    
    # 组合完整的FIT文件数据
    fit_data = fit_header + fit_content
    
    return io.BytesIO(fit_data)

def create_mock_tcx_file(content: str = "mock tcx file content", filename: str = "test.tcx") -> io.BytesIO:
    """
    创建模拟的TCX文件
    
    Args:
        content: 文件内容
        filename: 文件名
    
    Returns:
        BytesIO对象，包含模拟的TCX文件数据
    """
    tcx_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities>
    <Activity Sport="Biking">
      <Id>2025-07-28T10:00:00Z</Id>
      <Lap StartTime="2025-07-28T10:00:00Z">
        <TotalTimeSeconds>3600</TotalTimeSeconds>
        <DistanceMeters>50000</DistanceMeters>
        <MaximumSpeed>15.0</MaximumSpeed>
        <Calories>800</Calories>
        <AverageHeartRateBpm>
          <Value>150</Value>
        </AverageHeartRateBpm>
        <MaximumHeartRateBpm>
          <Value>180</Value>
        </MaximumHeartRateBpm>
        <Intensity>Active</Intensity>
        <TriggerMethod>Manual</TriggerMethod>
      </Lap>
    </Activity>
  </Activities>
  <Notes>{content}</Notes>
</TrainingCenterDatabase>"""
    
    return io.BytesIO(tcx_template.encode('utf-8'))

def create_mock_gpx_file(content: str = "mock gpx file content", filename: str = "test.gpx") -> io.BytesIO:
    """
    创建模拟的GPX文件
    
    Args:
        content: 文件内容
        filename: 文件名
    
    Returns:
        BytesIO对象，包含模拟的GPX文件数据
    """
    gpx_template = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="FIT-API-Test" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>Test Activity</name>
    <desc>{content}</desc>
    <time>2025-07-28T10:00:00Z</time>
  </metadata>
  <trk>
    <name>Test Track</name>
    <trkseg>
      <trkpt lat="40.7128" lon="-74.0060">
        <ele>10</ele>
        <time>2025-07-28T10:00:00Z</time>
      </trkpt>
      <trkpt lat="40.7129" lon="-74.0061">
        <ele>12</ele>
        <time>2025-07-28T10:01:00Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""
    
    return io.BytesIO(gpx_template.encode('utf-8'))

def upload_file_custom(
    athlete_id: int,
    file_data: io.BytesIO,
    filename: str,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    自定义文件上传方法
    
    Args:
        athlete_id: 运动员ID
        file_data: 文件数据（BytesIO对象）
        filename: 文件名
        **kwargs: 其他可选参数
    
    Returns:
        上传结果字典或None（如果失败）
    """
    
    # 准备表单数据
    data = {
        "athlete_id": athlete_id,
        "name": kwargs.get("name", filename),
        "description": kwargs.get("description", f"自定义上传的{filename}"),
        "trainer": kwargs.get("trainer", "false"),
        "commute": kwargs.get("commute", "false"),
        "data_type": kwargs.get("data_type", filename.split('.')[-1].lower()),
    }
    
    # 添加可选参数
    if "external_id" in kwargs:
        data["external_id"] = kwargs["external_id"]
    
    # 准备文件
    files = {
        "file": (filename, file_data, "application/octet-stream")
    }
    
    try:
        response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传成功!")
            print(f"   - 文件名: {filename}")
            print(f"   - Activity ID: {result['activity_id']}")
            print(f"   - ID String: {result['id_str']}")
            print(f"   - External ID: {result['external_id']}")
            print(f"   - Status: {result['status']}")
            if result['error']:
                print(f"   - Error: {result['error']}")
            return result
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 上传过程中发生错误: {e}")
        return None

def upload_file(athlete_id, file_path, **kwargs):
    """上传文件（从文件路径）"""
    
    # 准备表单数据
    data = {
        "athlete_id": athlete_id,
        "name": kwargs.get("name", "测试活动"),
        "description": kwargs.get("description", "这是一个测试活动"),
        "trainer": kwargs.get("trainer", "false"),
        "commute": kwargs.get("commute", "false"),
        "data_type": kwargs.get("data_type", "fit"),
    }
    
    # 添加可选参数
    if "external_id" in kwargs:
        data["external_id"] = kwargs["external_id"]
    
    # 准备文件
    files = {
        "file": (file_path, open(file_path, "rb"), "application/octet-stream")
    }
    
    try:
        response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 文件上传成功!")
            print(f"   - Activity ID: {result['activity_id']}")
            print(f"   - ID String: {result['id_str']}")
            print(f"   - External ID: {result['external_id']}")
            print(f"   - Status: {result['status']}")
            if result['error']:
                print(f"   - Error: {result['error']}")
            return result
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ 上传过程中发生错误: {e}")
        return None

def test_different_file_types(athlete_id: int):
    """测试不同文件类型的上传"""
    print("\n📁 测试不同文件类型上传...")
    
    # 测试FIT文件
    print("\n1. 测试FIT文件上传...")
    fit_file = create_mock_fit_file("custom fit content", "custom.fit")
    result1 = upload_file_custom(
        athlete_id=athlete_id,
        file_data=fit_file,
        filename="custom.fit",
        name="自定义FIT活动",
        description="这是一个自定义的FIT文件",
        trainer="false",
        commute="true",
        external_id="custom-fit-123"
    )
    
    # 测试TCX文件
    print("\n2. 测试TCX文件上传...")
    tcx_file = create_mock_tcx_file("custom tcx content", "custom.tcx")
    result2 = upload_file_custom(
        athlete_id=athlete_id,
        file_data=tcx_file,
        filename="custom.tcx",
        name="自定义TCX活动",
        description="这是一个自定义的TCX文件",
        trainer="true",
        commute="false",
        data_type="tcx",
        external_id="custom-tcx-456"
    )
    
    # 测试GPX文件
    print("\n3. 测试GPX文件上传...")
    gpx_file = create_mock_gpx_file("custom gpx content", "custom.gpx")
    result3 = upload_file_custom(
        athlete_id=athlete_id,
        file_data=gpx_file,
        filename="custom.gpx",
        name="自定义GPX活动",
        description="这是一个自定义的GPX文件",
        trainer="false",
        commute="false",
        data_type="gpx",
        external_id="custom-gpx-789"
    )
    
    return [result1, result2, result3]

def test_batch_upload(athlete_id: int, count: int = 3):
    """批量上传测试"""
    print(f"\n📦 批量上传测试（{count}个文件）...")
    
    results = []
    for i in range(count):
        print(f"\n上传第 {i+1}/{count} 个文件...")
        
        # 创建不同的模拟文件
        if i % 3 == 0:
            file_data = create_mock_fit_file(f"batch fit {i}", f"batch_{i}.fit")
            filename = f"batch_{i}.fit"
            data_type = "fit"
        elif i % 3 == 1:
            file_data = create_mock_tcx_file(f"batch tcx {i}", f"batch_{i}.tcx")
            filename = f"batch_{i}.tcx"
            data_type = "tcx"
        else:
            file_data = create_mock_gpx_file(f"batch gpx {i}", f"batch_{i}.gpx")
            filename = f"batch_{i}.gpx"
            data_type = "gpx"
        
        result = upload_file_custom(
            athlete_id=athlete_id,
            file_data=file_data,
            filename=filename,
            name=f"批量测试活动 {i+1}",
            description=f"这是第 {i+1} 个批量测试文件",
            trainer="true" if i % 2 == 0 else "false",
            commute="true" if i % 2 == 1 else "false",
            data_type=data_type,
            external_id=f"batch-{i}-{data_type}"
        )
        
        if result:
            results.append(result)
    
    print(f"\n✅ 批量上传完成！成功上传 {len(results)}/{count} 个文件")
    return results

def main():
    """主函数"""
    print("🚀 FIT文件上传接口测试")
    print("=" * 50)
    
    # 1. 创建运动员
    print("\n1. 创建运动员...")
    athlete_id = create_athlete()
    if not athlete_id:
        print("无法继续，运动员创建失败")
        return
    
    # 2. 测试不同文件类型
    print("\n2. 测试不同文件类型...")
    file_results = test_different_file_types(athlete_id)
    
    # 3. 批量上传测试
    print("\n3. 批量上传测试...")
    batch_results = test_batch_upload(athlete_id, 5)
    
    # 4. 统计结果
    print("\n📊 测试结果统计")
    print("=" * 30)
    print(f"运动员ID: {athlete_id}")
    print(f"文件类型测试: {len([r for r in file_results if r])}/3 成功")
    print(f"批量上传测试: {len(batch_results)}/5 成功")
    print(f"总上传成功: {len([r for r in file_results + batch_results if r])} 个文件")
    
    print("\n✅ 所有测试完成!")

if __name__ == "__main__":
    main() 