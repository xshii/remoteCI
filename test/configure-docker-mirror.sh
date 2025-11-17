#!/bin/bash
# Docker 镜像加速配置脚本（清华源）

echo "========================================="
echo "Docker 镜像加速配置（清华源）"
echo "========================================="
echo ""

# 检查 Docker 是否运行
if ! docker info &> /dev/null; then
    echo "⚠️  Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi

# 创建 .docker 目录
mkdir -p ~/.docker

# 备份现有配置
if [ -f ~/.docker/daemon.json ]; then
    echo ">>> 备份现有配置..."
    cp ~/.docker/daemon.json ~/.docker/daemon.json.backup.$(date +%Y%m%d_%H%M%S)
    echo "✓ 已备份到: ~/.docker/daemon.json.backup.*"
fi

# 创建新配置
echo ">>> 创建镜像加速配置..."
cat > ~/.docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.tuna.tsinghua.edu.cn",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ],
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false
}
EOF

echo "✓ 配置文件已创建: ~/.docker/daemon.json"
echo ""

# 显示配置内容
echo "配置内容："
echo "---"
cat ~/.docker/daemon.json
echo "---"
echo ""

# 提示重启
echo "========================================="
echo "⚠️  重要：需要重启 Docker Desktop"
echo "========================================="
echo ""
echo "请选择重启方式："
echo "  1) 自动重启（推荐）"
echo "  2) 手动重启"
echo ""
read -p "请选择 (1-2): " -n 1 -r
echo ""

if [[ $REPLY == "1" ]]; then
    echo ">>> 正在重启 Docker Desktop..."
    osascript -e 'quit app "Docker"'
    echo "✓ Docker Desktop 已停止"
    echo "等待 5 秒..."
    sleep 5
    echo ">>> 启动 Docker Desktop..."
    open -a Docker
    echo "✓ Docker Desktop 正在启动..."
    echo ""
    echo "请等待约 30 秒让 Docker 完全启动，然后验证配置"
else
    echo ""
    echo "请手动重启 Docker Desktop："
    echo "  1. 点击菜单栏 Docker 图标"
    echo "  2. 选择 'Quit Docker Desktop'"
    echo "  3. 重新打开 Docker Desktop"
fi

echo ""
echo "========================================="
echo "验证配置"
echo "========================================="
echo ""
echo "Docker 启动后，运行以下命令验证："
echo "  docker info | grep -A 5 'Registry Mirrors'"
echo ""
echo "应该看到："
echo "  Registry Mirrors:"
echo "    https://docker.mirrors.tuna.tsinghua.edu.cn/"
echo ""
echo "========================================="
