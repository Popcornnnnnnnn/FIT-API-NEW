#!/usr/bin/env python3
"""
活动数据缓存系统测试脚本

用于测试缓存系统的各项功能
"""

import requests
import json
import time
from typing import Dict, Any

class CacheSystemTester:
    """缓存系统测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
    
    def test_cache_hit(self, activity_id: int, resolution: str = "high") -> Dict[str, Any]:
        """测试缓存命中"""
        print(f"🧪 测试活动 {activity_id} 的缓存命中 (resolution: {resolution})...")
        
        # 第一次请求（应该缓存未命中）
        start_time = time.time()
        response1 = requests.get(f"{self.base_url}/activities/{activity_id}/all?resolution={resolution}")
        first_request_time = time.time() - start_time
        
        if response1.status_code != 200:
            return {
                "test": "cache_hit",
                "activity_id": activity_id,
                "status": "failed",
                "error": f"第一次请求失败: {response1.status_code}"
            }
        
        # 等待一下，确保缓存写入完成
        time.sleep(1)
        
        # 第二次请求（应该缓存命中）
        start_time = time.time()
        response2 = requests.get(f"{self.base_url}/activities/{activity_id}/all?resolution={resolution}")
        second_request_time = time.time() - start_time
        
        if response2.status_code != 200:
            return {
                "test": "cache_hit",
                "activity_id": activity_id,
                "status": "failed",
                "error": f"第二次请求失败: {response2.status_code}"
            }
        
        # 比较响应时间
        time_improvement = first_request_time / second_request_time if second_request_time > 0 else 0
        
        # 检查响应内容是否一致
        content_match = response1.json() == response2.json()
        
        result = {
            "test": "cache_hit",
            "activity_id": activity_id,
            "resolution": resolution,
            "status": "success",
            "first_request_time": round(first_request_time, 3),
            "second_request_time": round(second_request_time, 3),
            "time_improvement": round(time_improvement, 2),
            "content_match": content_match
        }
        
        if time_improvement > 1.5:  # 缓存命中应该明显更快
            result["cache_working"] = True
            print(f"✅ 缓存命中测试通过: 第二次请求快了 {time_improvement:.2f}x")
        else:
            result["cache_working"] = False
            print(f"⚠️ 缓存可能未生效: 时间改善不明显 ({time_improvement:.2f}x)")
        
        return result
    
    def test_cache_management(self) -> Dict[str, Any]:
        """测试缓存管理接口"""
        print("🧪 测试缓存管理接口...")
        
        results = {}
        
        # 测试获取缓存统计
        try:
            response = requests.get(f"{self.base_url}/activities/cache/stats")
            if response.status_code == 200:
                stats = response.json()
                results["stats"] = {
                    "status": "success",
                    "data": stats
                }
                print(f"✅ 缓存统计接口正常: {stats}")
            else:
                results["stats"] = {
                    "status": "failed",
                    "error": f"状态码: {response.status_code}"
                }
                print(f"❌ 缓存统计接口失败: {response.status_code}")
        except Exception as e:
            results["stats"] = {
                "status": "failed",
                "error": str(e)
            }
            print(f"❌ 缓存统计接口异常: {e}")
        
        return {
            "test": "cache_management",
            "status": "success",
            "results": results
        }
    
    def test_cache_cleanup(self) -> Dict[str, Any]:
        """测试缓存清理接口"""
        print("🧪 测试缓存清理接口...")
        
        try:
            response = requests.post(f"{self.base_url}/activities/cache/cleanup")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 缓存清理接口正常: {result}")
                return {
                    "test": "cache_cleanup",
                    "status": "success",
                    "data": result
                }
            else:
                print(f"❌ 缓存清理接口失败: {response.status_code}")
                return {
                    "test": "cache_cleanup",
                    "status": "failed",
                    "error": f"状态码: {response.status_code}"
                }
        except Exception as e:
            print(f"❌ 缓存清理接口异常: {e}")
            return {
                "test": "cache_cleanup",
                "status": "failed",
                "error": str(e)
            }
    
    def run_all_tests(self, activity_ids: list = None) -> Dict[str, Any]:
        """运行所有测试"""
        if activity_ids is None:
            activity_ids = [12345, 67890]  # 默认测试活动ID
        
        print("🚀 开始运行缓存系统测试...")
        print(f"📡 测试目标: {self.base_url}")
        print(f"🎯 测试活动: {activity_ids}")
        print("-" * 50)
        
        # 测试缓存管理接口
        self.test_results.append(self.test_cache_management())
        
        # 测试缓存清理接口
        self.test_results.append(self.test_cache_cleanup())
        
        # 测试缓存命中
        for activity_id in activity_ids:
            try:
                # 测试高分辨率缓存
                result = self.test_cache_hit(activity_id, "high")
                self.test_results.append(result)
                
                # 测试中分辨率缓存（验证不同分辨率的缓存隔离）
                result = self.test_cache_hit(activity_id, "medium")
                self.test_results.append(result)
                
            except Exception as e:
                error_result = {
                    "test": "cache_hit",
                    "activity_id": activity_id,
                    "resolution": "unknown",
                    "status": "failed",
                    "error": str(e)
                }
                self.test_results.append(error_result)
                print(f"❌ 测试活动 {activity_id} 时发生异常: {e}")
        
        # 生成测试报告
        report = self.generate_report()
        
        print("-" * 50)
        print("📊 测试完成！")
        print(f"✅ 成功: {report['success_count']}")
        print(f"❌ 失败: {report['failure_count']}")
        print(f"📈 缓存命中率: {report['cache_hit_rate']:.1f}%")
        
        return report
    
    def generate_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total_tests = len(self.test_results)
        success_count = sum(1 for r in self.test_results if r.get("status") == "success")
        failure_count = total_tests - success_count
        
        # 计算缓存命中率
        cache_tests = [r for r in self.test_results if r.get("test") == "cache_hit"]
        cache_working_count = sum(1 for r in cache_tests if r.get("cache_working", False))
        cache_hit_rate = (cache_working_count / len(cache_tests) * 100) if cache_tests else 0
        
        return {
            "total_tests": total_tests,
            "success_count": success_count,
            "failure_count": failure_count,
            "cache_hit_rate": cache_hit_rate,
            "test_results": self.test_results
        }

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="活动数据缓存系统测试")
    parser.add_argument("--url", default="http://localhost:8000", help="API基础URL")
    parser.add_argument("--activities", nargs="+", type=int, help="要测试的活动ID列表")
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = CacheSystemTester(args.url)
    
    # 运行测试
    if args.activities:
        report = tester.run_all_tests(args.activities)
    else:
        report = tester.run_all_tests()
    
    # 保存测试报告
    report_file = f"cache_test_report_{int(time.time())}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"📄 测试报告已保存到: {report_file}")
    
    # 返回退出码
    return 0 if report['failure_count'] == 0 else 1

if __name__ == "__main__":
    exit(main())
