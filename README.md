# FIT API

一个用于解析和处理 FIT 文件数据的 FastAPI 应用。

## 功能特性

- FIT 文件解析和数据提取
- 流数据 API 接口
- 支持多种数据分辨率
- 实时数据缓存
- 支持 W'平衡计算
- 支持最佳功率曲线计算

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

应用将在 `http://localhost:8000` 启动。

## API 接口

### 1. 获取活动可用的流数据类型

**接口**: `GET /activities/{activity_id}/available`

**参数**:
- `activity_id` (int): 活动ID

**响应示例**:
```json
{
  "activity_id": 106,
  "available_streams": ["power", "heartrate", "cadence", "altitude", "distance"],
  "total_streams": 4,
  "message": "获取成功"
}
```

### 2. 获取活动的流数据

**接口**: `GET /activities/{activity_id}/streams`

**参数**:
- `activity_id` (int): 活动ID
- `key` (string, 必需): 请求的流数据类型
- `resolution` (string, 可选): 数据分辨率，默认为 "high"

**支持的分辨率**:
- `low`: 低分辨率（5% 的数据点）
- `medium`: 中分辨率（25% 的数据点）
- `high`: 高分辨率（100% 的数据点）

**响应格式**:
接口返回一个数组，每个元素包含以下字段：

```json
[
  {
    "type": "power",
    "data": [5, 0, 25, 25, 100, ...],
    "series_type": "none",
    "original_size": 10879,
    "resolution": "high"
  }
]
```

**字段说明**:
- `type`: 流数据类型，与请求的 key 参数一致
- `data`: 数据数组，大小取决于 resolution 参数
- `series_type`: 系列类型，统一为 "none"
- `original_size`: 原始数据的总长度（不采样前的数据点数量）
- `resolution`: 实际使用的分辨率

**响应示例**:
```bash
# 获取功率数据（高分辨率）
curl -X GET "http://localhost:8000/activities/106/streams?key=power&resolution=high"

# 获取心率数据（中分辨率）
curl -X GET "http://localhost:8000/activities/106/streams?key=heartrate&resolution=medium"

# 获取踏频数据（低分辨率）
curl -X GET "http://localhost:8000/activities/106/streams?key=cadence&resolution=low"
```

**支持的流数据类型**:
- `power`: 功率数据（瓦特）
- `heartrate`: 心率数据（BPM）
- `cadence`: 踏频数据（RPM）
- `altitude`: 海拔数据（米，整数）
- `distance`: 距离数据（米）
- `speed`: 速度数据（千米/小时，保留一位小数）
- `temperature`: 温度数据（摄氏度）
- `best_power`: 最佳功率曲线（每秒区间最大均值，整数，忽略 resolution 参数，始终使用 high 分辨率）
- `power_hr_ratio`: 功率心率比
- `torque`: 扭矩数据（牛·米，整数）
- `spi`: SPI数据（瓦特/转，保留两位小数）
- `w_balance`: W'平衡数据（千焦，保留一位小数）
- `vam`: VAM数据（米/小时，整数）
- `latitude`: 纬度数据
- `longitude`: 经度数据

### 3. 获取活动的多个流数据

**接口**: `POST /activities/{activity_id}/streams`

**参数**:
- `activity_id` (int): 活动ID
- `keys` (array[string], 必需): 请求的流数据类型数组
- `resolution` (string, 必需): 数据分辨率

**支持的分辨率**:
- `low`: 低分辨率（5% 的数据点）
- `medium`: 中分辨率（25% 的数据点）
- `high`: 高分辨率（100% 的数据点）

**请求格式**:
```json
{
  "keys": ["heartrate", "distance", "altitude"],
  "resolution": "high"
}
```

**响应格式**:
```json
{
  "data": [
    {
      "type": "heartrate",
      "data": [120, 125, 130, ...]
    },
    {
      "type": "distance",
      "data": [0, 16.8, 33.6, ...]
    },
    {
      "type": "altitude",
      "data": [92.4, 93.4, 94.2, ...]
    }
  ]
}
```

**字段说明**:
- `type`: 流数据类型
- `data`: 流数据数组，如果请求的字段不存在则为 `null`

**响应示例**:
```bash
# 获取多个流数据（高分辨率）
curl -X POST "http://localhost:8000/activities/106/streams" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["heartrate", "power", "speed"], "resolution": "high"}'

# 获取多个流数据（中分辨率）
curl -X POST "http://localhost:8000/activities/106/streams" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["altitude", "cadence"], "resolution": "medium"}'
```

**错误处理**:
- **400 Bad Request**: 无效的分辨率参数
- **404 Not Found**: 活动不存在
- **500 Internal Server Error**: 服务器内部错误

