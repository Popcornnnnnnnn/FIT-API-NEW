# 活动数据缓存系统

## 概述

本系统为 `get("{activity_id}/all"` 接口实现了智能缓存机制，避免重复计算，提高响应速度。

## 功能特性

- 🚀 **智能缓存**: 自动缓存计算结果，避免重复计算
- 💾 **文件存储**: JSON数据存储在服务器文件系统中
- 🗄️ **数据库索引**: 通过数据库表管理缓存元数据
- ⏰ **自动过期**: 支持缓存生存时间设置
- 🧹 **自动清理**: 定时清理过期缓存文件
- 📊 **监控统计**: 提供缓存使用统计信息

## 系统架构

```
用户请求 → 检查缓存 → 缓存命中 → 直接返回
                ↓
            缓存未命中 → 计算数据 → 存储缓存 → 返回结果
```

## 安装步骤

### 1. 数据库设置

在服务器 `121.41.238.53` 的 `ry-system` 数据库中执行：

```sql
-- 执行 create_cache_table.sql 文件
source create_cache_table.sql;
```

### 2. 服务器设置

在 CentOS 服务器上执行：

```bash
# 给脚本执行权限
chmod +x server_setup_template.sh

# 运行设置脚本
./server_setup_template.sh
```

### 3. 代码部署

确保以下文件已正确部署：
- `app/activities/models.py` - 包含缓存表模型
- `app/activities/cache_manager.py` - 缓存管理器
- `app/activities/router.py` - 修改后的路由

## 使用方法

### 基本使用

调用 `GET /activities/{activity_id}/all` 接口时，系统会：

1. 自动生成缓存键（基于活动ID和resolution参数）
2. 检查是否存在有效缓存
3. 如果缓存命中，直接返回缓存数据
4. 如果缓存未命中，执行计算并缓存结果

**缓存策略说明**:
- 缓存键仅基于 `activity_id` 和 `resolution` 生成
- 相同活动ID和分辨率的请求将共享缓存，无论其他参数如何
- 不同分辨率（low/medium/high）的请求将分别缓存
- 这种设计确保了缓存的有效性和一致性

### 缓存管理接口

#### 清除指定活动缓存
```bash
DELETE /activities/cache/{activity_id}
```

#### 获取缓存统计
```bash
GET /activities/cache/stats
```

#### 清理过期缓存
```bash
POST /activities/cache/cleanup
```

## 配置说明

### 缓存参数

- **存储路径**: `/data/activity_cache`
- **生存时间**: 30天（可配置）
- **文件格式**: JSON
- **命名规则**: `{activity_id}_{cache_key}.json`

### 缓存键生成

缓存键基于以下参数生成：
- `activity_id`: 活动ID
- `resolution`: 数据分辨率

**注意**: 缓存键不包含 `access_token` 和 `keys` 参数，这意味着：
- 无论是否提供 Strava API 访问令牌，相同活动ID和分辨率的请求将共享缓存
- 不同分辨率（low/medium/high）的请求将分别缓存

## 监控和维护

### 定时任务

- **清理任务**: 每天凌晨2点自动清理过期缓存
- **监控任务**: 可选的系统服务监控

### 日志文件

- 清理日志: `/var/log/activity_cache/cleanup.log`
- 监控日志: `/var/log/activity_cache/monitor.log`

### 常用命令

```bash
# 查看缓存状态
/usr/local/bin/monitor_activity_cache.sh

# 手动清理缓存
/usr/local/bin/cleanup_activity_cache.sh

# 测试缓存系统
/usr/local/bin/test_activity_cache.sh

# 查看磁盘使用
df -h /data/activity_cache

# 查看定时任务
crontab -l
```

## 性能优化

### 缓存策略

1. **分层缓存**: 内存缓存 + 文件缓存 + 数据库索引
2. **智能过期**: 基于访问频率和时间的过期策略
3. **批量操作**: 支持批量清理和统计

### 存储优化

1. **文件压缩**: 可选的JSON压缩存储
2. **目录结构**: 按活动ID分组的目录结构
3. **磁盘监控**: 自动监控磁盘使用率

## 故障排除

### 常见问题

1. **缓存未命中率高**
   - 检查缓存生存时间设置
   - 验证缓存键生成逻辑

2. **磁盘空间不足**
   - 运行清理脚本
   - 检查磁盘配额

3. **权限问题**
   - 验证目录权限
   - 检查用户权限

### 调试方法

```bash
# 查看应用日志
tail -f /var/log/your_app.log

# 检查缓存文件
ls -la /data/activity_cache/

# 验证数据库连接
mysql -h 121.41.238.53 -u root -p ry-system
```

## 扩展功能

### 未来计划

- [ ] Redis缓存支持
- [ ] 分布式缓存
- [ ] 缓存预热机制
- [ ] 智能缓存策略
- [ ] 缓存命中率分析

### 自定义开发

如需自定义缓存策略，可修改 `ActivityCacheManager` 类：

```python
class CustomCacheManager(ActivityCacheManager):
    def generate_cache_key(self, activity_id: int, **kwargs):
        # 自定义缓存键生成逻辑
        pass
    
    def should_cache(self, data: Dict[str, Any]) -> bool:
        # 自定义缓存条件
        pass
```

## 技术支持

如有问题，请检查：
1. 数据库连接是否正常
2. 文件权限是否正确
3. 磁盘空间是否充足
4. 应用日志是否有错误信息

---

**注意**: 首次部署后，建议先测试小规模数据，确保系统运行正常后再处理大量数据。
