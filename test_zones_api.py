#!/usr/bin/env python3
"""
测试区间分析接口的脚本
"""

import requests
import json

def test_zones_api():
    """测试区间分析接口"""
    base_url = "http://localhost:8000"
    
    # 测试活动ID
    activity_id = 106
    
    print("🧪 开始测试区间分析接口...")
    print(f"📍 测试活动ID: {activity_id}")
    print()
    
    # 测试功率区间
    print("1️⃣ 测试功率区间分析...")
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/zones?key=power", timeout=30)
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ 功率区间分析成功!")
            print(f"   响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   ❌ 请求失败: {response.text}")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
    
    print()
    
    # 测试心率区间
    print("2️⃣ 测试心率区间分析...")
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/zones?key=heartrate", timeout=30)
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ 心率区间分析成功!")
            print(f"   响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
        else:
            print(f"   ❌ 请求失败: {response.text}")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
    
    print()
    
    # 测试无效参数
    print("3️⃣ 测试无效参数...")
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/zones?key=invalid", timeout=30)
        print(f"   状态码: {response.status_code}")
        
        if response.status_code == 422:
            print("   ✅ 参数验证正确，拒绝了无效参数")
        else:
            print(f"   ⚠️  意外的状态码: {response.status_code}")
    except Exception as e:
        print(f"   ❌ 请求异常: {e}")
    
    print()
    print("🎉 测试完成!")

if __name__ == "__main__":
    test_zones_api() 