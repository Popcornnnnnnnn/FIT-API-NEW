# 最佳成绩记录功能

## 功能概述

本功能在每次上传文件（无论是通过原始FIT还是Strava获取）时，自动检查是否有分段功率或速度刷新的历史记录，并在数据库的`tb_athlete_best_efforts`表中更新对应项。

## 支持的最佳成绩类型

### 分段时间功率记录
- 5s, 10s, 15s, 20s, 30s, 40s, 60s
- 2m, 3m, 5m, 10m, 15m, 20m, 30m, 40m
- 1h, 2h, 3h, 4h

### 分段距离速度记录
- 5km, 10km, 20km, 30km, 40km
- 50km, 60km, 70km, 80km, 90km, 100km

## 自动触发

最佳成绩更新会在以下情况下自动触发：

1. **本地数据库查询时**：调用 `/activities/{activity_id}/all` 接口（无access_token）
2. **Strava API查询时**：调用 `/activities/{activity_id}/all` 接口（有access_token）

### 返回内容更新

当有新的最佳成绩记录时，`/all` 接口的返回内容会包含 `best_efforts_update` 字段：

```json
{
  "overall": {...},
  "power": {...},
  "best_efforts_update": {
    "success": true,
    "new_records": {
      "power_records": {
        "5s": {"power": 800, "activity_id": 123},
        "30s": {"power": 600, "activity_id": 123}
      },
      "speed_records": {
        "5km": {"speed": 12.5, "activity_id": 123}
      }
    },
    "message": "活动123的最佳成绩记录已更新"
  }
}
```

## 手动触发

### 更新指定活动的最佳成绩
```http
POST /activities/{activity_id}/update-best-efforts
```

**返回格式**：
```json
{
  "message": "活动 123 的最佳成绩更新成功",
  "data": {
    "activity_id": 123,
    "status": "success",
    "new_records": {
      "power_records": {
        "5s": {"power": 800, "activity_id": 123}
      },
      "speed_records": {
        "5km": {"speed": 12.5, "activity_id": 123}
      }
    }
  }
}
```

### 查看运动员的最佳成绩记录
```http
GET /activities/{activity_id}/athlete-best-efforts
```

## 数据来源

系统会从以下数据源计算最佳成绩：

1. **流数据**：从FIT文件解析的原始流数据
   - 使用滑动窗口计算分段时间功率
   - 使用距离分段计算分段距离速度

2. **Lap数据**：从FIT文件解析的lap数据
   - 直接使用lap的平均功率和速度
   - 允许时间误差±5秒，距离误差±100米

## 数据库表结构

`tb_athlete_best_efforts` 表包含：
- `athlete_id`：运动员ID（主键）
- `best_power_*`：各时间段的最佳功率记录
- `best_power_*_activity_id`：对应活动ID
- `best_speed_*`：各距离段的最佳速度记录
- `best_speed_*_activity_id`：对应活动ID
- `created_at`、`updated_at`：时间戳

## 日志输出

系统会输出详细的日志信息：
- 🏆 [新记录]：发现新的最佳成绩
- 🏆 [Lap新记录]：从lap数据发现的新记录
- ✅ [最佳成绩更新]：成功更新记录
- ℹ️ [无新记录]：未发现新记录
- ❌ [最佳成绩更新失败]：更新失败

## 缓存机制

- lap数据会被缓存，避免重复下载FIT文件
- 缓存键格式：`lap_{activity_id}`
- 缓存TTL：1小时（可配置）

## 注意事项

1. 最佳成绩更新是异步进行的，不会影响主要API响应时间
2. 如果更新失败，会记录错误日志但不影响主要功能
3. 系统会自动创建运动员的最佳成绩记录（如果不存在）
4. 外键约束确保数据完整性
