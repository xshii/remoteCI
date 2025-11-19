# 使用日志调试数据库问题

## 已添加的日志功能

我在 `server/database.py` 中添加了详细的日志输出，可以追踪：

### 1. 数据库初始化
```
[数据库初始化] 路径: /home/user/remoteCI/data/jobs.db
[数据库初始化] 文件存在: True/False
```

### 2. 创建任务记录
```
[数据库写入] 准备创建任务记录
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: abc123...
  模式: git/upload/rsync
  用户ID: user123
✓ 任务记录创建成功
  验证查询: 找到 1 条记录
  数据库文件大小: 12345 字节
```

### 3. 更新任务状态
```
[数据库更新] 更新任务开始状态
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: abc123...
✓ 任务状态更新为 running，影响 1 行
```

### 4. 查询任务列表
```
[数据库查询] 查询任务列表
  数据库路径: /home/user/remoteCI/data/jobs.db
  limit=50, offset=0, filters=None
  执行SQL: SELECT * FROM ci_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?
  参数: [50, 0]
✓ 查询完成，返回 10 条记录
  前3条记录:
    1. abc123... | success | git
    2. def456... | running | upload
    3. ghi789... | queued | rsync
```

## 查看日志的方法

### 方法 1: 实时查看日志（推荐）

**如果使用 systemd 服务：**

```bash
# Flask 日志（实时）
sudo journalctl -u remote-ci -f

# Celery Worker 日志（实时）
sudo journalctl -u celery -f

# 同时查看两个服务的日志
sudo journalctl -u remote-ci -u celery -f
```

**如果手动启动：**

```bash
# 终端 1: 启动 Flask（会看到日志输出）
cd /home/user/remoteCI
python3 -m server.app

# 终端 2: 启动 Celery Worker（会看到日志输出）
cd /home/user/remoteCI
celery -A server.celery_app worker --loglevel=info
```

### 方法 2: 查看历史日志

```bash
# Flask 最近 100 行日志
sudo journalctl -u remote-ci -n 100 --no-pager

# Celery Worker 最近 100 行日志
sudo journalctl -u celery -n 100 --no-pager

# 搜索特定关键词
sudo journalctl -u remote-ci -u celery | grep -E "\[数据库|Database"

# 只看数据库相关的日志
sudo journalctl -u remote-ci -u celery | grep "数据库"
```

### 方法 3: 保存日志到文件

```bash
# 保存最近的日志
sudo journalctl -u remote-ci -u celery --since "1 hour ago" > debug_logs.txt

# 查看保存的日志
less debug_logs.txt
```

## 调试步骤

### 步骤 1: 清空并重启

为了获得干净的日志，先重启服务：

```bash
# 重启服务
sudo systemctl restart remote-ci
sudo systemctl restart celery

# 等待几秒让服务启动
sleep 3

# 检查服务状态
sudo systemctl status remote-ci
sudo systemctl status celery
```

启动时你应该看到：
```
[数据库初始化] 路径: /home/user/remoteCI/data/jobs.db
[数据库初始化] 文件存在: True
```

**如果看到不同的路径，这就是问题所在！**

### 步骤 2: 提交测试任务

在另一个终端提交任务：

```bash
# 提交一个简单的测试任务
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "debug-user"
  }' | jq .
```

### 步骤 3: 观察日志

在日志中你应该看到：

**Flask 日志（提交任务时）：**
```
[数据库写入] 准备创建任务记录
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: xxxxxxxxxx
  模式: git
  用户ID: debug-user
✓ 任务记录创建成功
  验证查询: 找到 1 条记录
  数据库文件大小: xxxxx 字节
```

**Celery Worker 日志（执行任务时）：**
```
[数据库更新] 更新任务开始状态
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: xxxxxxxxxx
✓ 任务状态更新为 running，影响 1 行

[数据库更新] 更新任务完成状态
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: xxxxxxxxxx
  最终状态: success
✓ 任务状态更新为 success，影响 1 行
```

### 步骤 4: 查询任务

```bash
# 查询任务历史
curl http://localhost:5000/api/jobs/history | jq .
```

在 Flask 日志中你应该看到：
```
[数据库查询] 查询任务列表
  数据库路径: /home/user/remoteCI/data/jobs.db
  limit=20, offset=0, filters=None
  执行SQL: SELECT * FROM ci_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?
  参数: [20, 0]
✓ 查询完成，返回 1 条记录
  前3条记录:
    1. xxxxxxxxxx... | success | git
```

## 问题诊断

### 问题 A: 数据库路径不一致

