#!/usr/bin/env python3
"""
快速上传测试脚本

这个脚本提供简单的文件上传测试功能，用于快速验证API是否正常工作。
"""

import requests
import io
import sys

# API基础URL
BASE_URL = "http://localhost:8000"

def quick_upload_test():
    """快速上传测试"""
    print("🚀 快速上传测试")
    print("=" * 30)
    
    # 1. 创建运动员
    print("1. 创建测试运动员...")
    athlete_data = {
        "name": "快速测试运动员",
        "ftp": 250.0,
        "max_hr": 185,
        "weight": 70.5
    }
    
    try:
        response = requests.post(f"{BASE_URL}/athletes/", json=athlete_data)
        if response.status_code != 200:
            print(f"❌ 运动员创建失败: {response.text}")
            return False
        
        athlete = response.json()
        athlete_id = athlete['id']
        print(f"✅ 运动员创建成功: {athlete['name']} (ID: {athlete_id})")
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到API服务器，请确保服务器正在运行")
        print("   启动命令: uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print(f"❌ 创建运动员时发生错误: {e}")
        return False
    
    # 2. 创建模拟文件
    print("\n2. 创建模拟文件...")
    file_content = b"mock fit file content for quick test"
    file_data = io.BytesIO(file_content)
    
    # 3. 上传文件
    print("3. 上传文件...")
    files = {"file": ("quick_test.fit", file_data, "application/octet-stream")}
    data = {
        "athlete_id": athlete_id,
        "name": "快速测试活动",
        "description": "这是一个快速测试",
        "trainer": "false",
        "commute": "false",
        "data_type": "fit",
        "external_id": "quick-test-123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 文件上传成功!")
            print(f"   - Activity ID: {result['activity_id']}")
            print(f"   - Status: {result['status']}")
            print(f"   - External ID: {result['external_id']}")
            return True
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 上传过程中发生错误: {e}")
        return False

def test_server_status():
    """测试服务器状态"""
    print("🔍 检查服务器状态...")
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print("✅ 服务器运行正常")
            return True
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False

def main():
    """主函数"""
    print("快速上传测试工具")
    print("=" * 50)
    
    # 检查服务器状态
    if not test_server_status():
        print("\n💡 提示:")
        print("1. 确保API服务器正在运行")
        print("2. 运行命令: uvicorn app.main:app --reload")
        print("3. 确保服务器运行在 http://localhost:8000")
        return
    
    # 执行快速测试
    success = quick_upload_test()
    
    if success:
        print("\n🎉 快速测试完成！API工作正常")
    else:
        print("\n❌ 快速测试失败，请检查错误信息")

if __name__ == "__main__":
    main() 