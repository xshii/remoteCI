# Remote CI 数据库查询参考

## 连接数据库

```bash
# 假设数据库在默认位置
DB_PATH="/home/user/remoteCI/data/jobs.db"

# 交互式模式
sqlite3 $DB_PATH

# 执行单条查询
sqlite3 $DB_PATH "SELECT * FROM ci_jobs LIMIT 10;"

# 格式化输出
sqlite3 $DB_PATH "SELECT * FROM ci_jobs LIMIT 10;" -header -column
```

## 常用查询

### 1. 基础查询

```sql
-- 查看所有表
.tables

-- 查看表结构
.schema ci_jobs
.schema special_users

-- 总任务数
SELECT COUNT(*) as total_jobs FROM ci_jobs;

-- 最近10条任务
SELECT
    job_id,
    status,
    mode,
    user_id,
    created_at
FROM ci_jobs
ORDER BY created_at DESC
LIMIT 10;
```

### 2. 按条件查询

```sql
-- 查询特定状态的任务
SELECT * FROM ci_jobs WHERE status = 'failed';
SELECT * FROM ci_jobs WHERE status = 'success';
SELECT * FROM ci_jobs WHERE status IN ('running', 'queued');

-- 查询特定用户的任务
SELECT * FROM ci_jobs WHERE user_id = 'your-user-id';

-- 查询特定项目的任务
SELECT * FROM ci_jobs WHERE project_name = 'your-project';

-- 查询特定模式的任务
SELECT * FROM ci_jobs WHERE mode = 'upload';
SELECT * FROM ci_jobs WHERE mode = 'rsync';
SELECT * FROM ci_jobs WHERE mode = 'git';

-- 查询特定时间范围的任务
SELECT * FROM ci_jobs
WHERE created_at >= '2024-01-01'
  AND created_at < '2024-02-01';

-- 查询今天的任务
SELECT * FROM ci_jobs
WHERE date(created_at) = date('now');

-- 查询最近24小时的任务
SELECT * FROM ci_jobs
WHERE datetime(created_at) >= datetime('now', '-1 day');
```

### 3. 统计查询

```sql
-- 按状态统计
SELECT
    status,
    COUNT(*) as count
FROM ci_jobs
GROUP BY status
ORDER BY count DESC;

-- 按模式统计
SELECT
    mode,
    COUNT(*) as count
FROM ci_jobs
GROUP BY mode;

-- 按用户统计
SELECT
    user_id,
    COUNT(*) as count
FROM ci_jobs
GROUP BY user_id
ORDER BY count DESC;

-- 按项目统计
SELECT
    project_name,
    COUNT(*) as count,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count
FROM ci_jobs
GROUP BY project_name
ORDER BY count DESC;

-- 成功率统计
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM ci_jobs;

-- 每日任务统计
SELECT
    date(created_at) as date,
    COUNT(*) as count,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM ci_jobs
GROUP BY date(created_at)
ORDER BY date DESC
LIMIT 30;
```

### 4. 性能分析

```sql
-- 平均执行时间
SELECT
    AVG(duration) as avg_duration,
    MIN(duration) as min_duration,
    MAX(duration) as max_duration
FROM ci_jobs
WHERE duration IS NOT NULL;

-- 按模式查看平均执行时间
SELECT
    mode,
    AVG(duration) as avg_duration,
    COUNT(*) as count
FROM ci_jobs
WHERE duration IS NOT NULL
GROUP BY mode;

-- 最慢的10个任务
SELECT
    job_id,
    mode,
    project_name,
    duration,
    created_at
FROM ci_jobs
WHERE duration IS NOT NULL
ORDER BY duration DESC
LIMIT 10;

-- 最快的10个任务
SELECT
    job_id,
    mode,
    project_name,
    duration,
    created_at
FROM ci_jobs
WHERE duration IS NOT NULL
ORDER BY duration ASC
LIMIT 10;
```

### 5. 错误分析

```sql
-- 失败的任务
SELECT
    job_id,
    mode,
    user_id,
    error_message,
    created_at
FROM ci_jobs
WHERE status = 'failed'
ORDER BY created_at DESC;

-- 超时的任务
SELECT
    job_id,
    mode,
    user_id,
    created_at
FROM ci_jobs
WHERE status = 'timeout'
ORDER BY created_at DESC;

-- 按错误信息分组
SELECT
    error_message,
    COUNT(*) as count
FROM ci_jobs
WHERE status = 'failed' AND error_message IS NOT NULL
GROUP BY error_message
ORDER BY count DESC;

-- 失败率最高的项目
SELECT
    project_name,
    COUNT(*) as total,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) / COUNT(*), 2) as failure_rate
FROM ci_jobs
WHERE project_name IS NOT NULL
GROUP BY project_name
HAVING COUNT(*) >= 5
ORDER BY failure_rate DESC;
```

### 6. 文件大小分析