**症状：**
- Flask 日志显示: `数据库路径: /home/user/remoteCI/data/jobs.db`
- Celery 日志显示: `数据库路径: /tmp/data/jobs.db` （不同！）

**原因：**
Flask 和 Celery Worker 使用了不同的数据库文件。

**解决方案：**
```bash
# 1. 创建 .env 文件
cat > /home/user/remoteCI/.env << 'EOF'
CI_DATA_DIR=/home/user/remoteCI/data
EOF

# 2. 更新 systemd 服务配置
sudo systemctl edit remote-ci
# 添加:
[Service]
Environment="CI_DATA_DIR=/home/user/remoteCI/data"

sudo systemctl edit celery
# 添加:
[Service]
Environment="CI_DATA_DIR=/home/user/remoteCI/data"

# 3. 重启服务
sudo systemctl daemon-reload
sudo systemctl restart remote-ci celery

# 4. 验证 - 两个日志中的路径应该相同
sudo journalctl -u remote-ci -u celery -n 50 | grep "数据库路径"
```

### 问题 B: 写入成功但查询为空

**症状：**
- 看到 `✓ 任务记录创建成功`
- 看到 `验证查询: 找到 1 条记录`
- 但查询时返回 `✓ 查询完成，返回 0 条记录`

**可能原因：**
1. 数据被意外删除
2. 查询条件过滤掉了所有记录
3. 时间或顺序问题

**解决方案：**
```bash
# 1. 直接查询数据库
sqlite3 /home/user/remoteCI/data/jobs.db "SELECT COUNT(*) FROM ci_jobs;"

# 2. 查看所有记录
sqlite3 /home/user/remoteCI/data/jobs.db "SELECT job_id, status, created_at FROM ci_jobs;"

# 3. 检查是否有清理任务在运行
sudo journalctl -u remote-ci -u celery | grep -i "cleanup\|delete\|clear"
```

### 问题 C: 写入失败

**症状：**
- 看到 `✗ 创建任务记录失败`
- 有错误堆栈信息

**可能原因：**
1. 数据库文件权限问题
2. 磁盘空间不足
3. 数据库文件损坏

**解决方案：**
```bash
# 1. 检查权限
ls -la /home/user/remoteCI/data/jobs.db

# 2. 检查磁盘空间
df -h /home/user/remoteCI/data

# 3. 检查数据库完整性
sqlite3 /home/user/remoteCI/data/jobs.db "PRAGMA integrity_check;"

# 4. 如果权限有问题
sudo chown $USER:$USER /home/user/remoteCI/data/jobs.db
chmod 644 /home/user/remoteCI/data/jobs.db
```

## 完整调试命令集

将以下命令保存为脚本，一键查看所有关键信息：

```bash
#!/bin/bash
# debug_database_issue.sh

echo "=========================================="
echo "数据库问题调试信息收集"
echo "=========================================="
echo

echo "1. 检查服务状态"
echo "---"
systemctl is-active remote-ci && echo "Flask: 运行中" || echo "Flask: 未运行"
systemctl is-active celery && echo "Celery: 运行中" || echo "Celery: 未运行"
echo

echo "2. 查看数据库初始化日志（路径）"
echo "---"
sudo journalctl -u remote-ci -u celery | grep "数据库初始化" | tail -5
echo

echo "3. 最近的数据库操作"
echo "---"
sudo journalctl -u remote-ci -u celery --since "10 minutes ago" | grep -E "\[数据库"
echo

echo "4. 数据库文件信息"
echo "---"
find /home/user/remoteCI -name 'jobs.db' -exec ls -lh {} \;
echo

echo "5. 数据库内容统计"
echo "---"
DB_PATH="/home/user/remoteCI/data/jobs.db"
if [ -f "$DB_PATH" ]; then
    echo "总任务数: $(sqlite3 $DB_PATH 'SELECT COUNT(*) FROM ci_jobs;')"
    echo "按状态统计:"
    sqlite3 $DB_PATH "SELECT status, COUNT(*) FROM ci_jobs GROUP BY status;" -header -column
else
    echo "数据库文件不存在: $DB_PATH"
fi
echo

echo "=========================================="
echo "完成"
echo "=========================================="
```

保存并运行：
```bash
chmod +x debug_database_issue.sh
./debug_database_issue.sh
```

## 下一步

运行上述调试后，请提供：

1. **数据库初始化时的路径**（Flask 和 Celery 各自的）
2. **任务提交时的日志**（是否显示"创建成功"）
3. **任务查询时的日志**（返回多少条记录）
4. **`debug_database_issue.sh` 的完整输出**

有了这些信息，我们就能精确定位问题！