### 4. 获取活动的总体信息

**接口**: `GET /activities/{activity_id}/overall`

**参数**:
- `activity_id` (int): 活动ID

**响应格式**:
```json
{
  "distance": 25.67,
  "moving_time": "01:23:45",
  "average_speed": 18.5,
  "elevation_gain": 450.2,
  "avg_power": 180,
  "calories": 850,
  "training_load": 45.2,
  "status": null,
  "avg_heartrate": 145,
  "max_altitude": 1250
}
```

**字段说明**:
- `distance`: 距离（千米，保留两位小数）
- `moving_time`: 移动时间（格式化字符串，HH:MM:SS）
- `average_speed`: 平均速度（千米每小时，保留一位小数）
- `elevation_gain`: 爬升海拔（米，保留一位小数）
- `avg_power`: 平均功率（瓦特，保留整数）
- `calories`: 卡路里（估算值，保留整数）
- `training_load`: 训练负荷（无单位，基于FTP计算）
- `status`: 状态值（始终为null）
- `avg_heartrate`: 平均心率（保留整数）
- `max_altitude`: 最高海拔（米，保留整数）

**数据来源优先级**:
1. 优先使用FIT文件session段中的数据
2. 如果session段数据不存在，则从流数据中计算

**响应示例**:
```bash
# 获取活动总体信息
curl -X GET "http://localhost:8000/activities/106/overall"
```

**错误处理**:
- **404 Not Found**: 活动信息不存在或无法解析
- **500 Internal Server Error**: 服务器内部错误

### 5. 获取活动的所有数据

**接口**: `GET /activities/{activity_id}/all`

**参数**:
- `activity_id` (int): 活动ID

**响应格式**:
```json
{
  "overall": { /* 总体信息 */ },
  "power": { /* 功率信息 */ },
  "heartrate": { /* 心率信息 */ },
  "cadence": { /* 踏频信息 */ },
  "speed": { /* 速度信息 */ },
  "training_effect": { /* 训练效果信息 */ },
  "altitude": { /* 海拔信息 */ },
  "temperature": { /* 温度信息 */ },
  "zones": { /* 区间分析信息 */ },
  "best_power": { /* 最佳功率信息 */ }
}
```

**字段说明**:
- `overall`: 总体信息（同 `/overall` 接口）
- `power`: 功率信息（同 `/power` 接口）
- `heartrate`: 心率信息（同 `/heartrate` 接口）
- `cadence`: 踏频信息（同 `/cadence` 接口）
- `speed`: 速度信息（同 `/speed` 接口）
- `training_effect`: 训练效果信息（同 `/training_effect` 接口）
- `altitude`: 海拔信息（同 `/altitude` 接口）
- `temperature`: 温度信息（同 `/temperature` 接口）
- `zones`: 区间分析信息（包含功率和心率区间数据）
- `best_powers`: 最佳功率信息（同 `/best_power` 接口）

**特点**:
- 一次性获取活动的所有数据
- 如果某个字段数据不存在，则返回 `null`
- 按照固定顺序返回字段：overall、power、heartrate、cadence、speed、training_effect、altitude、temperature、zones、best_powers

**响应示例**:
```bash
# 获取活动所有数据
curl -X GET "http://localhost:8000/activities/106/all"
```

**错误处理**:
- **404 Not Found**: 活动不存在
- **500 Internal Server Error**: 服务器内部错误

### 6. 获取活动的区间分析数据

**接口**: `GET /activities/{activity_id}/zones`

**参数**:
- `activity_id` (int): 活动ID
- `key` (string, 必需): 区间类型，支持 "power" 或 "heartrate"

**响应格式**:
```json
{
  "zones": [
    {
      "distribution_buckets": [
        {
          "min": 0,
          "max": 137,
          "time": "12:34:56",
          "percentage": "45.2%"
        },
        {
          "min": 137,
          "max": 187,
          "time": "8:45:30",
          "percentage": "31.8%"
        }
      ],
      "type": "power"
    }
  ]
}
```

**字段说明**:
- `distribution_buckets`: 区间分布桶列表
  - `min`: 区间最小值
  - `max`: 区间最大值
  - `time`: 在该区间的时间（格式化字符串，如 "1:23:45" 或 "45s"）
  - `percentage`: 该区间占总时长的百分比，如 "12.5%"
- `type`: 区间类型（"power" 或 "heartrate"）

**区间定义**:

**功率区间（基于FTP的7个区间）**:
- Zone 1: < 55% FTP
- Zone 2: 55-75% FTP
- Zone 3: 75-90% FTP
- Zone 4: 90-105% FTP
- Zone 5: 105-120% FTP
- Zone 6: 120-150% FTP
- Zone 7: 150-200% FTP

