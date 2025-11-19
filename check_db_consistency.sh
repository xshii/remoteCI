#!/bin/bash
# 数据库一致性检查脚本

echo "======================================================================="
echo "数据库路径一致性检查工具"
echo "======================================================================="
echo

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "1. 查找所有 jobs.db 文件..."
echo "-------------------------------------------------------------------"
DB_FILES=$(find /home/user/remoteCI /tmp /var 2>/dev/null | grep 'jobs\.db$' || true)

if [ -z "$DB_FILES" ]; then
    echo -e "${YELLOW}⚠ 没有找到任何数据库文件${NC}"
    echo "  这可能意味着系统还未运行过，或者数据库在其他位置"
else
    echo -e "${GREEN}✓ 找到以下数据库文件:${NC}"
    echo "$DB_FILES" | while read -r file; do
        if [ -f "$file" ]; then
            size=$(ls -lh "$file" | awk '{print $5}')
            count=$(sqlite3 "$file" "SELECT COUNT(*) FROM ci_jobs;" 2>/dev/null || echo "无法访问")
            echo "  - $file (大小: $size, 任务数: $count)"
        fi
    done
fi
echo

echo "2. 检查环境变量..."
echo "-------------------------------------------------------------------"
env_vars=("CI_DATA_DIR" "CI_WORK_DIR" "CI_WORKSPACE_DIR" "CI_API_HOST" "CI_API_PORT")
for var in "${env_vars[@]}"; do
    value=$(printenv "$var" || echo "")
    if [ -z "$value" ]; then
        echo -e "${YELLOW}⚠ $var: 未设置${NC}"
    else
        echo -e "${GREEN}✓ $var: $value${NC}"
    fi
done
echo

echo "3. 检查进程使用的数据库路径..."
echo "-------------------------------------------------------------------"

# 检查 Flask 进程
echo "检查 Flask (remote-ci) 进程:"
if systemctl is-active --quiet remote-ci 2>/dev/null; then
    echo -e "${GREEN}✓ remote-ci 服务正在运行${NC}"
    systemctl show -p Environment remote-ci 2>/dev/null | grep CI_DATA_DIR || echo "  未找到 CI_DATA_DIR 环境变量"
elif pgrep -f "flask.*app.py" > /dev/null; then
    echo -e "${GREEN}✓ Flask 进程正在运行 (非 systemd)${NC}"
    pgrep -f "flask.*app.py" -a
else
    echo -e "${YELLOW}⚠ Flask 服务未运行${NC}"
fi
echo

# 检查 Celery 进程
echo "检查 Celery Worker 进程:"
if systemctl is-active --quiet celery 2>/dev/null; then
    echo -e "${GREEN}✓ celery 服务正在运行${NC}"
    systemctl show -p Environment celery 2>/dev/null | grep CI_DATA_DIR || echo "  未找到 CI_DATA_DIR 环境变量"
elif pgrep -f "celery.*worker" > /dev/null; then
    echo -e "${GREEN}✓ Celery Worker 进程正在运行 (非 systemd)${NC}"
    pgrep -f "celery.*worker" -a
else
    echo -e "${YELLOW}⚠ Celery Worker 服务未运行${NC}"
fi
echo

echo "4. 检查目录权限..."
echo "-------------------------------------------------------------------"
dirs=("/home/user/remoteCI/data" "/tmp/remote-ci" "/var/ci-workspace")
for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        perms=$(ls -ld "$dir" | awk '{print $1, $3, $4}')
        echo -e "${GREEN}✓ $dir${NC}"
        echo "  权限: $perms"
    else
        echo -e "${YELLOW}⚠ $dir (不存在)${NC}"
    fi
done
echo

echo "5. 诊断结果总结..."
echo "-------------------------------------------------------------------"

# 统计数据库文件数量
if [ -z "$DB_FILES" ]; then
    db_count=0
else
    db_count=$(echo "$DB_FILES" | wc -l)
fi

if [ "$db_count" -eq 0 ]; then
    echo -e "${YELLOW}⚠ 问题: 没有找到数据库文件${NC}"
    echo "  建议: 系统可能还未初始化，请先运行一次 Flask 或提交一个任务"
elif [ "$db_count" -eq 1 ]; then
    echo -e "${GREEN}✓ 正常: 只找到一个数据库文件${NC}"
    echo "  位置: $DB_FILES"
else
    echo -e "${RED}✗ 警告: 找到多个数据库文件！${NC}"
    echo "  这可能导致数据不一致问题"
    echo "  建议: 设置 CI_DATA_DIR 环境变量，确保所有进程使用同一个数据库"
fi
echo

# 检查环境变量设置
if [ -z "$CI_DATA_DIR" ]; then
    echo -e "${RED}✗ 警告: CI_DATA_DIR 环境变量未设置${NC}"
    echo "  建议: 在 systemd 服务文件或 .env 文件中设置 CI_DATA_DIR"
    echo "  示例: CI_DATA_DIR=/home/user/remoteCI/data"
else
    echo -e "${GREEN}✓ CI_DATA_DIR 已设置: $CI_DATA_DIR${NC}"
fi
echo

echo "======================================================================="
echo "完成"
echo "======================================================================="
echo
echo "如需详细诊断和修复指南，请查看: DATABASE_DIAGNOSIS.md"
