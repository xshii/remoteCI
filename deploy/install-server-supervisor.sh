#!/bin/bash
##############################################################################
# 远程CI服务器安装脚本（Supervisor版本，适用于Docker容器）
# 用法: sudo bash install-server-supervisor.sh
##############################################################################

set -e

echo "=========================================="
echo "Remote CI Server - 安装脚本 (Supervisor)"
echo "=========================================="
echo ""

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用sudo运行此脚本"
    exit 1
fi

# ============ 1. 安装系统依赖 ============
echo ">>> 步骤 1/6: 安装系统依赖"

apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    redis-server \
    supervisor \
    git \
    rsync \
    curl

echo "✓ 系统依赖安装完成"
echo ""

# ============ 2. 创建服务用户 ============
echo ">>> 步骤 2/6: 创建服务用户"

if ! id "ci-user" &>/dev/null; then
    useradd -r -m -s /bin/bash ci-user
    echo "✓ 创建用户: ci-user"
else
    echo "✓ 用户已存在: ci-user"
fi

echo ""

# ============ 3. 创建目录结构 ============
echo ">>> 步骤 3/6: 创建目录结构"

INSTALL_DIR="/opt/remote-ci"
DATA_DIR="/var/lib/remote-ci"
WORKSPACE_DIR="/var/ci-workspace"

mkdir -p $INSTALL_DIR
mkdir -p $DATA_DIR/{logs,uploads}
mkdir -p $WORKSPACE_DIR
mkdir -p /var/log/remote-ci

chown -R ci-user:ci-user $DATA_DIR
chown -R ci-user:ci-user $WORKSPACE_DIR
chown -R ci-user:ci-user /var/log/remote-ci

echo "✓ 目录创建完成"
echo ""

# ============ 4. 安装Python依赖 ============
echo ">>> 步骤 4/6: 安装Python依赖"

cd $INSTALL_DIR

# 复制项目文件（假设当前目录是项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/../requirements.txt" ]; then
    cp -r $SCRIPT_DIR/../server $INSTALL_DIR/
    cp -r $SCRIPT_DIR/../client $INSTALL_DIR/
    cp $SCRIPT_DIR/../requirements.txt $INSTALL_DIR/
    cp $SCRIPT_DIR/../.env.example $INSTALL_DIR/
fi

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

deactivate

chown -R ci-user:ci-user $INSTALL_DIR

echo "✓ Python依赖安装完成"
echo ""

# ============ 5. 配置环境变量 ============
echo ">>> 步骤 5/6: 配置环境变量"

if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp $INSTALL_DIR/.env.example $INSTALL_DIR/.env

    # 生成随机token
    RANDOM_TOKEN=$(openssl rand -hex 32)

    sed -i "s/your-secret-token-here/$RANDOM_TOKEN/" $INSTALL_DIR/.env
    sed -i "s|CI_DATA_DIR=./data|CI_DATA_DIR=$DATA_DIR|" $INSTALL_DIR/.env
    sed -i "s|CI_WORKSPACE_DIR=/var/ci-workspace|CI_WORKSPACE_DIR=$WORKSPACE_DIR|" $INSTALL_DIR/.env

    echo "✓ 配置文件已创建: $INSTALL_DIR/.env"
    echo "⚠ 请记录API Token: $RANDOM_TOKEN"
else
    echo "✓ 配置文件已存在"
fi

echo ""

# ============ 6. 创建Supervisor配置 ============
echo ">>> 步骤 6/6: 创建Supervisor配置"

# 创建supervisor配置目录
mkdir -p /etc/supervisor/conf.d

# Redis服务配置
cat > /etc/supervisor/conf.d/remote-ci-redis.conf <<EOF
[program:remote-ci-redis]
command=redis-server --daemonize no --appendonly yes --dir $DATA_DIR
user=ci-user
autostart=true
autorestart=true
startretries=3
stdout_logfile=/var/log/remote-ci/redis.log
stderr_logfile=/var/log/remote-ci/redis.log
EOF