**心率区间（基于最大心率的5个区间）**:
- Zone 1: < 60% Max HR
- Zone 2: 60-70% Max HR
- Zone 3: 70-80% Max HR
- Zone 4: 80-90% Max HR
- Zone 5: 90-100% Max HR

**响应示例**:
```bash
# 获取功率区间分析
curl -X GET "http://localhost:8000/activities/106/zones?key=power"

# 获取心率区间分析
curl -X GET "http://localhost:8000/activities/106/zones?key=heartrate"
```

**错误处理**:
- **404 Not Found**: 活动或运动员信息不存在
- **400 Bad Request**: FTP或最大心率数据不存在或无效，或活动数据不存在
- **500 Internal Server Error**: 服务器内部错误

## 数据格式说明

### 数据类型和精度

- **altitude**: 海拔数据保留到整数（米）
- **speed**: 速度数据转换为千米/小时并保留一位小数
- **vam**: VAM数据保留到整数（米/小时）
- **w_balance**: W'平衡数据保留一位小数（千焦）
- **best_power**: 最佳功率曲线数据（瓦特，整数）

### 特殊字段说明

#### W'平衡 (w_balance)
- 需要从 `tb_athlete` 表获取运动员的 FTP 和 W'值
- 使用 Skiba 模型计算无氧储备的消耗和恢复
- 返回格式为数组，每个元素表示该时刻的 W'平衡值

#### 最佳功率曲线 (best_power)
- 计算每秒区间的最大平均功率
- 数据保留到整数（瓦特）
- 忽略 resolution 参数，始终使用 high 分辨率返回完整数据
- 返回格式为数组，索引 i 表示 i+1 秒内的最大平均功率

## 数据采样说明

- **original_size**: 表示原始 FIT 文件中的数据点总数，与采样率无关
- **data 数组大小**: 根据 resolution 参数进行采样：
  - `low`: 约 5% 的数据点
  - `medium`: 约 25% 的数据点
  - `high`: 100% 的数据点

## 错误处理

### 常见错误码

- **404 Not Found**: 活动不存在或文件未找到
- **422 Unprocessable Entity**: 参数验证失败（如无效的 resolution 值）
- **500 Internal Server Error**: 服务器内部错误

### 特殊响应

- **空数组 `[]`**: 当请求的字段在该活动中不存在时返回

## 故障排除

### 1. 422 错误
如果遇到 422 错误，请检查：
- `resolution` 参数是否为有效值（`low`, `medium`, `high`）
- 参数名称是否正确

### 2. 404 错误
如果遇到 404 错误，请检查：
- 活动ID是否存在
- FIT 文件是否已正确上传

### 3. 空数据
如果返回空数组，说明：
- 该活动不包含请求的流数据类型
- 数据可能已损坏或格式不支持

### 4. W'平衡计算
如果 w_balance 字段返回全零数据，请检查：
- `tb_athlete` 表中是否有对应的运动员数据
- 运动员数据中是否包含有效的 FTP 和 W'值

## 测试

运行测试脚本验证接口功能：

```bash
# 测试流数据接口
python3 test_api_simulation.py

# 测试活动总体信息接口
python3 test_overall_api.py
```

这些脚本会测试所有字段和分辨率组合，并验证数据格式的正确性。

## 开发说明

### 项目结构

```
FIT-API-NEW/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── streams/             # 流数据相关模块
│   │   ├── router.py        # API 路由
│   │   ├── crud.py          # 数据操作
│   │   ├── models.py        # 数据模型
│   │   ├── schemas.py       # 数据验证
│   │   └── fit_parser.py    # FIT 文件解析
│   ├── activities/          # 活动相关模块
│   │   ├── router.py        # API 路由
│   │   ├── crud.py          # 数据操作
│   │   ├── models.py        # 数据模型
│   │   ├── schemas.py       # 数据验证
│   │   └── zone_analyzer.py # 区间分析器
│   └── utils.py             # 工具函数
├── fit_files/               # FIT 文件目录
├── test_api_simulation.py   # 测试脚本
└── README.md               # 项目文档
```

### 数据流程

1. 客户端请求特定活动的流数据
2. 系统检查活动是否存在
3. 验证请求的字段是否可用
4. 根据分辨率参数对数据进行采样
5. 返回标准化的数组格式响应

### 数据库表结构

#### tb_activity 表
- `id`: 活动ID
- `upload_fit_url`: FIT文件下载URL

#### tb_athlete 表
- `id`: 运动员ID
- `max_heartrate`: 最大心率
- `ftp`: 功能阈值功率
- `w_balance`: W'平衡值（用于 w_balance 计算） 