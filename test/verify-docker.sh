#!/bin/bash
# Docker 安装验证脚本

echo "========================================="
echo "Docker 安装验证"
echo "========================================="
echo ""

# 检查 Docker 命令
echo ">>> 检查 Docker CLI..."
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo "✓ $DOCKER_VERSION"
else
    echo "✗ Docker CLI 未找到"
    echo "请确保 Docker Desktop 已完全启动"
    exit 1
fi

echo ""

# 检查 docker-compose
echo ">>> 检查 docker-compose..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version)
    echo "✓ $COMPOSE_VERSION"
else
    echo "✗ docker-compose 未找到"
    exit 1
fi

echo ""

# 检查 Docker 守护进程
echo ">>> 检查 Docker 守护进程..."
if docker info &> /dev/null; then
    echo "✓ Docker 守护进程正在运行"
else
    echo "✗ Docker 守护进程未运行"
    echo "请等待 Docker Desktop 完全启动"
    exit 1
fi

echo ""

# 运行测试容器
echo ">>> 运行测试容器 (hello-world)..."
if docker run --rm hello-world &> /tmp/docker-test.log; then
    echo "✓ 测试容器运行成功"
    echo ""
    echo "测试输出："
    echo "---"
    cat /tmp/docker-test.log | grep -A 5 "Hello from Docker"
    echo "---"
else
    echo "✗ 测试容器运行失败"
    cat /tmp/docker-test.log
    exit 1
fi

echo ""
echo "========================================="
echo "✓ Docker 安装验证成功！"
echo "========================================="
echo ""
echo "下一步："
echo "  cd /Users/gakki/dev/remoteCI/test"
echo "  ./start-docker.sh"
echo ""
echo "========================================="

rm -f /tmp/docker-test.log
