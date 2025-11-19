# 任务提交后无法查询的问题排查指南

## 问题现象
- 任务提交后，通过查询接口无法看到任务记录
- 查询数据库发现既没有特殊用户也没有任务记录

## 排查步骤

### 第一步：确认数据库文件位置

请告诉我以下信息：

1. **你是如何查询数据库的？**
   - [ ] 通过 API 查询 (`curl http://localhost:5000/api/jobs/history`)
   - [ ] 直接用 sqlite3 查询数据库文件
   - [ ] 使用我提供的脚本 (`./read_db.sh` 或 `python3 read_db.py`)
   - [ ] 其他方式：___________

2. **如果是直接查询数据库文件，文件路径是什么？**
   ```bash
   # 请提供完整路径
   数据库路径: ___________
   ```

3. **系统是否正在运行？**
   ```bash
   # 检查服务状态
   systemctl status remote-ci
   systemctl status celery
   # 或检查进程
   ps aux | grep flask
   ps aux | grep celery
   ```

### 第二步：定位问题

#### 情况 A：系统还未运行过

**特征：**
- `/home/user/remoteCI/data/` 目录不存在
- 找不到任何 `.db` 文件
- Flask 和 Celery 进程未运行

**解决方案：**
```bash
# 1. 运行修复脚本，创建必要的目录和配置
./fix_db_path.sh

# 2. 启动服务
# 如果使用 systemd
sudo systemctl start remote-ci
sudo systemctl start celery

# 如果手动启动
# 终端 1: 启动 Flask
cd /home/user/remoteCI
export CI_DATA_DIR=/home/user/remoteCI/data
python3 -m server.app

# 终端 2: 启动 Celery Worker
cd /home/user/remoteCI
export CI_DATA_DIR=/home/user/remoteCI/data
celery -A server.celery_app worker --loglevel=info

# 3. 提交测试任务
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }'

# 4. 查询任务历史
curl http://localhost:5000/api/jobs/history
```

#### 情况 B：数据库存在但为空

**特征：**
- 数据库文件存在（你能查询到表结构）
- 但是 `ci_jobs` 和 `special_users` 表都是空的
- 系统正在运行

**可能原因：**
1. **Flask 和 Celery 使用了不同的数据库文件**
   - Flask 写入数据库 A
   - Celery Worker 写入数据库 B
   - 你查询的是数据库 C（空的）

2. **任务提交失败了**
   - 检查 Flask 日志
   - 检查 Celery Worker 日志

**解决方案：**

**方案 1：追踪实际使用的数据库文件**

```bash
# 1. 启动系统监控（需要 inotify-tools）
sudo apt-get install inotify-tools

# 2. 监控所有 .db 文件的访问
find /home/user/remoteCI -name '*.db' -o -name 'jobs.db' 2>/dev/null | while read file; do
    inotifywait -m "$file" &
done

# 3. 提交一个任务，观察哪个数据库文件被修改

# 或者使用 lsof 查看进程打开的文件
# 找到 Flask 进程 PID
flask_pid=$(pgrep -f "flask|app.py" | head -1)
echo "Flask PID: $flask_pid"

# 查看打开的文件
lsof -p $flask_pid | grep -E '\.db|database'

# 找到 Celery Worker PID
celery_pid=$(pgrep -f "celery.*worker" | head -1)
echo "Celery PID: $celery_pid"

# 查看打开的文件
lsof -p $celery_pid | grep -E '\.db|database'
```

**方案 2：添加调试日志**

在 `server/app.py` 和 `server/tasks.py` 中添加日志：

```python
# 在文件顶部添加
import logging
logging.basicConfig(level=logging.DEBUG)

# 在数据库初始化后添加
from server.config import DATA_DIR
print(f"[DEBUG] 当前进程使用的数据库路径: {DATA_DIR}/jobs.db")
logging.info(f"数据库路径: {DATA_DIR}/jobs.db")
```

**方案 3：使用统一的数据库路径**

