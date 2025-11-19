# 客户端调试 API 使用指南

## 概述

现在你可以通过 HTTP API 从客户端查看数据库操作日志和系统信息，无需登录服务器！

所有调试 API 都**免 Token 认证**，方便快速调试。

---

## 🔍 API 端点列表

### 1. 查看日志 `/api/debug/logs`

查看最近的 Flask 应用日志，包括所有数据库操作。

**注意：** Celery Worker 的日志在单独的文件中：`{DATA_DIR}/logs/celery_worker.log`

**请求：**
```bash
# 查看最近 100 行日志
curl http://localhost:5000/api/debug/logs

# 查看最近 500 行
curl http://localhost:5000/api/debug/logs?lines=500

# 只看数据库相关的日志
curl http://localhost:5000/api/debug/logs?filter=数据库

# 只看错误日志
curl http://localhost:5000/api/debug/logs?filter=ERROR

# 格式化输出
curl http://localhost:5000/api/debug/logs | jq .
```

**响应示例：**
```json
{
  "log_file": "/home/user/remoteCI/data/logs/app.log",
  "total_lines": 523,
  "returned_lines": 100,
  "filter": "数据库",
  "logs": [
    "2024-01-15 10:23:45 [INFO] remoteCI.database: [数据库初始化] 路径: /home/user/remoteCI/data/jobs.db\n",
    "2024-01-15 10:23:45 [INFO] remoteCI.database: [数据库初始化] 文件存在: True\n",
    "2024-01-15 10:25:12 [INFO] remoteCI.database: [数据库写入] 准备创建任务记录: job_id=abc123, mode=git, user_id=test\n",
    "2024-01-15 10:25:12 [INFO] remoteCI.database: ✓ 任务记录创建成功: job_id=abc123, 验证=1条, 文件大小=12345B\n"
  ]
}
```

---

### 2. 数据库信息 `/api/debug/db-info`

查看数据库路径、大小、任务统计和最近的数据库操作。

**请求：**
```bash
curl http://localhost:5000/api/debug/db-info | jq .
```

**响应示例：**
```json
{
  "database_path": "/home/user/remoteCI/data/jobs.db",
  "data_dir": "/home/user/remoteCI/data",
  "file_exists": true,
  "file_size": 45056,
  "file_size_mb": 0.04,
  "last_modified": "2024-01-15T10:25:12",
  "total_jobs": 15,
  "jobs_by_status": {
    "success": 10,
    "running": 2,
    "failed": 3
  },
  "recent_db_operations": [
    "2024-01-15 10:25:12 [INFO] [数据库写入] 准备创建任务记录: job_id=abc123",
    "2024-01-15 10:25:12 [INFO] ✓ 任务记录创建成功: job_id=abc123, 验证=1条",
    "2024-01-15 10:25:15 [INFO] [数据库查询] 查询任务列表: limit=20, offset=0"
  ]
}
```

---

### 3. 配置信息 `/api/debug/config`

查看环境变量、配置路径和进程信息。

**请求：**
```bash
curl http://localhost:5000/api/debug/config | jq .
```

**响应示例：**
```json
{
  "environment": {
    "CI_DATA_DIR": "/home/user/remoteCI/data",
    "CI_WORK_DIR": "/tmp/remote-ci",
    "CI_WORKSPACE_DIR": "/var/ci-workspace",
    "PYTHONUNBUFFERED": "1"
  },
  "config": {
    "DATA_DIR": "/home/user/remoteCI/data",
    "WORKSPACE_DIR": "/var/ci-workspace",
    "API_HOST": "0.0.0.0",
    "API_PORT": 5000
  },
  "system": {
    "python_version": "3.10.12 ...",
    "hostname": "remoteCI-server",
    "pid": 12345,
    "cwd": "/home/user/remoteCI"
  },
  "database": {
    "path": "/home/user/remoteCI/data/jobs.db",
    "exists": true
  },
  "log_file": "/home/user/remoteCI/data/logs/app.log"
}
```

---

## 🎯 典型使用场景

### 场景 1: 检查数据库路径是否正确

```bash
# 查看配置
curl http://localhost:5000/api/debug/config | jq '.database'

# 输出：
# {
#   "path": "/home/user/remoteCI/data/jobs.db",
#   "exists": true
# }
```

### 场景 2: 追踪任务提交流程

```bash
# 1. 提交任务
JOB_ID=$(curl -s -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }' | jq -r '.job_id')

echo "任务ID: $JOB_ID"

# 2. 等待几秒
sleep 3

# 3. 查看日志，追踪这个任务的操作
curl "http://localhost:5000/api/debug/logs?filter=$JOB_ID&lines=50" | jq -r '.logs[]'
```

你会看到：
```
[INFO] [数据库写入] 准备创建任务记录: job_id=abc-123-xyz, mode=git, user_id=test-user
[INFO] ✓ 任务记录创建成功: job_id=abc-123-xyz, 验证=1条, 文件大小=12345B
[INFO] [数据库更新] 更新任务开始状态: job_id=abc-123-xyz
[INFO] ✓ 任务状态更新为 running: job_id=abc-123-xyz, 影响1行
[INFO] ✓ 任务状态更新为 success: job_id=abc-123-xyz, 影响1行
```

