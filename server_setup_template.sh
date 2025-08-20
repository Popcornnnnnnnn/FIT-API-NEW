#!/bin/bash

# 活动数据缓存服务器设置脚本
# 在 CentOS 服务器 121.41.238.53 上执行

echo "🚀 开始设置活动数据缓存系统..."

# 1. 创建缓存存储目录
CACHE_DIR="/data/activity_cache"
echo "📁 创建缓存存储目录: $CACHE_DIR"
sudo mkdir -p $CACHE_DIR
sudo chown -R $USER:$USER $CACHE_DIR
sudo chmod 755 $CACHE_DIR

# 2. 检查目录权限
echo "🔐 检查目录权限..."
ls -la $CACHE_DIR

# 3. 创建日志目录
LOG_DIR="/var/log/activity_cache"
echo "📝 创建日志目录: $LOG_DIR"
sudo mkdir -p $LOG_DIR
sudo chown -R $USER:$USER $LOG_DIR
sudo chmod 755 $LOG_DIR

# 4. 检查磁盘空间
echo "💾 检查磁盘空间..."
df -h $CACHE_DIR

# 5. 创建定时清理脚本
CLEANUP_SCRIPT="/usr/local/bin/cleanup_activity_cache.sh"
echo "🧹 创建定时清理脚本: $CLEANUP_SCRIPT"

cat > $CLEANUP_SCRIPT << 'EOF'
#!/bin/bash

# 活动数据缓存清理脚本
# 每天凌晨2点执行，清理过期的缓存文件

CACHE_DIR="/data/activity_cache"
LOG_FILE="/var/log/activity_cache/cleanup.log"
DAYS_TO_KEEP=30

echo "$(date): 开始清理过期缓存文件..." >> $LOG_FILE

# 清理超过指定天数的文件
find $CACHE_DIR -name "*.json" -type f -mtime +$DAYS_TO_KEEP -delete

# 记录清理结果
CLEANED_COUNT=$(find $CACHE_DIR -name "*.json" -type f -mtime +$DAYS_TO_KEEP | wc -l)
echo "$(date): 清理完成，删除了 $CLEANED_COUNT 个过期文件" >> $LOG_FILE

# 清理空目录
find $CACHE_DIR -type d -empty -delete

echo "$(date): 缓存清理任务完成" >> $LOG_FILE
EOF

# 6. 设置脚本权限
sudo chmod +x $CLEANUP_SCRIPT

# 7. 添加到 crontab
echo "⏰ 添加到 crontab..."
(crontab -l 2>/dev/null; echo "0 2 * * * $CLEANUP_SCRIPT") | crontab -

# 8. 创建监控脚本
MONITOR_SCRIPT="/usr/local/bin/monitor_activity_cache.sh"
echo "📊 创建监控脚本: $MONITOR_SCRIPT"

cat > $MONITOR_SCRIPT << 'EOF'
#!/bin/bash

# 活动数据缓存监控脚本
# 检查缓存目录状态和磁盘使用情况

CACHE_DIR="/data/activity_cache"
LOG_FILE="/var/log/activity_cache/monitor.log"

echo "$(date): 开始监控缓存状态..." >> $LOG_FILE

# 检查目录是否存在
if [ ! -d "$CACHE_DIR" ]; then
    echo "$(date): 错误: 缓存目录不存在: $CACHE_DIR" >> $LOG_FILE
    exit 1
fi

# 统计文件数量
FILE_COUNT=$(find $CACHE_DIR -name "*.json" -type f | wc -l)
echo "$(date): 缓存文件数量: $FILE_COUNT" >> $LOG_DIR

# 检查磁盘使用情况
DISK_USAGE=$(df -h $CACHE_DIR | tail -1 | awk '{print $5}' | sed 's/%//')
echo "$(date): 磁盘使用率: $DISK_USAGE%" >> $LOG_FILE

# 如果磁盘使用率超过80%，发出警告
if [ $DISK_USAGE -gt 80 ]; then
    echo "$(date): 警告: 磁盘使用率过高 ($DISK_USAGE%)" >> $LOG_FILE
    # 这里可以添加邮件通知或其他告警机制
fi

# 检查目录权限
PERMISSIONS=$(ls -ld $CACHE_DIR | awk '{print $1}')
echo "$(date): 目录权限: $PERMISSIONS" >> $LOG_FILE

