#!/bin/bash
# Remote CI - Docker 测试环境启动脚本

set -e

echo "========================================="
echo "Remote CI - Docker 测试环境"
echo "========================================="
echo ""
echo "⚠️  注意：这是测试环境，仅用于开发测试"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: Docker 未安装"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 docker-compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误: docker-compose 未安装"
    echo "请先安装 docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker 已安装: $(docker --version)"
echo "✓ docker-compose 已安装: $(docker-compose --version)"
echo ""

# 检查 .env 文件（在父目录）
if [ ! -f ../.env ]; then
    echo "⚠️  警告: .env 文件不存在，从模板创建..."
    cp ../.env.example ../.env
    echo "✓ 已创建 .env 文件"
    echo ""
fi

# 读取配置
if [ -f ../.env ]; then
    source ../.env
fi

# 使用测试默认值
CI_API_TOKEN=${CI_API_TOKEN:-test-token-only}
CI_MAX_CONCURRENT=${CI_MAX_CONCURRENT:-2}
CI_JOB_TIMEOUT=${CI_JOB_TIMEOUT:-3600}

echo "========================================="
echo "测试环境配置:"
echo "========================================="
echo "API Token: ${CI_API_TOKEN}"
echo "最大并发: $CI_MAX_CONCURRENT"
echo "任务超时: $CI_JOB_TIMEOUT 秒"
echo "========================================="
echo ""

# 构建并启动服务
echo ">>> 构建 Docker 镜像..."
docker-compose build

echo ""
echo ">>> 启动测试服务..."
docker-compose up -d

echo ""
echo ">>> 等待服务启动..."
sleep 5

# 显示服务状态
echo ""
echo "========================================="
echo "服务状态:"
echo "========================================="
docker-compose ps

echo ""
echo "========================================="
echo "✓ 测试环境启动成功！"
echo "========================================="
echo ""
echo "访问地址:"
echo "  - Web 管理界面: http://localhost:5000"
echo "  - API 健康检查: http://localhost:5000/api/health"
echo "  - API Token: test-token-only"
echo ""
echo "常用命令 (在 test 目录下执行):"
echo "  - 查看日志: docker-compose logs -f"
echo "  - 停止服务: docker-compose stop"
echo "  - 重启服务: docker-compose restart"
echo "  - 完全停止: ./stop-docker.sh"
echo ""
echo "详细文档请查看: DOCKER.md"
echo "========================================="
