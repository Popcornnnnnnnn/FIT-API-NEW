"""跑步配速分析核心算法

说明：
- NGP（标准化坡度配速）：考虑坡度影响的标准化配速
- 用于跑步活动的训练负荷计算（rTSS）
- 基于专业版（可复现/可校准）方法实现
"""

from typing import List, Optional
import numpy as np
import re


def parse_pace_string(pace_str: str) -> Optional[int]:
    """
    解析配速字符串，只支持 "分钟:秒" 格式
    
    支持的格式：
    - "3:40" (分钟:秒) -> 返回 220 (秒/公里)
    
    参数：
        pace_str: 配速字符串
    
    返回：
        配速（秒/公里，整数），如果解析失败返回None
    """
    if not pace_str or not isinstance(pace_str, str):
        return None
    
    pace_str = pace_str.strip()
    if not pace_str:
        return None
    
    # 只解析 "分钟:秒" 格式，如 "3:40"
    match = re.match(r'^(\d+):(\d+)$', pace_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        total_seconds = minutes * 60 + seconds
        
        # 配速通常在120-600秒/公里之间（2-10分钟/公里），超出这个范围可能是格式错误
        if 120 <= total_seconds <= 600:
            return int(total_seconds)
        # 如果小于120秒，也可能是合理的（快速配速）
        elif total_seconds < 120:
            return int(total_seconds)
        else:
            # 大于600秒可能格式有误
            return None
    
    return None


def calculate_grade_from_track(
    altitudes: List[float],
    distances: List[float],
    window_meters: float = 30.0,
) -> List[float]:
    """
    从轨迹计算坡度
    
    使用距离窗口（默认30米）计算局部斜率，定义为高程变化/距离变化。
    计算后进行平滑处理以去除噪声。
    
    参数：
        altitudes: 海拔序列（米），假定1Hz采样
        distances: 累计距离序列（米）
        window_meters: 坡度计算窗口长度（米），默认30米
    
    返回：
        坡度百分比序列（%），正值表示上坡，负值表示下坡
    """
    if not altitudes or not distances or len(altitudes) != len(distances):
        return []
    
    n = len(altitudes)
    if n < 2:
        return [0.0] * n
    
    grades: List[float] = []
    
    for i in range(n):
        # 找到窗口范围内的点
        target_dist = distances[i]
        start_idx = i
        end_idx = i
        
        # 向前查找
        while start_idx > 0 and (target_dist - distances[start_idx]) < window_meters / 2:
            start_idx -= 1
        
        # 向后查找
        while end_idx < n - 1 and (distances[end_idx] - target_dist) < window_meters / 2:
            end_idx += 1
        
        if end_idx > start_idx:
            delta_alt = altitudes[end_idx] - altitudes[start_idx]
            delta_dist = distances[end_idx] - distances[start_idx]
            if delta_dist > 0:
                grade_pct = (delta_alt / delta_dist) * 100.0
                grades.append(grade_pct)
            else:
                grades.append(0.0)
        else:
            grades.append(0.0)
    
    # 平滑处理（简单的移动平均）
    if len(grades) > 3:
        smoothed = []
        for i in range(len(grades)):
            start = max(0, i - 1)
            end = min(len(grades), i + 2)
            smoothed.append(np.mean(grades[start:end]))
        return smoothed
    
    return grades


def calculate_adjustment_factor(grade_pct: float) -> float:
    """
    定义代价因子 adj_factor(grade)
    
    基于分段二次模型计算调整因子：
    - 上坡: adj = 1 + 4.5 * g + 2 * g²
    - 下坡: adj = 1 + 1.5 * g + 3 * g²
    
    其中 g 为小数坡度（坡度百分比 / 100）
    
    坡度被限制在 [-15%, 15%] 范围内以避免极值影响。
    
    参数：
        grade_pct: 坡度百分比（%）
    
    返回：
        调整因子，adj > 1 表示比平地更耗能，adj < 1 表示比平地更省力
    """
    # 限制坡度范围
    g = np.clip(grade_pct, -15.0, 15.0) / 100.0  # 转换为小数坡度
    
    if g >= 0:
        # 上坡
        adj = 1.0 + 4.5 * g + 2.0 * (g ** 2)
    else:
        # 下坡
        adj = 1.0 + 1.5 * g + 3.0 * (g ** 2)
    
    return float(adj)


def calculate_normalized_graded_pace(
    speeds: List[float],  # 速度（米/秒）
    altitudes: List[float],  # 海拔（米）
    distances: List[float],  # 累计距离（米）
    window_meters: float = 30.0,  # 坡度计算窗口（米）
) -> Optional[float]:
    """
    计算标准化坡度配速（NGP）
    
    步骤：
    1. 从轨迹计算坡度
    2. 计算每一点的调整因子
    3. 计算等效平路时间
    4. 计算NGP速度并转换为配速（秒/公里）
    
    参数：
        speeds: 速度序列（m/s），假定1Hz采样
        altitudes: 海拔序列（m）
        distances: 累计距离序列（m）
        window_meters: 坡度计算窗口长度（米），默认30米
    
    返回：
        NGP配速（秒/公里），如果输入不合法返回None
    """
    if not speeds or not altitudes or not distances:
        return None
    
    n = min(len(speeds), len(altitudes), len(distances))
    if n < 2:
        return None
    
    # 确保所有序列长度一致
    speeds_arr = np.array(speeds[:n])
    altitudes_arr = np.array(altitudes[:n])
    distances_arr = np.array(distances[:n])
    
    # 1. 计算坡度
    grades = calculate_grade_from_track(
        altitudes_arr.tolist(),
        distances_arr.tolist(),
        window_meters
    )
    
    if not grades:
        return None
    
    # 2. 计算每一点的调整因子
    adj_factors = [calculate_adjustment_factor(g) for g in grades]
    
    # 3. 计算等效平路时间
    # 假设每秒采样一次，dt = 1秒
    # time_eq = Σ(dt * adj) = Σ(1 * adj)
    time_eq = sum(adj_factors)
    
    if time_eq <= 0:
        return None
    
    # 4. 计算总距离
    total_distance = distances_arr[-1] - distances_arr[0]  # 米
    if total_distance <= 0:
        return None
    
    # 5. 计算NGP速度（米/秒）
    ngp_speed_ms = total_distance / time_eq
    
    # 6. 转换为配速（秒/公里）
    # 配速 = 距离（米） / 速度（米/秒） = 1000 / (ngp_speed_ms) 秒/公里
    if ngp_speed_ms > 0:
        ngp_pace_sec_per_km = 1000.0 / ngp_speed_ms
        return float(ngp_pace_sec_per_km)
    
    return None


def calculate_running_intensity_factor(
    ngp: float,
    ft_pace: int
) -> Optional[float]:
    """
    计算跑步强度因子（IF）
    
    公式：IF = 阈值配速 / NGP
    
    注意：配速越小表示越快，所以比值越大表示强度越高
    
    参数：
        ngp: 标准化坡度配速（秒/公里）
        ft_pace: 阈值配速（秒/公里）
    
    返回：
        强度因子，如果输入不合法返回None
    """
    if not ft_pace or ft_pace <= 0 or not ngp or ngp <= 0:
        return None
    
    intensity_factor = ft_pace / ngp
    return float(intensity_factor)