```bash
# 1. 创建 .env 文件
cat > /home/user/remoteCI/.env << 'EOF'
CI_DATA_DIR=/home/user/remoteCI/data
EOF

# 2. 创建目录
mkdir -p /home/user/remoteCI/data/{logs,uploads,artifacts}

# 3. 如果使用 systemd，更新服务配置
# 编辑 /etc/systemd/system/remote-ci.service 和 celery.service
[Service]
Environment="CI_DATA_DIR=/home/user/remoteCI/data"
WorkingDirectory=/home/user/remoteCI

# 4. 重启服务
sudo systemctl daemon-reload
sudo systemctl restart remote-ci celery

# 5. 验证
./check_db_consistency.sh
```

#### 情况 C：任务提交失败

**检查方法：**

```bash
# 1. 查看 Flask 日志
journalctl -u remote-ci -f
# 或
tail -f /var/log/remote-ci/app.log

# 2. 查看 Celery Worker 日志
journalctl -u celery -f
# 或
tail -f /var/log/celery/worker.log

# 3. 检查 Redis 连接
redis-cli ping
# 应该返回 PONG

# 4. 手动测试任务提交
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-api-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "debug-test"
  }' -v

# 观察返回的响应和日志
```

### 第三步：验证修复

修复后，执行以下验证：

```bash
# 1. 检查数据库一致性
./check_db_consistency.sh

# 2. 提交测试任务
TEST_JOB_ID=$(curl -s -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }' | jq -r '.job_id')

echo "测试任务 ID: $TEST_JOB_ID"

# 3. 等待几秒
sleep 5

# 4. 查询任务历史
curl -s http://localhost:5000/api/jobs/history | jq .

# 5. 查询数据库
./read_db.sh

# 6. 验证数据库中有任务记录
sqlite3 /home/user/remoteCI/data/jobs.db \
  "SELECT job_id, status, mode FROM ci_jobs ORDER BY created_at DESC LIMIT 5;" \
  -header -column
```

### 第四步：持久化配置

确保配置持久化，避免重启后问题复现：

```bash
# 1. 环境变量配置
cat >> /home/user/remoteCI/.env << 'EOF'
CI_DATA_DIR=/home/user/remoteCI/data
CI_WORK_DIR=/tmp/remote-ci
CI_WORKSPACE_DIR=/var/ci-workspace
EOF

# 2. systemd 服务配置
# /etc/systemd/system/remote-ci.service
[Service]
EnvironmentFile=/home/user/remoteCI/.env
Environment="CI_DATA_DIR=/home/user/remoteCI/data"

# /etc/systemd/system/celery.service
[Service]
EnvironmentFile=/home/user/remoteCI/.env
Environment="CI_DATA_DIR=/home/user/remoteCI/data"

# 3. 重新加载配置
sudo systemctl daemon-reload
```

## 快速诊断命令

请运行以下命令并告诉我结果：

```bash
# 命令 1: 搜索数据库文件
echo "=== 搜索数据库文件 ==="
find /home/user/remoteCI /tmp /var -name '*.db' 2>/dev/null

# 命令 2: 检查 data 目录
echo -e "\n=== 检查 data 目录 ==="
ls -la /home/user/remoteCI/data/ 2>/dev/null || echo "目录不存在"

# 命令 3: 检查环境变量
echo -e "\n=== 环境变量 ==="
echo "CI_DATA_DIR: ${CI_DATA_DIR:-未设置}"

# 命令 4: 检查进程
echo -e "\n=== 运行中的进程 ==="
ps aux | grep -E "flask|celery" | grep -v grep

# 命令 5: 测试 API
echo -e "\n=== 测试 API ==="
curl -s http://localhost:5000/api/jobs/history | head -20
```

## 我需要的信息

为了帮你更准确地定位问题，请提供：

1. **你查询的数据库文件完整路径**
2. **系统运行状态**（进程是否在运行）
3. **如何提交的任务**（命令或截图）
4. **上述快速诊断命令的输出**

有了这些信息，我可以更精确地帮你解决问题！
