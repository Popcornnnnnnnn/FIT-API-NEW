#!/usr/bin/env python3
"""
测试逗号分隔的 keys 参数格式
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_keys_parsing():
    """测试 keys 参数的解析逻辑"""
    
    # 模拟不同的 keys 参数输入
    test_cases = [
        ("time,distance,watts,heartrate", ["time", "distance", "watts", "heartrate"]),
        ("watts,cadence", ["watts", "cadence"]),
        ("best_power,torque,spi", ["best_power", "torque", "spi"]),
        ("latitude,longitude", ["latitude", "longitude"]),
        ("time, distance, watts", ["time", "distance", "watts"]),  # 测试空格
        ("", None),  # 空字符串
        (None, None),  # None 值
    ]
    
    print("测试 keys 参数解析:")
    print("=" * 50)
    
    for i, (input_keys, expected) in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: '{input_keys}'")
        
        # 模拟解析逻辑
        if input_keys:
            keys_list = [key.strip() for key in input_keys.split(',') if key.strip()]
        else:
            # 如果 keys 为空，返回所有可用的字段
            keys_list = ['time', 'distance', 'latlng', 'altitude', 'velocity_smooth', 'heartrate', 'cadence', 'watts', 'temp', 'moving', 'grade_smooth', 'best_power', 'torque', 'spi', 'power_hr_ratio', 'w_balance', 'vam']
        
        print(f"  解析结果: {keys_list}")
        if expected:
            print(f"  期望结果: {expected}")
            if keys_list == expected:
                print("  ✅ 通过")
            else:
                print("  ❌ 失败")
        else:
            print(f"  返回所有字段: {len(keys_list)} 个字段")
    
    print("\n测试完成!")

if __name__ == "__main__":
    test_keys_parsing()
