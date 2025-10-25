# Intervals 数据持久化重构说明

## 修改概述

将 intervals 区间识别数据从 API 响应中移除，改为持久化存储到本地文件，并提供独立的查询接口。

## 主要变更

### 1. 新增文件

- **`app/infrastructure/intervals_manager.py`**: intervals 文件管理器
  - `save_intervals(activity_id, data)`: 保存 intervals 数据到 `/data/intervals/{activity_id}.json`
  - `load_intervals(activity_id)`: 从文件读取 intervals 数据
  - `delete_intervals(activity_id)`: 删除指定活动的 intervals 文件
  - 自动创建 `/data/intervals/` 目录

- **`tests/test_intervals_manager.py`**: intervals_manager 的单元测试

### 2. 修改的文件

#### `app/schemas/activities.py`
- **移除**: `AllActivityDataResponse` 中的 `intervals` 字段
- intervals 数据不再在 `/activities/{activity_id}/all` 接口中返回

#### `app/services/activity_service.py`
- **新增方法**: 
  - `_generate_and_save_intervals_strava()`: Strava 数据路径的 intervals 生成和保存
  - `_generate_and_save_intervals_local()`: 本地数据路径的 intervals 生成和保存
  
- **修改**: `get_all_data()` 方法
  - Strava 路径：在生成 zone_preview 后，生成并保存 intervals 到文件
  - 本地路径：在所有指标计算完成后，生成并保存 intervals 到文件
  - intervals 数据不再添加到响应中

#### `app/api/activities.py`
- **重写**: `GET /activities/{activity_id}/intervals` 接口
  - 移除所有参数（`access_token`, `ftp`, `lthr`, `hr_max`）
  - 从 `/data/intervals/{activity_id}.json` 文件读取数据
  - 如果文件不存在，返回 404 错误，提示先调用 `/all` 接口

### 3. 新增目录

- **`/data/intervals/`**: 存储所有活动的 intervals 数据文件

## 使用流程

### 1. 生成 intervals 数据

调用 all 接口时自动生成并保存：

```bash
# 本地 FIT 文件
GET /activities/{activity_id}/all?resolution=high

# 或 Strava 数据
GET /activities/{activity_id}/all?access_token=xxx&resolution=high
```

intervals 数据会自动保存到 `/data/intervals/{activity_id}.json`

### 2. 查询 intervals 数据

使用独立的 intervals 接口：

```bash
GET /activities/{activity_id}/intervals
```

返回示例：
```json
{
  "duration": 3600,
  "ftp": 250.0,
  "items": [
    {
      "start": 0,
      "end": 300,
      "duration": 300,
      "classification": "warmup",
      "average_power": 150.0,
      ...
    }
  ],
  "preview_image": "artifacts/Pics/interval_preview_106.png",
  "zone_segments": [...]
}
```

## 优势

1. **减少响应体积**: `/all` 接口不再返回大量 intervals 数据，响应更快
2. **按需获取**: 只在需要时才调用 `/intervals` 接口获取详细区间数据
3. **数据持久化**: intervals 数据保存在文件中，无需每次重新计算
4. **接口简化**: intervals 接口不再需要复杂的参数，直接读取文件即可

## 注意事项

1. **首次调用**: 必须先调用 `/all` 接口生成 intervals 数据，然后才能通过 `/intervals` 接口查询
2. **缓存更新**: 如果活动数据发生变化，需要重新调用 `/all` 接口来更新 intervals 文件
3. **文件管理**: intervals 文件存储在 `/data/intervals/` 目录，可以手动删除无用的文件

## 测试

运行单元测试：

```bash
python -m pytest tests/test_intervals_manager.py -v
```

所有测试应该通过：
- ✓ 测试保存和读取 intervals 数据
- ✓ 测试读取不存在的 intervals 数据
- ✓ 测试删除不存在的 intervals 数据
- ✓ 测试 intervals 目录自动创建

## 兼容性

- **向后不兼容**: `/all` 接口响应中不再包含 `intervals` 字段
- **新接口**: `/intervals` 接口现在只接受 `activity_id`，不再支持参数覆盖
- **迁移建议**: 如果有依赖 `/all` 接口中 `intervals` 字段的客户端，需要改为调用 `/intervals` 接口

## 性能影响

- **正面**: 减少了 `/all` 接口的响应时间和响应体积
- **负面**: 首次调用 `/all` 时需要额外的文件 I/O 操作（通常可以忽略）

