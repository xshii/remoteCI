#!/bin/bash
# 快速修复数据库路径不一致问题

echo "======================================================================="
echo "数据库路径修复工具"
echo "======================================================================="
echo

# 设置默认路径
DEFAULT_DATA_DIR="/home/user/remoteCI/data"

echo "此脚本将帮助你修复数据库路径不一致的问题"
echo
echo "建议的数据库路径: $DEFAULT_DATA_DIR"
echo

# 创建 .env 文件
ENV_FILE="/home/user/remoteCI/.env"

if [ -f "$ENV_FILE" ]; then
    echo "⚠ .env 文件已存在: $ENV_FILE"
    echo "是否备份并覆盖? (y/N)"
    read -r answer
    if [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
        echo "取消操作"
        exit 0
    fi
    cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d_%H%M%S)"
    echo "✓ 已备份到: $ENV_FILE.bak.$(date +%Y%m%d_%H%M%S)"
fi

echo "创建 .env 文件..."
cat > "$ENV_FILE" << EOF
# Remote CI 配置文件
# 数据库和日志存储路径（必须设置为绝对路径）
CI_DATA_DIR=$DEFAULT_DATA_DIR

# 临时工作目录
CI_WORK_DIR=/tmp/remote-ci

# 用户工作空间目录（rsync模式使用）
CI_WORKSPACE_DIR=/var/ci-workspace

# API 配置
CI_API_HOST=0.0.0.0
CI_API_PORT=5000
CI_API_TOKEN=change-me-in-production

# Redis 配置（Celery 使用）
CI_BROKER_URL=redis://localhost:6379/0
CI_RESULT_BACKEND=redis://localhost:6379/0

# 任务配置
CI_MAX_CONCURRENT=2
CI_JOB_TIMEOUT=3600
CI_LOG_RETENTION_DAYS=7
EOF

echo "✓ 已创建 .env 文件: $ENV_FILE"
echo

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p "$DEFAULT_DATA_DIR"
mkdir -p "$DEFAULT_DATA_DIR/logs"
mkdir -p "$DEFAULT_DATA_DIR/uploads"
mkdir -p "$DEFAULT_DATA_DIR/artifacts"
mkdir -p "/tmp/remote-ci"
mkdir -p "/var/ci-workspace"

echo "✓ 目录已创建"
echo

# 设置权限
echo "设置目录权限..."
chmod 755 "$DEFAULT_DATA_DIR"
chmod 755 "$DEFAULT_DATA_DIR/logs"
chmod 755 "$DEFAULT_DATA_DIR/uploads"
chmod 755 "$DEFAULT_DATA_DIR/artifacts"

echo "✓ 权限已设置"
echo

# 检查是否需要更新 systemd 服务
echo "======================================================================="
echo "后续步骤:"
echo "======================================================================="
echo
echo "1. 如果使用 systemd 服务，请更新服务文件添加环境变量:"
echo
echo "   编辑 /etc/systemd/system/remote-ci.service:"
echo "   [Service]"
echo "   Environment=\"CI_DATA_DIR=$DEFAULT_DATA_DIR\""
echo "   Environment=\"CI_WORK_DIR=/tmp/remote-ci\""
echo
echo "   编辑 /etc/systemd/system/celery.service:"
echo "   [Service]"
echo "   Environment=\"CI_DATA_DIR=$DEFAULT_DATA_DIR\""
echo "   Environment=\"CI_WORK_DIR=/tmp/remote-ci\""
echo
echo "   然后执行:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl restart remote-ci celery"
echo
echo "2. 如果使用 supervisor，请更新配置文件添加环境变量"
echo
echo "3. 如果手动启动，确保先导入环境变量:"
echo "   export CI_DATA_DIR=$DEFAULT_DATA_DIR"
echo "   export CI_WORK_DIR=/tmp/remote-ci"
echo
echo "4. 验证修复:"
echo "   ./check_db_consistency.sh"
echo
echo "======================================================================="
echo "完成"
echo "======================================================================="
