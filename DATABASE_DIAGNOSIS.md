# 数据库路径不一致问题诊断指南

## 问题描述
任务提交后，无法在查询数据库时显示，怀疑是提交数据库和查询数据库不一致。

## 问题根源分析

### 1. 数据库初始化位置

系统在两个不同的模块中初始化了数据库实例：

- **server/app.py:30** (Flask 进程)
  ```python
  job_db = JobDatabase(f"{DATA_DIR}/jobs.db")
  ```

- **server/tasks.py:26** (Celery Worker 进程)
  ```python
  job_db = JobDatabase(f"{DATA_DIR}/jobs.db")
  ```

### 2. DATA_DIR 的计算逻辑

在 **server/config.py:16**：
```python
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = os.getenv('CI_DATA_DIR', str(BASE_DIR / 'data'))
```

**问题点：**
1. 如果没有设置 `CI_DATA_DIR` 环境变量，`DATA_DIR` 将基于 `BASE_DIR` 计算
2. `BASE_DIR = Path(__file__).parent.parent` 依赖于当前文件的位置
3. **Flask 和 Celery Worker 可能从不同的目录启动**，导致 `BASE_DIR` 不同
4. 最终导致两个进程使用不同的数据库文件路径

### 3. 数据流程

```
用户提交任务
    ↓
Flask (app.py) → job_db.create_job() → 写入数据库A
    ↓
Celery Worker (tasks.py) → job_db.update_job_started() → 写入数据库B (可能不同)
    ↓
Flask (app.py) → job_db.get_jobs() → 从数据库A读取 (没有更新的数据)
```

## 诊断步骤

### 步骤 1: 检查当前数据库文件位置

```bash
# 查找所有数据库文件
find /home/user/remoteCI -name 'jobs.db'
find /tmp -name 'jobs.db'
find /var -name 'jobs.db' 2>/dev/null

# 查看当前 data 目录
ls -la /home/user/remoteCI/data/
```

### 步骤 2: 检查环境变量

```bash
# 查看当前环境变量
echo "CI_DATA_DIR: $CI_DATA_DIR"

# 如果使用了 systemd 服务，检查服务配置
systemctl show -p Environment celery
systemctl show -p Environment remote-ci

# 如果使用了 supervisor，检查配置文件
grep CI_DATA_DIR /etc/supervisor/conf.d/*.conf
```

### 步骤 3: 查看进程实际使用的路径

创建测试脚本来验证每个进程看到的路径：

**test_flask_db_path.py:**
```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/user/remoteCI')

from server.config import DATA_DIR, BASE_DIR
print(f"Flask 进程看到的路径:")
print(f"  BASE_DIR: {BASE_DIR}")
print(f"  DATA_DIR: {DATA_DIR}")
print(f"  数据库路径: {DATA_DIR}/jobs.db")
```

**test_celery_db_path.py:**
```python
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/home/user/remoteCI')

# 模拟 Celery Worker 的环境
os.chdir('/home/user/remoteCI')  # 或者 Celery 实际的工作目录

from server.config import DATA_DIR, BASE_DIR
print(f"Celery Worker 进程看到的路径:")
print(f"  BASE_DIR: {BASE_DIR}")
print(f"  DATA_DIR: {DATA_DIR}")
print(f"  数据库路径: {DATA_DIR}/jobs.db")
```

### 步骤 4: 查看数据库内容

```bash
# 如果找到了数据库文件，查看内容
sqlite3 /path/to/jobs.db "SELECT COUNT(*) FROM ci_jobs;"
sqlite3 /path/to/jobs.db "SELECT job_id, status, mode, created_at FROM ci_jobs ORDER BY created_at DESC LIMIT 10;"
```

### 步骤 5: 检查进程日志

```bash
# Flask 日志
journalctl -u remote-ci -n 50 --no-pager | grep -i "data_dir\|database"

# Celery 日志
journalctl -u celery -n 50 --no-pager | grep -i "data_dir\|database"

# 或者查看应用日志文件
tail -100 /var/log/remote-ci/*.log | grep -i "data_dir\|database"
```

## 解决方案

### 方案 1: 设置环境变量（推荐）

在系统启动配置中明确设置 `CI_DATA_DIR` 为绝对路径：