```sql
-- 磁盘使用统计
SELECT
    SUM(log_size) as total_log_size,
    SUM(artifacts_size) as total_artifacts_size,
    SUM(code_archive_size) as total_code_size,
    SUM(log_size + artifacts_size + code_archive_size) as total_size
FROM ci_jobs;

-- 按用户统计磁盘使用
SELECT
    user_id,
    SUM(log_size + artifacts_size + code_archive_size) as total_size,
    COUNT(*) as job_count
FROM ci_jobs
WHERE user_id IS NOT NULL
GROUP BY user_id
ORDER BY total_size DESC;

-- 最大的任务
SELECT
    job_id,
    project_name,
    log_size,
    artifacts_size,
    code_archive_size,
    (log_size + artifacts_size + code_archive_size) as total_size
FROM ci_jobs
ORDER BY total_size DESC
LIMIT 10;
```

### 7. 用户活跃度

```sql
-- 活跃用户排名
SELECT
    user_id,
    COUNT(*) as total_jobs,
    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_jobs,
    MAX(created_at) as last_activity
FROM ci_jobs
WHERE user_id IS NOT NULL
GROUP BY user_id
ORDER BY total_jobs DESC;

-- 最近活跃的用户
SELECT
    user_id,
    COUNT(*) as jobs_today
FROM ci_jobs
WHERE user_id IS NOT NULL
  AND date(created_at) = date('now')
GROUP BY user_id
ORDER BY jobs_today DESC;
```

### 8. 特殊用户配额查询

```sql
-- 查看所有特殊用户
SELECT
    user_id,
    ROUND(quota_bytes / 1024.0 / 1024.0 / 1024.0, 2) as quota_gb,
    created_at,
    updated_at
FROM special_users;

-- 特殊用户的使用情况
SELECT
    s.user_id,
    ROUND(s.quota_bytes / 1024.0 / 1024.0 / 1024.0, 2) as quota_gb,
    ROUND(SUM(j.log_size + j.artifacts_size + j.code_archive_size) / 1024.0 / 1024.0 / 1024.0, 2) as used_gb,
    ROUND(100.0 * SUM(j.log_size + j.artifacts_size + j.code_archive_size) / s.quota_bytes, 2) as usage_percent
FROM special_users s
LEFT JOIN ci_jobs j ON s.user_id = j.user_id AND j.is_expired = 0
GROUP BY s.user_id;
```

### 9. 数据清理

```sql
-- 查询可以清理的旧任务（超过30天）
SELECT
    job_id,
    created_at,
    status
FROM ci_jobs
WHERE datetime(created_at) < datetime('now', '-30 day');

-- 统计需要清理的任务数量
SELECT
    COUNT(*) as cleanable_jobs
FROM ci_jobs
WHERE datetime(created_at) < datetime('now', '-30 day');

-- 查询已过期的任务
SELECT
    job_id,
    status,
    created_at
FROM ci_jobs
WHERE is_expired = 1;
```

### 10. 完整任务详情

```sql
-- 查看特定任务的所有信息
SELECT * FROM ci_jobs WHERE job_id = 'your-job-id';

-- 格式化显示单个任务
SELECT
    'Job ID: ' || job_id || char(10) ||
    'Status: ' || status || char(10) ||
    'Mode: ' || mode || char(10) ||
    'User: ' || COALESCE(user_id, 'N/A') || char(10) ||
    'Project: ' || COALESCE(project_name, 'N/A') || char(10) ||
    'Script: ' || script || char(10) ||
    'Created: ' || created_at || char(10) ||
    'Started: ' || COALESCE(started_at, 'N/A') || char(10) ||
    'Finished: ' || COALESCE(finished_at, 'N/A') || char(10) ||
    'Duration: ' || COALESCE(CAST(duration AS TEXT), 'N/A') || 's' || char(10) ||
    'Exit Code: ' || COALESCE(CAST(exit_code AS TEXT), 'N/A') || char(10) ||
    'Log File: ' || COALESCE(log_file, 'N/A')
FROM ci_jobs
WHERE job_id = 'your-job-id';
```

## 导出数据

```bash
# 导出为 CSV
sqlite3 -header -csv $DB_PATH "SELECT * FROM ci_jobs;" > jobs.csv

# 导出特定查询结果
sqlite3 -header -csv $DB_PATH "SELECT job_id, status, mode, created_at FROM ci_jobs WHERE status='failed';" > failed_jobs.csv

# 导出为 JSON（需要 jq）
sqlite3 -json $DB_PATH "SELECT * FROM ci_jobs LIMIT 10;" | jq .

# 备份整个数据库
cp $DB_PATH jobs.db.backup.$(date +%Y%m%d_%H%M%S)
```

## 交互式模式的有用命令

```sql
-- 在 sqlite3 交互模式下
.help           -- 显示帮助
.tables         -- 列出所有表
.schema         -- 显示所有表的结构
.schema TABLE   -- 显示特定表的结构
.mode column    -- 列模式显示
.headers on     -- 显示列名
.width 10 20 30 -- 设置列宽
.output file.txt -- 输出到文件
.output stdout  -- 恢复输出到屏幕
.quit           -- 退出
```

## Python 脚本示例

```python
import sqlite3

# 连接数据库
conn = sqlite3.connect('/home/user/remoteCI/data/jobs.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询
cursor.execute('SELECT * FROM ci_jobs WHERE status = ?', ('failed',))
rows = cursor.fetchall()

for row in rows:
    print(f"Job: {row['job_id']}, Status: {row['status']}")

conn.close()
```
