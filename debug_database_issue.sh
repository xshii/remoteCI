#!/bin/bash
# 数据库问题快速调试脚本

echo "=========================================="
echo "数据库问题调试信息收集"
echo "=========================================="
echo

echo "1. 检查服务状态"
echo "----------------------------------------"
if systemctl is-active remote-ci &>/dev/null; then
    echo "✓ Flask (remote-ci): 运行中"
else
    echo "✗ Flask (remote-ci): 未运行"
fi

if systemctl is-active celery &>/dev/null; then
    echo "✓ Celery Worker: 运行中"
else
    echo "✗ Celery Worker: 未运行"
fi

# 检查进程
FLASK_PIDS=$(pgrep -f "flask|server.app" || true)
if [ -n "$FLASK_PIDS" ]; then
    echo "✓ Flask 进程 (PID: $FLASK_PIDS)"
fi

CELERY_PIDS=$(pgrep -f "celery.*worker" || true)
if [ -n "$CELERY_PIDS" ]; then
    echo "✓ Celery Worker 进程 (PID: $CELERY_PIDS)"
fi
echo

echo "2. 数据库初始化日志（路径）"
echo "----------------------------------------"
echo "Flask 使用的数据库路径:"
sudo journalctl -u remote-ci --since "1 hour ago" 2>/dev/null | grep "数据库初始化" | tail -2 || \
    (echo "（没有找到 systemd 日志，尝试搜索所有日志）" && \
     sudo journalctl --since "1 hour ago" 2>/dev/null | grep "数据库初始化.*server.app" | tail -2)

echo
echo "Celery Worker 使用的数据库路径:"
sudo journalctl -u celery --since "1 hour ago" 2>/dev/null | grep "数据库初始化" | tail -2 || \
    (echo "（没有找到 systemd 日志，尝试搜索所有日志）" && \
     sudo journalctl --since "1 hour ago" 2>/dev/null | grep "数据库初始化.*celery" | tail -2)
echo

echo "3. 最近的数据库写入操作"
echo "----------------------------------------"
sudo journalctl -u remote-ci -u celery --since "30 minutes ago" 2>/dev/null | grep "\[数据库写入\]" | tail -10 || \
    echo "（没有找到数据库写入日志）"
echo

echo "4. 最近的数据库查询操作"
echo "----------------------------------------"
sudo journalctl -u remote-ci -u celery --since "30 minutes ago" 2>/dev/null | grep "\[数据库查询\]" | tail -10 || \
    echo "（没有找到数据库查询日志）"
echo

echo "5. 数据库文件位置"
echo "----------------------------------------"
DB_FILES=$(find /home/user/remoteCI /tmp /var -name 'jobs.db' 2>/dev/null || true)
if [ -n "$DB_FILES" ]; then
    echo "$DB_FILES" | while read -r file; do
        if [ -f "$file" ]; then
            size=$(ls -lh "$file" | awk '{print $5}')
            mtime=$(stat -c %y "$file" 2>/dev/null | cut -d. -f1 || stat -f "%Sm" "$file" 2>/dev/null)
            count=$(sqlite3 "$file" "SELECT COUNT(*) FROM ci_jobs;" 2>/dev/null || echo "?")
            echo "  • $file"
            echo "    大小: $size, 修改时间: $mtime, 任务数: $count"
        fi
    done
else
    echo "  （没有找到数据库文件）"
fi
echo

echo "6. 环境变量"
echo "----------------------------------------"
echo "CI_DATA_DIR: ${CI_DATA_DIR:-未设置}"

# 检查 systemd 环境变量
if systemctl show -p Environment remote-ci 2>/dev/null | grep -q CI_DATA_DIR; then
    echo "remote-ci 服务环境变量:"
    systemctl show -p Environment remote-ci 2>/dev/null | grep CI_DATA_DIR
fi

if systemctl show -p Environment celery 2>/dev/null | grep -q CI_DATA_DIR; then
    echo "celery 服务环境变量:"
    systemctl show -p Environment celery 2>/dev/null | grep CI_DATA_DIR
fi
echo

echo "7. 数据库内容统计"
echo "----------------------------------------"
# 尝试常见位置
for DB_PATH in "/home/user/remoteCI/data/jobs.db" "/tmp/data/jobs.db" $DB_FILES; do
    if [ -f "$DB_PATH" ]; then
        echo "数据库: $DB_PATH"
        total=$(sqlite3 "$DB_PATH" 'SELECT COUNT(*) FROM ci_jobs;' 2>/dev/null || echo "0")
        echo "  总任务数: $total"

        if [ "$total" -gt 0 ]; then
            echo "  按状态统计:"
            sqlite3 "$DB_PATH" "SELECT status, COUNT(*) FROM ci_jobs GROUP BY status;" 2>/dev/null | while read -r line; do
                echo "    $line"
            done

            echo "  最近3条任务:"
            sqlite3 "$DB_PATH" "SELECT substr(job_id,1,30), status, mode, created_at FROM ci_jobs ORDER BY created_at DESC LIMIT 3;" 2>/dev/null | while read -r line; do
                echo "    $line"
            done
        fi
        echo
    fi
done
echo

echo "8. 诊断建议"
echo "----------------------------------------"

# 检查是否有多个数据库
db_count=$(echo "$DB_FILES" | grep -c . || echo "0")
if [ "$db_count" -gt 1 ]; then
    echo "⚠ 警告: 发现多个数据库文件！这可能导致数据不一致"
    echo "  建议: 设置 CI_DATA_DIR 环境变量"
fi

# 检查环境变量
if [ -z "$CI_DATA_DIR" ]; then
    echo "⚠ 警告: CI_DATA_DIR 环境变量未设置"
    echo "  建议: 运行 ./fix_db_path.sh 修复配置"
fi

# 检查服务状态
if ! systemctl is-active remote-ci &>/dev/null && ! pgrep -f "flask|server.app" &>/dev/null; then
    echo "⚠ 警告: Flask 服务未运行"
    echo "  建议: 启动服务后再测试"
fi

if ! systemctl is-active celery &>/dev/null && ! pgrep -f "celery.*worker" &>/dev/null; then
    echo "⚠ 警告: Celery Worker 未运行"
    echo "  建议: 启动服务后再测试"
fi

echo
echo "=========================================="
echo "完成"
echo "=========================================="
echo
echo "下一步:"
echo "1. 如果发现数据库路径不一致，运行: ./fix_db_path.sh"
echo "2. 重启服务后查看实时日志:"
echo "   sudo journalctl -u remote-ci -u celery -f"
echo "3. 提交测试任务并观察日志输出"
echo "4. 查看详细调试指南: cat DEBUG_WITH_LOGS.md"