# API服务配置
cat > /etc/supervisor/conf.d/remote-ci-api.conf <<EOF
[program:remote-ci-api]
command=$INSTALL_DIR/venv/bin/python -m server.app
directory=$INSTALL_DIR
user=ci-user
environment=PATH="$INSTALL_DIR/venv/bin"
autostart=true
autorestart=true
startretries=3
stdout_logfile=/var/log/remote-ci/api.log
stderr_logfile=/var/log/remote-ci/api.log
EOF

# Celery Worker服务配置
cat > /etc/supervisor/conf.d/remote-ci-worker.conf <<EOF
[program:remote-ci-worker]
command=$INSTALL_DIR/venv/bin/celery -A server.celery_app worker --loglevel=info --concurrency=2
directory=$INSTALL_DIR
user=ci-user
environment=PATH="$INSTALL_DIR/venv/bin"
autostart=true
autorestart=true
startretries=3
stdout_logfile=/var/log/remote-ci/worker.log
stderr_logfile=/var/log/remote-ci/worker.log
stopwaitsecs=60
stopasgroup=true
killasgroup=true
EOF

# Flower监控服务配置（可选）
cat > /etc/supervisor/conf.d/remote-ci-flower.conf <<EOF
[program:remote-ci-flower]
command=$INSTALL_DIR/venv/bin/celery -A server.celery_app flower --port=5555
directory=$INSTALL_DIR
user=ci-user
environment=PATH="$INSTALL_DIR/venv/bin"
autostart=false
autorestart=true
startretries=3
stdout_logfile=/var/log/remote-ci/flower.log
stderr_logfile=/var/log/remote-ci/flower.log
EOF

# 创建supervisor组配置
cat > /etc/supervisor/conf.d/remote-ci-group.conf <<EOF
[group:remote-ci]
programs=remote-ci-redis,remote-ci-api,remote-ci-worker
priority=999
EOF

# 重新加载supervisor配置
supervisorctl reread
supervisorctl update

echo "✓ Supervisor配置已创建"
echo ""

# ============ 启动服务 ============
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "管理服务:"
echo "  启动所有服务:    sudo supervisorctl start remote-ci:*"
echo "  停止所有服务:    sudo supervisorctl stop remote-ci:*"
echo "  重启所有服务:    sudo supervisorctl restart remote-ci:*"
echo "  查看所有状态:    sudo supervisorctl status remote-ci:*"
echo ""
echo "管理单个服务:"
echo "  API服务:         sudo supervisorctl start/stop/restart remote-ci-api"
echo "  Worker服务:      sudo supervisorctl start/stop/restart remote-ci-worker"
echo "  Redis服务:       sudo supervisorctl start/stop/restart remote-ci-redis"
echo "  Flower监控:      sudo supervisorctl start/stop/restart remote-ci-flower"
echo ""
echo "查看日志:"
echo "  实时查看API日志:  sudo tail -f /var/log/remote-ci/api.log"
echo "  实时查看Worker日志: sudo tail -f /var/log/remote-ci/worker.log"
echo "  查看所有日志:     sudo supervisorctl tail -f remote-ci-api"
echo ""
echo "访问地址:"
echo "  Web界面: http://$(hostname -I | awk '{print $1}'):5000"
echo "  Flower监控: http://$(hostname -I | awk '{print $1}'):5555"
echo ""
echo "配置文件: $INSTALL_DIR/.env"
echo "日志目录: /var/log/remote-ci/"
echo "Supervisor配置: /etc/supervisor/conf.d/remote-ci-*.conf"
echo ""
echo "下一步:"
echo "  1. 修改 $INSTALL_DIR/.env 配置"
echo "  2. 配置SSH密钥（rsync模式需要）"
echo "  3. 启动服务: sudo supervisorctl start remote-ci:*"
echo "=========================================="
