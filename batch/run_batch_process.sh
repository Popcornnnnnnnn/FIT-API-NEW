#!/bin/bash
# 运动员43批量处理启动脚本

echo "=========================================="
echo "运动员43批量处理脚本"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# 检查必要文件
if [ ! -f "batch_config.py" ]; then
    echo "❌ 配置文件 batch_config.py 不存在"
    echo "请先创建配置文件"
    exit 1
fi

if [ ! -f "batch_process_athlete_43.py" ]; then
    echo "❌ 主脚本 batch_process_athlete_43.py 不存在"
    exit 1
fi

# 显示选项
echo "请选择操作:"
echo "1. 环境测试"
echo "2. 测试单个活动"
echo "3. 处理所有活动"
echo "4. 显示帮助"
echo "5. 退出"
echo ""

read -p "请输入选项 (1-5): " choice

case $choice in
    1)
        echo "运行环境测试..."
        python3 test_batch_environment.py
        ;;
    2)
        read -p "请输入活动ID (默认106): " activity_id
        activity_id=${activity_id:-106}
        echo "测试活动 $activity_id..."
        python3 batch_process_athlete_43.py test $activity_id
        ;;
    3)
        echo "开始处理所有活动..."
        echo "注意: 这可能需要较长时间，按 Ctrl+C 可以中断"
        read -p "确认继续? (y/N): " confirm
        if [[ $confirm =~ ^[Yy]$ ]]; then
            python3 batch_process_athlete_43.py
        else
            echo "已取消"
        fi
        ;;
    4)
        python3 batch_process_athlete_43.py help
        ;;
    5)
        echo "退出"
        exit 0
        ;;
    *)
        echo "无效选项"
        exit 1
        ;;
esac
