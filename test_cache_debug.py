#!/usr/bin/env python3
"""
测试缓存调试信息
"""

import time
import requests

def test_cache_debug():
    """测试缓存调试信息"""
    base_url = "http://127.0.0.1:8000"
    activity_id = 168
    
    print("=== 缓存调试测试 ===")
    print("现在请观察服务器控制台的输出信息...")
    print("🟢 = 缓存命中 (快速)")
    print("🔴 = 缓存未命中 (需要下载)")
    print("✅ = 下载完成")
    print("❌ = 下载失败")
    print()
    
    # 1. 第一次调用（应该显示下载）
    print("1. 第一次调用heartrate接口:")
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/heartrate")
        end_time = time.time()
        print(f"   响应时间: {end_time - start_time:.3f}秒")
        print(f"   状态码: {response.status_code}")
    except Exception as e:
        print(f"   请求失败: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 2. 第二次调用（应该显示缓存命中）
    print("2. 第二次调用heartrate接口:")
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/heartrate")
        end_time = time.time()
        print(f"   响应时间: {end_time - start_time:.3f}秒")
        print(f"   状态码: {response.status_code}")
    except Exception as e:
        print(f"   请求失败: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 3. 调用其他接口（应该显示缓存命中）
    print("3. 调用power接口:")
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/power")
        end_time = time.time()
        print(f"   响应时间: {end_time - start_time:.3f}秒")
        print(f"   状态码: {response.status_code}")
    except Exception as e:
        print(f"   请求失败: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 4. 清空缓存后再次调用
    print("4. 清空缓存后再次调用:")
    try:
        response = requests.delete(f"{base_url}/activities/cache")
        if response.status_code == 200:
            print("   缓存已清空")
        else:
            print(f"   清空缓存失败: {response.status_code}")
    except Exception as e:
        print(f"   清空缓存失败: {e}")
    
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/activities/{activity_id}/heartrate")
        end_time = time.time()
        print(f"   响应时间: {end_time - start_time:.3f}秒")
        print(f"   状态码: {response.status_code}")
    except Exception as e:
        print(f"   请求失败: {e}")
    
    print("\n=== 测试完成 ===")
    print("请查看服务器控制台的输出，观察缓存命中和未命中的情况")

if __name__ == "__main__":
    test_cache_debug()
