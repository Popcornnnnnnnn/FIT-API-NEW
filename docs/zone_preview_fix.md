# Zone Preview Path 修复说明

## 问题描述

在重构 intervals 功能后，`/activities/{activity_id}/all` 接口返回的 `zone_preview_path` 字段为空，导致无法获取区间预览图片的路径。

## 根本原因

- **Strava 路径**：已正确设置 `result.zone_preview_path = preview_info.get("path")`
- **本地路径**：缺少生成和设置 `zone_preview_path` 的逻辑

本地 FIT 文件处理路径没有生成 zone preview 图片，也没有设置 `zone_preview_path` 字段到响应中。

## 解决方案

### 1. 新增方法

**`_generate_and_save_zone_preview_local()`**

为本地数据路径添加 zone preview 生成逻辑：

```python
def _generate_and_save_zone_preview_local(
    self,
    db: Session,
    activity_id: int,
    local_pair: Optional[Tuple[Any, Any]],
    stream_data: Dict[str, Any],
) -> Optional[str]:
    """生成 zone_preview 图片（本地路径）"""
```

**功能**：
- 提取本地流数据（power, timestamp, heart_rate）
- 转换为 Strava 格式（watts, time, heartrate）
- 调用 `_generate_zone_preview()` 生成预览图
- 返回生成的图片路径

### 2. 修改流程

在 `get_all_data()` 的本地路径中，在生成 intervals 之前先生成 zone_preview：

```python
# 生成 zone_preview 和 intervals 数据
try:
    zone_preview_path_result = self._generate_and_save_zone_preview_local(
        db,
        activity_id,
        local_pair,
        raw_stream_data,
    )
    if zone_preview_path_result:
        response_data["zone_preview_path"] = zone_preview_path_result
    
    # 生成并保存 intervals 数据
    intervals_data = self._generate_and_save_intervals_local(...)
```

### 3. 数据格式转换

本地流数据使用的键名与 Strava 不同：

| 数据类型 | 本地格式 | Strava 格式 |
|---------|---------|------------|
| 功率 | `power` | `watts` |
| 时间戳 | `timestamp` | `time` |
| 心率 | `heart_rate` | `heartrate` |

在调用 `_generate_zone_preview()` 前，将本地格式转换为 Strava 格式：

```python
strava_format_stream_data = {
    'watts': power_series,
    'time': timestamps,
    'heartrate': heart_rate_series,
}
```

## 文件路径

生成的 zone preview 图片保存在：

```
/data/zone_previews/strava_{activity_id}_zones.png
```

- 对于 Strava 数据：使用 `external_id`
- 对于本地数据：使用本地 `activity_id`

## 验证

### 本地 FIT 文件
```bash
GET /activities/106/all?resolution=high
```

**返回**：
```json
{
  "zone_preview_path": "data/zone_previews/strava_106_zones.png",
  ...
}
```

### Strava 数据
```bash
GET /activities/123/all?access_token=xxx&resolution=high
```

**返回**：
```json
{
  "zone_preview_path": "data/zone_previews/strava_16208383156_zones.png",
  ...
}
```

## 注意事项

1. **图片生成时机**：每次调用 `/all` 接口时都会重新生成 zone preview 图片
2. **文件覆盖**：相同 activity_id 的图片会被覆盖
3. **依赖条件**：需要有功率数据或心率数据，以及对应的阈值（FTP 或 LTHR）
4. **异常处理**：如果生成失败，`zone_preview_path` 为 `None`，但不影响其他数据返回

## 相关文件

- `app/services/activity_service.py` - 新增 `_generate_and_save_zone_preview_local()` 方法
- `data/zone_previews/` - zone preview 图片存储目录

## 测试建议

1. 测试本地 FIT 文件的 zone_preview_path 返回
2. 测试 Strava 数据的 zone_preview_path 返回
3. 验证生成的图片文件存在且正确
4. 测试无功率/心率数据时的降级处理

