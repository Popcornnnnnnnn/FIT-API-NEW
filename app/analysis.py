from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/summary/{activity_id}")
def get_activity_summary(activity_id: int):
    # TODO: 实现真实分析逻辑
    return {
        "activity_id": activity_id,
        "distance_km": 42.2,
        "duration_min": 180,
        "avg_power": 200,
        "avg_hr": 150
    }

@router.get("/stream/{activity_id}")
def get_activity_stream(activity_id: int, sample_rate: int = 1):
    # TODO: 返回流数据
    return {
        "activity_id": activity_id,
        "stream": [
            {"time": i, "power": 200 + i % 10, "hr": 150 + i % 5} for i in range(0, 100, sample_rate)
        ]
    }

@router.get("/advanced/{activity_id}")
def get_advanced_metrics(activity_id: int):
    # TODO: 计算NP, IF, TSS等
    return {
        "activity_id": activity_id,
        "NP": 220,
        "IF": 0.85,
        "TSS": 120,
        "hr_zones": {"zone1": 30, "zone2": 50, "zone3": 20}
    } 