**1. 创建或编辑 .env 文件**（如果使用了）：
```bash
cat > /home/user/remoteCI/.env << 'EOF'
CI_DATA_DIR=/home/user/remoteCI/data
CI_WORK_DIR=/tmp/remote-ci
CI_WORKSPACE_DIR=/var/ci-workspace
CI_API_HOST=0.0.0.0
CI_API_PORT=5000
CI_API_TOKEN=your-secure-token
CI_BROKER_URL=redis://localhost:6379/0
CI_RESULT_BACKEND=redis://localhost:6379/0
EOF
```

**2. 如果使用 systemd，编辑服务文件**：

编辑 `/etc/systemd/system/remote-ci.service`：
```ini
[Service]
Environment="CI_DATA_DIR=/home/user/remoteCI/data"
Environment="CI_WORK_DIR=/tmp/remote-ci"
Environment="CI_WORKSPACE_DIR=/var/ci-workspace"
```

编辑 `/etc/systemd/system/celery.service`（或 celery worker 的服务文件）：
```ini
[Service]
Environment="CI_DATA_DIR=/home/user/remoteCI/data"
Environment="CI_WORK_DIR=/tmp/remote-ci"
Environment="CI_WORKSPACE_DIR=/var/ci-workspace"
```

然后重新加载并重启服务：
```bash
sudo systemctl daemon-reload
sudo systemctl restart remote-ci
sudo systemctl restart celery
```

**3. 如果使用 supervisor，编辑配置文件**：

编辑 `/etc/supervisor/conf.d/remote-ci.conf`：
```ini
[program:remote-ci]
environment=CI_DATA_DIR="/home/user/remoteCI/data",CI_WORK_DIR="/tmp/remote-ci"
```

编辑 `/etc/supervisor/conf.d/celery.conf`：
```ini
[program:celery]
environment=CI_DATA_DIR="/home/user/remoteCI/data",CI_WORK_DIR="/tmp/remote-ci"
```

然后重启：
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart all
```

### 方案 2: 修改代码使用单例模式（备选）

如果无法统一环境变量，可以修改代码确保所有进程使用同一个硬编码路径：

**修改 server/config.py:**
```python
# 使用绝对路径，不依赖 __file__
DATA_DIR = os.getenv('CI_DATA_DIR', '/home/user/remoteCI/data')
WORK_DIR = os.getenv('CI_WORK_DIR', '/tmp/remote-ci')
WORKSPACE_DIR = os.getenv('CI_WORKSPACE_DIR', '/var/ci-workspace')
```

### 方案 3: 添加日志记录数据库路径（调试用）

在 server/app.py 和 server/tasks.py 的开头添加日志：

```python
# server/app.py
job_db = JobDatabase(f"{DATA_DIR}/jobs.db")
print(f"[Flask] 数据库路径: {DATA_DIR}/jobs.db")

# server/tasks.py
job_db = JobDatabase(f"{DATA_DIR}/jobs.db")
print(f"[Celery Worker] 数据库路径: {DATA_DIR}/jobs.db")
```

这样可以在启动时看到每个进程实际使用的路径。

## 验证修复

修复后，执行以下步骤验证：

```bash
# 1. 重启所有服务
sudo systemctl restart remote-ci celery
# 或
sudo supervisorctl restart all

# 2. 提交一个测试任务
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/your-repo.git",
    "branch": "main",
    "script": "echo test",
    "user_id": "test-user"
  }'

# 3. 查看任务列表
curl http://localhost:5000/api/jobs/history | jq .

# 4. 检查数据库
sqlite3 /home/user/remoteCI/data/jobs.db "SELECT job_id, status, mode FROM ci_jobs ORDER BY created_at DESC LIMIT 5;"
```

## 预防措施

1. **始终使用环境变量设置路径**，不依赖相对路径计算
2. **在部署文档中明确说明环境变量要求**
3. **添加健康检查**，定期验证数据库连接
4. **添加启动时的路径日志**，方便排查问题
5. **使用容器化部署**（Docker），确保环境一致性

## 快速检查清单

- [ ] 确认 `CI_DATA_DIR` 环境变量已设置
- [ ] Flask 和 Celery Worker 使用相同的环境变量
- [ ] 数据库文件只有一个，位于正确的位置
- [ ] 两个进程都有权限读写数据库文件
- [ ] 提交任务后能在历史记录中看到
- [ ] 任务状态能正确更新