### 场景 3: 诊断任务无法查询的问题

```bash
# 1. 查看数据库信息
curl http://localhost:5000/api/debug/db-info | jq .

# 检查：
# - file_exists: 应该是 true
# - total_jobs: 应该 > 0
# - jobs_by_status: 查看任务分布

# 2. 查看最近的数据库操作
curl "http://localhost:5000/api/debug/logs?filter=数据库&lines=50" | jq -r '.logs[]'

# 3. 检查写入和查询的数据库路径是否一致
curl http://localhost:5000/api/debug/logs | jq -r '.logs[]' | grep "数据库路径"
```

### 场景 4: 查看错误日志

```bash
# 只看错误和警告
curl "http://localhost:5000/api/debug/logs?filter=ERROR&lines=100" | jq -r '.logs[]'
curl "http://localhost:5000/api/debug/logs?filter=WARNING&lines=100" | jq -r '.logs[]'

# 查看失败的任务创建
curl "http://localhost:5000/api/debug/logs?filter=创建任务记录失败" | jq -r '.logs[]'
```

### 场景 5: 实时监控日志（轮询）

创建一个简单的监控脚本：

```bash
#!/bin/bash
# monitor_logs.sh - 每5秒刷新日志

while true; do
    clear
    echo "=== Remote CI 实时日志 (Ctrl+C 退出) ==="
    echo "时间: $(date)"
    echo
    curl -s "http://localhost:5000/api/debug/logs?filter=数据库&lines=20" | \
        jq -r '.logs[]' | tail -20
    sleep 5
done
```

---

## 📝 完整调试工作流

```bash
# 1. 检查系统配置
echo "=== 1. 检查配置 ==="
curl -s http://localhost:5000/api/debug/config | jq '{
  database: .database,
  data_dir: .config.DATA_DIR,
  env_data_dir: .environment.CI_DATA_DIR
}'

# 2. 检查数据库状态
echo -e "\n=== 2. 数据库状态 ==="
curl -s http://localhost:5000/api/debug/db-info | jq '{
  path: .database_path,
  exists: .file_exists,
  size_mb: .file_size_mb,
  total_jobs: .total_jobs,
  status: .jobs_by_status
}'

# 3. 提交测试任务
echo -e "\n=== 3. 提交测试任务 ==="
JOB_RESPONSE=$(curl -s -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "debug-test"
  }')

JOB_ID=$(echo $JOB_RESPONSE | jq -r '.job_id')
echo "任务ID: $JOB_ID"

# 4. 等待任务执行
echo -e "\n=== 4. 等待执行... ==="
sleep 5

# 5. 查看任务相关的日志
echo -e "\n=== 5. 任务日志 ==="
curl -s "http://localhost:5000/api/debug/logs?filter=$JOB_ID&lines=50" | \
    jq -r '.logs[]' | grep -E "(数据库|$JOB_ID)"

# 6. 验证任务是否可查询
echo -e "\n=== 6. 查询任务 ==="
curl -s "http://localhost:5000/api/jobs/history?user_id=debug-test" | \
    jq '.jobs[] | {job_id, status, mode}'

# 7. 查看数据库操作统计
echo -e "\n=== 7. 最近数据库操作 ==="
curl -s http://localhost:5000/api/debug/db-info | \
    jq -r '.recent_db_operations[]' | tail -10
```

保存为 `full_debug.sh`，然后运行：
```bash
chmod +x full_debug.sh
./full_debug.sh
```

---

## 🛠️ 浏览器中查看

你也可以在浏览器中直接访问（不需要 jq）：

```
http://localhost:5000/api/debug/logs?lines=100
http://localhost:5000/api/debug/db-info
http://localhost:5000/api/debug/config
```

浏览器会显示 JSON 格式的响应。

---

## ⚠️ 安全提示

这些调试 API 目前**不需要 Token 认证**，方便调试。

在生产环境中，建议：
1. 添加 IP 白名单限制
2. 或者添加 Token 认证
3. 或者只在调试模式下启用

临时禁用方法（在 app.py 中添加）：
```python
DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

@app.route('/api/debug/logs', methods=['GET'])
def get_debug_logs():
    if not DEBUG_MODE:
        return jsonify({'error': 'Debug mode disabled'}), 403
    # ... 原有代码
```

---

## 📊 日志格式说明

日志格式：
```
时间 [级别] 模块名: 消息
```

例如：
```
2024-01-15 10:25:12 [INFO] remoteCI.database: [数据库写入] 准备创建任务记录: job_id=abc123
```

- **时间**: `2024-01-15 10:25:12`
- **级别**: `INFO`, `WARNING`, `ERROR`
- **模块**: `remoteCI.database`, `remoteCI.app`
- **消息**: 具体的操作信息

---

## 🎉 总结

有了这些 API，你现在可以：

✅ 从客户端查看所有数据库操作日志
✅ 实时追踪任务的完整流程
✅ 检查数据库路径配置
✅ 诊断数据不一致问题
✅ 无需登录服务器查看日志

**下一步：**
1. 启动服务
2. 提交一个测试任务
3. 用这些 API 追踪任务流程
4. 如果发现问题，立即能看到详细日志！
