#!/bin/bash
# Remote CI - Docker 停止脚本

set -e

echo "========================================="
echo "Remote CI - Docker 停止脚本"
echo "========================================="
echo ""

# 询问是否删除数据
echo "请选择停止模式:"
echo "  1) 仅停止服务（保留数据）"
echo "  2) 停止并删除容器（保留数据卷）"
echo "  3) 停止并删除所有数据（包括数据卷）"
echo ""
read -p "请选择 (1-3): " -n 1 -r
echo ""

case $REPLY in
    1)
        echo ">>> 停止服务..."
        docker-compose stop
        echo "✓ 服务已停止"
        echo ""
        echo "重启服务: docker-compose start"
        ;;
    2)
        echo ">>> 停止并删除容器..."
        docker-compose down
        echo "✓ 容器已删除"
        echo ""
        echo "数据卷已保留，重新启动: ./start-docker.sh"
        ;;
    3)
        echo "⚠️  警告: 这将删除所有数据，包括任务历史和日志！"
        read -p "确定要继续吗？(y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo ">>> 停止并删除所有数据..."
            docker-compose down -v
            echo "✓ 容器和数据卷已删除"
            echo ""
            echo "重新启动: ./start-docker.sh"
        else
            echo "已取消"
            exit 1
        fi
        ;;
    *)
        echo "❌ 无效的选择"
        exit 1
        ;;
esac

echo ""
echo "========================================="
