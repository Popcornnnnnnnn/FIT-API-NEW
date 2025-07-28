#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单使用示例

这个脚本展示了如何使用自定义文件上传方法的基本用法。
"""

import io
import requests

# API基础URL
BASE_URL = "http://localhost:8000"

def simple_upload_example():
    """简单上传示例"""
    print("🚀 简单上传示例")
    print("=" * 30)
    
    # 1. 创建运动员
    print("1. 创建运动员...")
    athlete_data = {
        "name": "示例运动员",
        "ftp": 250.0,
        "max_hr": 185,
        "weight": 70.5
    }
    
    response = requests.post(f"{BASE_URL}/athletes/", json=athlete_data)
    if response.status_code != 200:
        print(f"❌ 运动员创建失败: {response.text}")
        return
    
    athlete = response.json()
    athlete_id = athlete['id']
    print(f"✅ 运动员创建成功: {athlete['name']} (ID: {athlete_id})")
    
    # 2. 创建模拟文件
    print("\n2. 创建模拟文件...")
    # 先用字符串写中文内容，再编码为utf-8字节串，避免直接在字节串中写中文
    file_content = "这是一个简单的测试文件内容".encode("utf-8")
    file_data = io.BytesIO(file_content)
    
    # 3. 使用自定义上传方法
    print("3. 上传文件...")
    files = {"file": ("simple_test.fit", file_data, "application/octet-stream")}
    data = {
        "athlete_id": athlete_id,
        "name": "简单测试活动",
        "description": "这是一个简单的测试",
        "trainer": "false",
        "commute": "false",
        "data_type": "fit",
        "external_id": "simple-test-001"
    }
    
    response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        print("✅ 上传成功!")
        print(f"   - Activity ID: {result['activity_id']}")
        print(f"   - Status: {result['status']}")
        print(f"   - External ID: {result['external_id']}")
    else:
        print(f"❌ 上传失败: {response.text}")

def custom_upload_function(athlete_id, file_content, filename, **kwargs):
    """
    自定义上传函数示例
    
    Args:
        athlete_id: 运动员ID
        file_content: 文件内容（bytes 或 str）
        filename: 文件名
        **kwargs: 其他参数
    """
    # 如果 file_content 是 str，则编码为 utf-8
    if isinstance(file_content, str):
        file_content = file_content.encode("utf-8")
    file_data = io.BytesIO(file_content)
    
    # 准备数据
    data = {
        "athlete_id": athlete_id,
        "name": kwargs.get("name", filename),
        "description": kwargs.get("description", "自定义上传"),
        "trainer": kwargs.get("trainer", "false"),
        "commute": kwargs.get("commute", "false"),
        "data_type": kwargs.get("data_type", "fit"),
    }
    
    if "external_id" in kwargs:
        data["external_id"] = kwargs["external_id"]
    
    files = {"file": (filename, file_data, "application/octet-stream")}
    
    response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"上传失败: {response.text}")
        return None

def demonstrate_custom_function():
    """演示自定义函数的使用"""
    print("\n🔧 演示自定义函数...")
    
    # 创建运动员
    athlete_data = {"name": "自定义测试", "ftp": 250.0, "max_hr": 185, "weight": 70.5}
    response = requests.post(f"{BASE_URL}/athletes/", json=athlete_data)
    athlete_id = response.json()['id']
    
    # 使用自定义函数上传
    # 这里直接传入 str，custom_upload_function 会自动编码
    result = custom_upload_function(
        athlete_id=athlete_id,
        file_content="自定义文件内容",
        filename="custom_file.fit",
        name="自定义活动",
        description="使用自定义函数上传",
        trainer="true",
        commute="false",
        external_id="custom-001"
    )
    
    if result:
        print(f"✅ 自定义函数上传成功! Activity ID: {result['activity_id']}")

if __name__ == "__main__":
    print("简单使用示例")
    print("=" * 50)
    
    # 运行简单示例
    simple_upload_example()
    
    # 演示自定义函数
    demonstrate_custom_function()
    
    print("\n✅ 示例完成!") 