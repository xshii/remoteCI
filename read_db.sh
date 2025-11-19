#!/bin/bash
# 数据库内容查看工具

# 使用方法:
# ./read_db.sh [数据库文件路径]
# 如果不提供路径，会自动搜索

DB_PATH="$1"

echo "======================================================================="
echo "Remote CI 数据库内容查看工具"
echo "======================================================================="
echo

# 如果没有提供路径，尝试查找
if [ -z "$DB_PATH" ]; then
    echo "正在搜索数据库文件..."

    # 常见位置
    SEARCH_PATHS=(
        "/home/user/remoteCI/data/jobs.db"
        "/tmp/remote-ci/jobs.db"
        "/var/lib/remote-ci/jobs.db"
        "$HOME/.remote-ci/jobs.db"
    )

    for path in "${SEARCH_PATHS[@]}"; do
        if [ -f "$path" ]; then
            DB_PATH="$path"
            echo "✓ 找到数据库: $DB_PATH"
            break
        fi
    done

    # 如果还没找到，搜索整个项目目录
    if [ -z "$DB_PATH" ]; then
        FOUND=$(find /home/user/remoteCI -name 'jobs.db' 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
            DB_PATH="$FOUND"
            echo "✓ 找到数据库: $DB_PATH"
        fi
    fi
fi

# 检查数据库文件是否存在
if [ -z "$DB_PATH" ] || [ ! -f "$DB_PATH" ]; then
    echo "✗ 错误: 找不到数据库文件"
    echo
    echo "使用方法:"
    echo "  ./read_db.sh /path/to/jobs.db"
    echo
    echo "或者手动指定位置后再运行"
    exit 1
fi

# 检查 sqlite3 是否安装
if ! command -v sqlite3 &> /dev/null; then
    echo "✗ 错误: sqlite3 未安装"
    echo "请先安装: sudo apt-get install sqlite3"
    exit 1
fi

echo
echo "======================================================================="
echo "数据库信息"
echo "======================================================================="
echo "文件路径: $DB_PATH"
echo "文件大小: $(ls -lh "$DB_PATH" | awk '{print $5}')"
echo "修改时间: $(stat -c %y "$DB_PATH" 2>/dev/null || stat -f %Sm "$DB_PATH" 2>/dev/null)"
echo

echo "======================================================================="
echo "1. 数据库表结构"
echo "======================================================================="
sqlite3 "$DB_PATH" ".schema" 2>/dev/null || echo "无法读取表结构"
echo

echo "======================================================================="
echo "2. 任务统计"
echo "======================================================================="
echo "总任务数:"
sqlite3 "$DB_PATH" "SELECT COUNT(*) as total FROM ci_jobs;" 2>/dev/null || echo "0"
echo

echo "按状态统计:"
sqlite3 "$DB_PATH" "
SELECT
    status,
    COUNT(*) as count
FROM ci_jobs
GROUP BY status
ORDER BY count DESC;
" -header -column 2>/dev/null || echo "无数据"
echo

echo "按模式统计:"
sqlite3 "$DB_PATH" "
SELECT
    mode,
    COUNT(*) as count
FROM ci_jobs
GROUP BY mode
ORDER BY count DESC;
" -header -column 2>/dev/null || echo "无数据"
echo

echo "按用户统计:"
sqlite3 "$DB_PATH" "
SELECT
    COALESCE(user_id, '(未设置)') as user_id,
    COUNT(*) as count
FROM ci_jobs
GROUP BY user_id
ORDER BY count DESC
LIMIT 10;
" -header -column 2>/dev/null || echo "无数据"
echo

echo "======================================================================="
echo "3. 最近的任务（最新10条）"
echo "======================================================================="
sqlite3 "$DB_PATH" "
SELECT
    substr(job_id, 1, 20) || '...' as job_id,
    status,
    mode,
    COALESCE(user_id, 'N/A') as user_id,
    substr(created_at, 1, 19) as created_at
FROM ci_jobs
ORDER BY created_at DESC
LIMIT 10;
" -header -column 2>/dev/null || echo "无数据"
echo

echo "======================================================================="
echo "4. 任务详情（选择最新的一条）"
echo "======================================================================="
LATEST_JOB=$(sqlite3 "$DB_PATH" "SELECT job_id FROM ci_jobs ORDER BY created_at DESC LIMIT 1;" 2>/dev/null)

if [ -n "$LATEST_JOB" ]; then
    echo "最新任务: $LATEST_JOB"
    echo "-------------------------------------------------------------------"
    sqlite3 "$DB_PATH" "
SELECT
    'job_id: ' || job_id || char(10) ||
    'status: ' || status || char(10) ||
    'mode: ' || mode || char(10) ||
    'user_id: ' || COALESCE(user_id, 'N/A') || char(10) ||
    'project_name: ' || COALESCE(project_name, 'N/A') || char(10) ||
    'created_at: ' || created_at || char(10) ||
    'started_at: ' || COALESCE(started_at, 'N/A') || char(10) ||
    'finished_at: ' || COALESCE(finished_at, 'N/A') || char(10) ||
    'duration: ' || COALESCE(CAST(duration AS TEXT), 'N/A') || 's' || char(10) ||
    'exit_code: ' || COALESCE(CAST(exit_code AS TEXT), 'N/A') || char(10) ||
    'log_file: ' || COALESCE(log_file, 'N/A')
FROM ci_jobs
WHERE job_id = '$LATEST_JOB';
" 2>/dev/null
else
    echo "数据库为空"
fi
echo

echo "======================================================================="
echo "5. 运行中的任务"
echo "======================================================================="
sqlite3 "$DB_PATH" "
SELECT
    substr(job_id, 1, 20) || '...' as job_id,
    status,
    mode,
    COALESCE(user_id, 'N/A') as user_id,
    substr(created_at, 1, 19) as created_at
FROM ci_jobs
WHERE status IN ('queued', 'running')
ORDER BY created_at DESC;
" -header -column 2>/dev/null

COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM ci_jobs WHERE status IN ('queued', 'running');" 2>/dev/null)
if [ "$COUNT" = "0" ]; then
    echo "（无运行中的任务）"
fi
echo

echo "======================================================================="
echo "6. 特殊用户配额"
echo "======================================================================="
HAS_SPECIAL=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM special_users;" 2>/dev/null)

if [ "$HAS_SPECIAL" -gt 0 ]; then
    sqlite3 "$DB_PATH" "
SELECT
    user_id,
    CAST(quota_bytes / 1024.0 / 1024.0 / 1024.0 AS TEXT) || ' GB' as quota,
    substr(created_at, 1, 19) as created_at
FROM special_users
ORDER BY created_at DESC;
" -header -column 2>/dev/null
else
    echo "（无特殊用户）"
fi
echo

echo "======================================================================="
echo "交互式查询模式"
echo "======================================================================="
echo "如需进行自定义查询，可以运行:"
echo "  sqlite3 $DB_PATH"
echo
echo "示例查询:"
echo "  -- 查看所有表"
echo "  .tables"
echo
echo "  -- 查看特定任务"
echo "  SELECT * FROM ci_jobs WHERE job_id = 'xxx';"
echo
echo "  -- 查看失败的任务"
echo "  SELECT job_id, status, error_message FROM ci_jobs WHERE status = 'failed';"
echo
echo "  -- 按项目统计"
echo "  SELECT project_name, COUNT(*) FROM ci_jobs GROUP BY project_name;"
echo
echo "======================================================================="
