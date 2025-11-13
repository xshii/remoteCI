#!/bin/bash
##############################################################################
# 远程CI服务器安装脚本
# 用法: sudo bash install-server.sh
##############################################################################

set -e

echo "=========================================="
echo "Remote CI Server - 安装脚本"
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
if [ -f "../requirements.txt" ]; then
    cp -r ../{server,requirements.txt,.env.example} $INSTALL_DIR/
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

    echo "✓ 配置文件已创建: $INSTALL_DIR/.env"
    echo "⚠ 请记录API Token: $RANDOM_TOKEN"
else
    echo "✓ 配置文件已存在"
fi

echo ""

# ============ 6. 创建systemd服务 ============
echo ">>> 步骤 6/6: 创建systemd服务"

# API服务
cat > /etc/systemd/system/remote-ci-api.service <<EOF
[Unit]
Description=Remote CI API Server
After=network.target redis.service

[Service]
Type=simple
User=ci-user
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python -m server.app
Restart=always
RestartSec=10
StandardOutput=append:/var/log/remote-ci/api.log
StandardError=append:/var/log/remote-ci/api.log

[Install]
WantedBy=multi-user.target
EOF

# Celery Worker服务
cat > /etc/systemd/system/remote-ci-worker.service <<EOF
[Unit]
Description=Remote CI Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=ci-user
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/celery -A server.celery_app worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10
StandardOutput=append:/var/log/remote-ci/worker.log
StandardError=append:/var/log/remote-ci/worker.log

[Install]
WantedBy=multi-user.target
EOF

# Flower监控（可选）
cat > /etc/systemd/system/remote-ci-flower.service <<EOF
[Unit]
Description=Remote CI Flower Monitoring
After=network.target redis.service

[Service]
Type=simple
User=ci-user
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/celery -A server.celery_app flower --port=5555
Restart=always
RestartSec=10
StandardOutput=append:/var/log/remote-ci/flower.log
StandardError=append:/var/log/remote-ci/flower.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "✓ systemd服务已创建"
echo ""

# ============ 启动服务 ============
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "启动服务:"
echo "  sudo systemctl start redis"
echo "  sudo systemctl start remote-ci-api"
echo "  sudo systemctl start remote-ci-worker"
echo "  sudo systemctl start remote-ci-flower  # 可选"
echo ""
echo "设置开机启动:"
echo "  sudo systemctl enable redis"
echo "  sudo systemctl enable remote-ci-api"
echo "  sudo systemctl enable remote-ci-worker"
echo ""
echo "查看状态:"
echo "  sudo systemctl status remote-ci-api"
echo "  sudo systemctl status remote-ci-worker"
echo ""
echo "访问地址:"
echo "  Web界面: http://$(hostname -I | awk '{print $1}'):5000"
echo "  Flower监控: http://$(hostname -I | awk '{print $1}'):5555"
echo ""
echo "配置文件: $INSTALL_DIR/.env"
echo "日志目录: /var/log/remote-ci/"
echo ""
echo "下一步:"
echo "  1. 修改 $INSTALL_DIR/.env 配置"
echo "  2. 配置SSH密钥（rsync模式需要）"
echo "  3. 启动服务"
echo "=========================================="
