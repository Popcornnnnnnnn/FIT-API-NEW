#!/usr/bin/env python3
"""
快速测试数据库连接和API可用性
"""

import time
import requests
import sys
from sqlalchemy import create_engine, text

# 导入配置
try:
    from batch_config import DB_CONFIG, API_CONFIG, PROCESSING_CONFIG
except ImportError:
    print("❌ 配置文件 batch_config.py 不存在")
    sys.exit(1)

def test_database_connection():
    """测试数据库连接"""
    print("测试数据库连接...")
    
    try:
        db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 测试查询运动员43的活动数量
            query = text("SELECT COUNT(*) FROM tb_activity WHERE athlete_id = :athlete_id")
            result = conn.execute(query, {"athlete_id": PROCESSING_CONFIG['athlete_id']})
            count = result.scalar()
            
            print(f"✅ 数据库连接成功")
            print(f"   运动员 {PROCESSING_CONFIG['athlete_id']} 有 {count} 个活动")
            return True
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

def test_api_connection():
    """测试API连接"""
    print("\n测试API连接...")
    
    try:
        # 测试一个简单的API调用
        url = f"{API_CONFIG['base_url']}/activities/cache/status"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            print("✅ API服务器连接成功")
            return True
        else:
            print(f"❌ API服务器响应异常: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API服务器连接失败: {e}")
        return False

def test_single_activity():
    """测试单个活动API调用"""
    print("\n测试单个活动API调用...")
    
    try:
        # 先获取一个活动ID
        db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            query = text("SELECT id FROM tb_activity WHERE athlete_id = :athlete_id LIMIT 1")
            result = conn.execute(query, {"athlete_id": PROCESSING_CONFIG['athlete_id']})
            activity_id = result.scalar()
            
            if not activity_id:
                print(f"❌ 未找到运动员 {PROCESSING_CONFIG['athlete_id']} 的活动")
                return False
            
            # 测试API调用
            url = f"{API_CONFIG['base_url']}/activities/{activity_id}/all"
            params = {
                'access_token': API_CONFIG['access_token'],
                'resolution': 'high'
            }
            
            print(f"   测试活动ID: {activity_id}")
            start_time = time.time()
            response = requests.get(url, params=params, timeout=30)
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                # 检查缓存信息
                try:
                    response_data = response.json()
                    cache_hit = False
                    source_info = "未知"
                    
                    if 'data' in response_data and 'source' in response_data.get('data', {}):
                        source_info = response_data['data']['source']
                        cache_hit = source_info == "cache"
                    
                    cache_header = response.headers.get('X-Cache', '').lower()
                    if 'hit' in cache_header:
                        cache_hit = True
                        source_info = "HTTP缓存"
                    
                    cache_status = "(缓存命中)" if cache_hit else "(实时数据)"
                    print(f"✅ 单个活动API调用成功 {cache_status} - 耗时: {duration:.2f}秒")
                except:
                    print(f"✅ 单个活动API调用成功 - 耗时: {duration:.2f}秒")
                return True
            else:
                print(f"❌ 单个活动API调用失败: HTTP {response.status_code} - 耗时: {duration:.2f}秒")
                print(f"   响应: {response.text[:200]}...")
                return False
                
    except Exception as e:
        print(f"❌ 测试单个活动失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("批量处理脚本环境测试")
    print("=" * 50)
    
    # 显示配置信息
    print(f"数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"API服务器: {API_CONFIG['base_url']}")
    print(f"目标运动员: {PROCESSING_CONFIG['athlete_id']}")
    print(f"Access Token: {API_CONFIG['access_token'][:20]}...")
    print("-" * 50)
    
    # 执行测试
    db_ok = test_database_connection()
    api_ok = test_api_connection()
    activity_ok = test_single_activity()
    
    print("\n" + "=" * 50)
    print("测试结果总结:")
    print(f"数据库连接: {'✅ 通过' if db_ok else '❌ 失败'}")
    print(f"API服务器: {'✅ 通过' if api_ok else '❌ 失败'}")
    print(f"活动API调用: {'✅ 通过' if activity_ok else '❌ 失败'}")
    
    if db_ok and api_ok and activity_ok:
        print("\n🎉 所有测试通过！可以运行批量处理脚本")
        print("运行命令: python batch_process_athlete_43.py")
    else:
        print("\n⚠️  部分测试失败，请检查配置和服务器状态")
        if not db_ok:
            print("   - 检查数据库连接配置")
        if not api_ok:
            print("   - 检查API服务器是否运行")
        if not activity_ok:
            print("   - 检查access_token是否有效")

if __name__ == "__main__":
    main()
