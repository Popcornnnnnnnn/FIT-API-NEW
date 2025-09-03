# 最佳成绩记录功能增强 - 更新日志

## 更新内容
在调用 `/all` 接口时，不仅更新最佳成绩，还在返回内容中添加刷新的最佳成绩信息。

## 主要修改

### 1. app/activities/crud.py
- **修改函数**: `calculate_and_update_best_efforts()` 
  - 返回类型从 `bool` 改为 `Dict[str, Any]`
  - 返回格式：
    ```python
    {
        "success": True/False,
        "new_records": {
            "power_records": {
                "5s": {"power": 800, "activity_id": 123},
                "30s": {"power": 600, "activity_id": 123}
            },
            "speed_records": {
                "5km": {"speed": 12.5, "activity_id": 123}
            }
        },
        "message": "更新信息"
    }
    ```

### 2. app/activities/data_manager.py
- **修改方法**: `update_best_efforts()`
  - 返回类型从 `bool` 改为 `Dict[str, Any]`
  - 返回相同的字典格式

### 3. app/activities/schemas.py
- **修改模型**: `AllActivityDataResponse`
  - 新增字段：`best_efforts_update: Optional[Dict[str, Any]]`
  - 描述：最佳成绩更新信息，包含新刷新的功率和速度记录

### 4. app/activities/router.py
- **修改接口**: `get_activity_all_data()`
  - 本地数据库查询时：捕获最佳成绩更新结果并添加到响应中
  - Strava API查询时：同样捕获并添加最佳成绩更新信息
- **修改接口**: `update_activity_best_efforts()`
  - 返回格式更新，包含新的最佳成绩记录信息

## 返回内容示例

### /all 接口返回（有新的最佳成绩时）
```json
{
  "overall": {...},
  "power": {...},
  "heartrate": {...},
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

### /all 接口返回（无新的最佳成绩时）
```json
{
  "overall": {...},
  "power": {...},
  "heartrate": {...}
  // 不包含 best_efforts_update 字段
}
```

### 手动更新接口返回
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

## 功能特点

1. **自动检测**：系统自动检测是否有新的最佳成绩记录
2. **实时反馈**：在API响应中立即返回新记录信息
3. **详细记录**：包含具体的功率/速度值和对应的活动ID
4. **错误处理**：即使更新失败也不会影响主要API功能
5. **向后兼容**：无新记录时不添加额外字段，保持API兼容性

## 测试验证

- ✅ 所有模块导入成功
- ✅ 返回格式正确
- ✅ 数据结构完整
- ✅ 错误处理完善
- ✅ 变量初始化问题已修复

## 使用说明

1. **自动触发**：调用 `/all` 接口时自动检查并返回新记录
2. **手动触发**：调用 `/update-best-efforts` 接口手动更新
3. **查看记录**：调用 `/athlete-best-efforts` 接口查看所有记录

## 注意事项

1. 只有在有新的最佳成绩记录时才会在响应中包含 `best_efforts_update` 字段
2. 更新失败时不会影响主要API的响应
3. 所有时间单位使用秒（如5s, 30s），距离单位使用米/秒
4. 活动ID用于追踪哪个活动创造了该记录

## 问题修复

### 变量初始化问题
**问题**：`"detail": "服务器内部错误: cannot access local variable 'best_efforts_result' where it is not associated with a value"`

**原因**：在Strava API和本地数据库查询部分，`best_efforts_result` 变量在使用前没有被正确初始化。

**修复**：
1. 将最佳成绩更新代码移到使用该变量之前
2. 确保变量在使用前被正确初始化为 `None`
3. 在异常处理中提供默认值

**修复后的流程**：
```python
# 1. 先初始化变量
best_efforts_result = None

# 2. 更新最佳成绩记录
try:
    best_efforts_result = activity_data_manager.update_best_efforts(db, activity_id)
except Exception as e:
    best_efforts_result = {
        "success": False,
        "new_records": {"power_records": {}, "speed_records": {}},
        "message": f"最佳成绩检查失败: {str(e)}"
    }

# 3. 使用变量构建响应
if best_efforts_result and best_efforts_result.get("success"):
    # 添加到响应中
```