echo "$(date): 监控完成" >> $LOG_FILE
EOF

# 9. 设置监控脚本权限
sudo chmod +x $MONITOR_SCRIPT

# 10. 创建配置文件
CONFIG_FILE="/etc/activity_cache.conf"
echo "⚙️ 创建配置文件: $CONFIG_FILE"

cat > $CONFIG_FILE << 'EOF'
# 活动数据缓存配置文件

# 缓存存储目录
CACHE_DIR="/data/activity_cache"

# 缓存生存时间（天）
CACHE_TTL_DAYS=30

# 最大缓存文件大小（MB）
MAX_FILE_SIZE_MB=100

# 清理任务执行时间（每天）
CLEANUP_TIME="02:00"

# 监控间隔（分钟）
MONITOR_INTERVAL=60

# 日志级别
LOG_LEVEL="INFO"
EOF

# 11. 设置配置文件权限
sudo chmod 644 $CONFIG_FILE

# 12. 创建服务文件（可选，用于 systemd）
SERVICE_FILE="/etc/systemd/system/activity-cache-monitor.service"
echo "🔧 创建 systemd 服务文件: $SERVICE_FILE"

cat > $SERVICE_FILE << 'EOF'
[Unit]
Description=Activity Cache Monitor Service
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/monitor_activity_cache.sh
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

# 13. 重新加载 systemd 配置
sudo systemctl daemon-reload

# 14. 启用并启动服务（可选）
# sudo systemctl enable activity-cache-monitor
# sudo systemctl start activity-cache-monitor

# 15. 创建测试脚本
TEST_SCRIPT="/usr/local/bin/test_activity_cache.sh"
echo "🧪 创建测试脚本: $TEST_SCRIPT"

cat > $TEST_SCRIPT << 'EOF'
#!/bin/bash

# 活动数据缓存测试脚本

CACHE_DIR="/data/activity_cache"
TEST_FILE="$CACHE_DIR/test_12345_abc123.json"

echo "🧪 开始测试缓存系统..."

# 测试1: 创建测试文件
echo '{"test": "data", "timestamp": "'$(date -Iseconds)'"}' > $TEST_FILE
if [ $? -eq 0 ]; then
    echo "✅ 测试1通过: 文件创建成功"
else
    echo "❌ 测试1失败: 文件创建失败"
fi

# 测试2: 检查文件权限
if [ -r $TEST_FILE ] && [ -w $TEST_FILE ]; then
    echo "✅ 测试2通过: 文件权限正确"
else
    echo "❌ 测试2失败: 文件权限不正确"
fi

# 测试3: 检查文件内容
if grep -q "test" $TEST_FILE; then
    echo "✅ 测试3通过: 文件内容正确"
else
    echo "❌ 测试3失败: 文件内容不正确"
fi

# 清理测试文件
rm -f $TEST_FILE
echo "🧹 清理测试文件完成"

echo "🎉 缓存系统测试完成"
EOF

# 16. 设置测试脚本权限
sudo chmod +x $TEST_SCRIPT

# 17. 显示设置完成信息
echo ""
echo "🎉 活动数据缓存系统设置完成！"
echo ""
echo "📋 设置摘要:"
echo "   - 缓存目录: $CACHE_DIR"
echo "   - 日志目录: $LOG_DIR"
echo "   - 清理脚本: $CLEANUP_SCRIPT"
echo "   - 监控脚本: $MONITOR_SCRIPT"
echo "   - 配置文件: $CONFIG_FILE"
echo "   - 测试脚本: $TEST_SCRIPT"
echo ""
echo "🚀 下一步操作:"
echo "   1. 在数据库中执行 create_cache_table.sql 创建缓存表"
echo "   2. 运行测试脚本: $TEST_SCRIPT"
echo "   3. 检查 crontab: crontab -l"
echo "   4. 查看服务状态: systemctl status activity-cache-monitor"
echo ""
echo "📚 相关命令:"
echo "   - 手动清理缓存: $CLEANUP_SCRIPT"
echo "   - 查看缓存状态: $MONITOR_SCRIPT"
echo "   - 查看日志: tail -f $LOG_FILE"
echo "   - 查看磁盘使用: df -h $CACHE_DIR"
