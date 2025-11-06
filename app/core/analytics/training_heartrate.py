"""基于心率的训练效果分析算法

参考 Banister-TRIMP 模型和训练效果评分体系（0-5分制）。

说明：
- 使用相对最大心率（%HRmax）和阈值心率（FTHR）进行强度定义
- 不使用储备心率（HRrest），简化计算
- 有氧效果（Aerobic TE）：基于 TRIMP 和 hrTSS
- 无氧效果（Anaerobic TE）：基于高强度窗口检测
- 训练焦点：根据有氧/无氧比例判断
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd


def preprocess_hr(
    hr: List[float], 
    smooth_win: int = 5
) -> np.ndarray:
    """心率预处理：去伪点 + 平滑
    
    Args:
        hr: 心率序列（bpm）
        smooth_win: 滚动平均窗口（秒），默认5秒
        
    Returns:
        处理后的心率数组
        
    预处理步骤：
        1. 去伪点：HR < 40 或 HR > 240 视为异常，裁剪到合理范围
        2. 平滑：5-15s 移动中值/均值滤波
    """
    hr_array = np.asarray(hr, dtype=float)
    
    # 去伪点：裁剪到 [40, 240] bpm
    hr_array = np.clip(hr_array, 40, 240)
    
    # 平滑：滚动平均
    series = pd.Series(hr_array).rolling(
        window=smooth_win, 
        min_periods=1, 
        center=True
    ).mean()
    
    return series.values


def relative_intensity(
    hr: np.ndarray, 
    hr_max: float
) -> np.ndarray:
    """计算相对强度（不使用储备心率）
    
    Args:
        hr: 心率序列（bpm）
        hr_max: 最大心率（bpm）
        
    Returns:
        相对强度序列 s(t) ∈ [0, 1]
        
    公式：
        s(t) = HR_s(t) / HRmax
    """
    s = hr / hr_max
    return np.clip(s, 0.0, 1.0)


def trimp_weights(
    s: np.ndarray,
    k1: float = 0.64,
    k2: float = 1.92,
    gender: str = "male"
) -> np.ndarray:
    """计算 TRIMP 权重（Banister 指数权重）
    
    Args:
        s: 相对强度序列 [0, 1]
        k1: 系数1，男性默认 0.64，女性默认 0.86
        k2: 系数2，男性默认 1.92，女性默认 1.67
        gender: 性别，"male" 或 "female"
        
    Returns:
        瞬时权重序列 w(t)
        
    公式：
        w(t) = k1 × e^(k2 × s(t))
        
    说明：
        强度越高，权重指数放大，模拟生理负荷的非线性增长
    """
    if gender.lower() == "female":
        k1, k2 = 0.86, 1.67
    
    w = k1 * np.exp(k2 * s)
    return w


def aerobic_effect(
    hr: np.ndarray,
    hr_max: float,
    fthr: float,
    dt: float = 1.0,
    gender: str = "male"
) -> Tuple[float, float, float]:
    """计算有氧训练效果（Aerobic TE，0-5分制）
    
    Args:
        hr: 心率序列（bpm）
        hr_max: 最大心率（bpm）
        fthr: 功能阈值心率 FTHR（bpm）
        dt: 采样间隔（秒），默认 1Hz
        gender: 性别，"male" 或 "female"
        
    Returns:
        (TE_aero, hrTSS, trimp) 元组
        - TE_aero: 有氧训练效果（0-5）
        - hrTSS: 类 TSS 负荷值
        - trimp: 总 TRIMP 值（分钟）
        
    算法步骤：
        1. 计算瞬时权重 w(t) = k1 × e^(k2 × s(t))
        2. 累计 TRIMP = Σ w(t) × Δt（分钟）
        3. 计算参考强度 s_FTP = FTHR / HRmax
        4. 计算 FTP@1h 的 TRIMP_ref = 60 × k1 × e^(k2 × s_FTP)
        5. hrTSS_aero = 100 × TRIMP / TRIMP_ref
        6. 映射到 TE：TE_aero = min(5, 5 × (1 - e^(-hrTSS/K_a)))
        
    经验初值：K_a = 90（相当于 hrTSS≈90 时 TE≈3.2-3.5）
    """
    # 计算相对强度
    s = relative_intensity(hr, hr_max)
    
    # 计算权重
    w = trimp_weights(s, gender=gender)
    
    # 累计 TRIMP（分钟）
    trimp = np.sum(w) * dt / 60.0
    
    # 计算参考强度（阈值心率占最大心率的百分比）
    s_ftp = fthr / hr_max
    
    # 获取对应性别的系数
    k1, k2 = (0.64, 1.92) if gender.lower() == "male" else (0.86, 1.67)
    
    # 计算 FTP@1h 的 TRIMP 参考值
    trimp_ref = 60.0 * k1 * np.exp(k2 * s_ftp)
    
    # 计算 hrTSS（类似 TSS 的负荷值）
    hrTSS = 100.0 * trimp / trimp_ref if trimp_ref > 0 else 0.0
    
    # 映射到 0-5 分制（平滑饱和函数）
    K_a = 90.0  # 经验初值
    TE_aero = min(5.0, 5.0 * (1.0 - np.exp(-hrTSS / K_a)))
    
    return TE_aero, hrTSS, trimp


def detect_intervals(
    hr: np.ndarray,
    hr_max: float,
    fthr: Optional[float] = None,
    s_threshold: float = 0.90,
    min_len: float = 10.0,
    max_len: float = 120.0,
    dt: float = 1.0
) -> Tuple[List[Tuple[int, int]], np.ndarray]:
    """检测高强度窗口（用于无氧效果计算）
    
    Args:
        hr: 心率序列（bpm）
        hr_max: 最大心率（bpm）
        fthr: 功能阈值心率（bpm），可选
        s_threshold: 强度阈值，默认 0.90（90% HRmax）
        min_len: 最小窗口长度（秒），默认 10s
        max_len: 最大窗口长度（秒），默认 120s
        dt: 采样间隔（秒）
        
    Returns:
        (segments, s) 元组
        - segments: 高强度窗口列表 [(start_idx, end_idx), ...]
        - s: 相对强度序列
        
    检测逻辑：
        - 若有 FTHR：s_thr = max(s_FTP, 0.88)（靠近至高于阈值）
        - 无 FTHR：s_thr ≈ 0.90（90% HRmax）
        - 连续样本满足 s(t) >= s_thr
        - 持续时长在 [10s, 120s] 范围内
    """
    # 计算相对强度
    s = relative_intensity(hr, hr_max)
    
    # 确定阈值强度
    if fthr:
        s_ftp = fthr / hr_max
        s_thr = max(s_ftp, 0.88)  # 至少接近阈值
    else:
        s_thr = s_threshold  # 使用默认值 0.90
    
    # 检测高强度区域
    mask = (s >= s_thr).astype(int)
    
    # 找到所有上升沿和下降沿
    diff = np.diff(np.r_[0, mask, 0])
    idx = np.where(diff != 0)[0]
    
    # 配对形成窗口 [(start, end), ...]
    segments = [(idx[i], idx[i + 1]) for i in range(0, len(idx), 2)]
    
    # 过滤持续时长在 [min_len, max_len] 范围内的窗口
    segments = [
        (a, b) for a, b in segments 
        if min_len <= (b - a) * dt <= max_len
    ]
    
    return segments, s


def anaerobic_effect(
    hr: np.ndarray,
    hr_max: float,
    fthr: float,
    dt: float = 1.0
) -> Tuple[float, float, List[Tuple[int, int]]]:
    """计算无氧训练效果（Anaerobic TE，0-5分制）
    
    Args:
        hr: 心率序列（bpm）
        hr_max: 最大心率（bpm）
        fthr: 功能阈值心率（bpm）
        dt: 采样间隔（秒）
        
    Returns:
        (TE_ana, ana_load, segments) 元组
        - TE_ana: 无氧训练效果（0-5）
        - ana_load: 累计无氧负荷
        - segments: 检测到的高强度窗口列表
        
    算法步骤：
        1. 检测高强度窗口（10-120s，s >= s_thr）
        2. 对每个窗口 i（长度 L_i 秒）：
           - 计算强度超额：u_i = (s_i - s_FTP) / (1 - s_FTP)，下限 0
           - 窗口得分：a_i = L_i × (u_i)^p × (1 + α × r_i)
             其中 p=2.0（高强度更累），α=0.5，r_i 为心率上升速率 bonus
        3. 累计负荷：A = D × Σ a_i
           D = 1 + β × max(0, 1.5 - R)（密度修正，R 为恢复比）
        4. 映射到 TE：TE_ana = min(5, 5 × (1 - e^(-A/K_n)))
        
    经验初值：K_n = 12（把 "10-15 个像样的短间歇" 映射到 3-4 的区间）
    """
    # 检测高强度窗口
    segments, s = detect_intervals(hr, hr_max, fthr, dt=dt)
    
    if not segments:
        return 0.0, 0.0, []
    
    # 计算阈值相对强度
    s_ftp = fthr / hr_max
    
    # 累计无氧负荷
    a_total = 0.0
    p = 2.0  # 强度指数（高强度更累）
    alpha = 0.5  # 心率上升速率系数
    
    for start, end in segments:
        # 窗口长度（秒）
        L_i = (end - start) * dt
        
        # 窗口内中位强度
        s_i = np.median(s[start:end])
        
        # 强度超额（归一化到 [0, 1]）
        u_i = max(0.0, (s_i - s_ftp) / (1.0 - s_ftp))
        
        # 心率上升速率 bonus（窗口内 dHR/dt 的 80% 分位数，归一化到 0-1）
        if end > start + 1:
            dhr = np.diff(hr[start:end])
            r_i = np.percentile(dhr, 80) / 10.0  # 简化：除以 10 归一化
            r_i = np.clip(r_i, 0.0, 1.0)
        else:
            r_i = 0.0
        
        # 窗口得分
        a_i = L_i * (u_i ** p) * (1.0 + alpha * r_i)
        a_total += a_i
    
    # 密度修正：短间歇的无氧刺激来自重复与密度
    # R = 平均（恢复时长 / 窗口时长）
    if len(segments) > 1:
        intervals = []
        for i in range(len(segments) - 1):
            work_len = (segments[i][1] - segments[i][0]) * dt
            rest_len = (segments[i + 1][0] - segments[i][1]) * dt
            intervals.append(rest_len / work_len if work_len > 0 else 0)
        R = np.mean(intervals) if intervals else 0
    else:
        R = 0
    
    beta = 0.3  # 密度系数
    D = 1.0 + beta * max(0.0, 1.5 - R)  # 恢复不足时增加负荷
    
    # 应用密度修正
    A = D * a_total
    
    # 映射到 0-5 分制
    K_n = 12.0  # 经验初值
    TE_ana = min(5.0, 5.0 * (1.0 - np.exp(-A / K_n)))
    
    return TE_ana, A, segments


def training_focus(
    TE_aero: float, 
    TE_ana: float,
    duration_min: float,
    s_time_in_zones: Optional[Dict[str, float]] = None
) -> str:
    """根据有氧/无氧效果判断训练焦点
    
    Args:
        TE_aero: 有氧训练效果（0-5）
        TE_ana: 无氧训练效果（0-5）
        duration_min: 训练时长（分钟）
        s_time_in_zones: 相对强度区间时长分布（可选）
        
    Returns:
        训练焦点描述字符串
        
    判断规则（优先级从上到下）：
        1. 冲刺/无氧耐力：TE_ana >= 3.0 且 TE_ana >= TE_aero + 0.5
        2. 最大摄氧量（VO2max）：TE_ana ∈ [2.0, 4.5] 且 30-90s 高强度窗口累计 >= 6 次
        3. 乳酸阈（Threshold）：区间 s ∈ [s_FTP-0.05, s_FTP+0.05] 有效时间 >= 12-20min，
           或 TE_aero >= 3.0 且 TE_ana < 2.5
        4. 节奏/高有氧（Tempo）：s ∈ [0.75, 0.88] 累计 >= 20-40min，TE_aero 主导
        5. 基础有氧（Base）：s < 0.75 占比 > 70%，且两边 TE 都 < 2.5
        6. 恢复（Recovery）：全程 s < 0.70 且总时长 > 20min
    """
    if duration_min < 5:
        return "时间过短，无法判断"
    
    # 规则 1: 冲刺/无氧耐力
    if TE_ana >= 3.0 and TE_ana >= TE_aero + 0.5:
        return "Sprint/Anaerobic"
    
    # 规则 2: 最大摄氧量
    if 2.0 <= TE_ana <= 4.5 and TE_aero >= 2.5:
        return "VO2max"
    
    # 规则 3: 乳酸阈
    if TE_aero >= 3.0 and TE_ana < 2.5:
        return "Threshold"
    
    # 规则 4: 节奏/高有氧
    if 2.0 <= TE_aero < 3.0 and TE_ana < 2.0:
        return "Tempo"
    
    # 规则 5: 基础有氧
    if TE_aero < 2.0 and TE_ana < 1.5:
        return "Base"
    
    # 规则 6: 恢复
    if TE_aero < 1.5 and TE_ana < 0.5 and duration_min > 20:
        return "Recovery"
    
    # 默认：综合耐力
    return "Mixed"


def compute_training_effect(
    hr_series: List[float],
    hr_max: float,
    fthr: Optional[float] = None,
    dt: float = 1.0,
    gender: str = "male"
) -> Dict[str, Any]:
    """计算完整的训练效果分析
    
    Args:
        hr_series: 心率序列（bpm）
        hr_max: 最大心率（bpm）
        fthr: 功能阈值心率（bpm），可选
        dt: 采样间隔（秒），默认 1Hz
        gender: 性别，"male" 或 "female"
        
    Returns:
        包含以下字段的字典：
        - TE_Aerobic: 有氧训练效果（0-5）
        - TE_Anaerobic: 无氧训练效果（0-5）
        - Training_Focus: 训练焦点描述
        - hrTSS_like: 类 TSS 负荷值
        - TRIMP: 总 TRIMP 值（分钟）
        - Ana_Load: 无氧累计负荷
        - HI_segments: 高强度窗口列表
        
    使用示例：
        >>> result = compute_training_effect(
        ...     hr_series=[120, 130, 140, 150, 160, 170, 160, 150],
        ...     hr_max=190,
        ...     fthr=170,
        ...     dt=1.0
        ... )
        >>> print(result["TE_Aerobic"], result["Training_Focus"])
    """
    if not hr_series or len(hr_series) < 10:
        return {
            "TE_Aerobic": 0.0,
            "TE_Anaerobic": 0.0,
            "Training_Focus": "数据不足",
            "hrTSS_like": 0.0,
            "TRIMP": 0.0,
            "Ana_Load": 0.0,
            "HI_segments": []
        }
    
    # 预处理心率
    hr = preprocess_hr(hr_series)
    
    # 计算训练时长（分钟）
    duration_min = len(hr) * dt / 60.0
    
    # 计算有氧训练效果
    TE_aero, hrTSS, trimp = aerobic_effect(hr, hr_max, fthr or hr_max * 0.90, dt, gender)
    
    # 计算无氧训练效果
    if fthr:
        TE_ana, ana_load, segments = anaerobic_effect(hr, hr_max, fthr, dt)
    else:
        # 无 FTHR 时，假定阈值为 90% HRmax
        TE_ana, ana_load, segments = anaerobic_effect(hr, hr_max, hr_max * 0.90, dt)
    
    # 判断训练焦点
    focus = training_focus(TE_aero, TE_ana, duration_min)
    
    return {
        "TE_Aerobic": round(TE_aero, 2),
        "TE_Anaerobic": round(TE_ana, 2),
        "Training_Focus": focus,
        "hrTSS_like": round(hrTSS, 1),
        "TRIMP": round(trimp, 1),
        "Ana_Load": round(ana_load, 2),
        "HI_segments": segments
    }

