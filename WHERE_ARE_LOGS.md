# 日志输出位置说明

## database.py 中的 print 语句会在哪里显示？

### 场景 1: 手动在终端启动（最直观）✅ 推荐用于调试

**启动方式：**
```bash
# 终端 1: 启动 Flask
cd /home/user/remoteCI
python3 -m server.app

# 终端 2: 启动 Celery Worker
cd /home/user/remoteCI
celery -A server.celery_app worker --loglevel=info
```

**日志显示位置：**
- ✅ **直接显示在当前终端窗口**
- 所有 print 输出和 logging 日志都会实时显示
- Flask 日志同时保存到：`{DATA_DIR}/logs/app.log`
- Celery 日志同时保存到：`{DATA_DIR}/logs/celery_worker.log`

**示例输出：**
```
[数据库初始化] 路径: /home/user/remoteCI/data/jobs.db
[数据库初始化] 文件存在: False
 * Serving Flask app 'server.app'
 * Debug mode: off
[数据库写入] 准备创建任务记录
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: abc-123-xyz
✓ 任务记录创建成功
```

---

### 场景 2: 使用 systemd 服务启动

**启动方式：**
```bash
sudo systemctl start remote-ci
sudo systemctl start celery
```

**日志显示位置：**
- ✅ **systemd journal 日志系统**
- 通过 `journalctl` 命令查看

**查看方法：**

```bash
# 实时查看 Flask 日志（推荐）
sudo journalctl -u remote-ci -f

# 实时查看 Celery 日志
sudo journalctl -u celery -f

# 同时查看两个服务的日志
sudo journalctl -u remote-ci -u celery -f

# 查看最近 100 行
sudo journalctl -u remote-ci -n 100

# 查看最近 1 小时的日志
sudo journalctl -u remote-ci --since "1 hour ago"

# 只看数据库相关的日志
sudo journalctl -u remote-ci -u celery | grep "数据库"

# 保存日志到文件
sudo journalctl -u remote-ci -u celery --since "1 hour ago" > debug_logs.txt
```

---

### 场景 3: 使用 supervisor 启动

**启动方式：**
```bash
sudo supervisorctl start remote-ci
sudo supervisorctl start celery
```

**日志显示位置：**
- ✅ **supervisor 配置的日志文件**
- 通常在 `/var/log/supervisor/` 目录下

**查看方法：**

```bash
# 查看 Flask 日志
tail -f /var/log/supervisor/remote-ci-stdout.log
tail -f /var/log/supervisor/remote-ci-stderr.log

# 查看 Celery 日志
tail -f /var/log/supervisor/celery-stdout.log
tail -f /var/log/supervisor/celery-stderr.log

# 搜索数据库相关日志
grep "数据库" /var/log/supervisor/*.log
```

**注意：** 日志文件路径取决于 supervisor 配置文件中的 `stdout_logfile` 和 `stderr_logfile` 设置。

---

### 场景 4: 后台运行（使用 nohup 或 &）

**启动方式：**
```bash
nohup python3 -m server.app > flask.log 2>&1 &
nohup celery -A server.celery_app worker > celery.log 2>&1 &
```

**日志显示位置：**
- ✅ **指定的日志文件**（上例中是 `flask.log` 和 `celery.log`）

**查看方法：**
```bash
# 实时查看
tail -f flask.log
tail -f celery.log

# 搜索数据库日志
grep "数据库" flask.log celery.log
```

---

## 🎯 推荐的调试方法

### 方法 1: 终端直接运行（最简单）✨

打开 2 个终端窗口：

**终端 1 - Flask:**
```bash
cd /home/user/remoteCI
export CI_DATA_DIR=/home/user/remoteCI/data
python3 -m server.app
```

**终端 2 - Celery:**
```bash
cd /home/user/remoteCI
export CI_DATA_DIR=/home/user/remoteCI/data
celery -A server.celery_app worker --loglevel=info
```

**终端 3 - 提交测试任务:**
```bash
# 提交任务
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }'
```

然后观察终端 1 和终端 2 的输出！

---

### 方法 2: systemd + journalctl

如果系统已经在运行：

```bash
# 1. 重启服务（获得新的日志）
sudo systemctl restart remote-ci celery

# 2. 打开实时日志窗口
sudo journalctl -u remote-ci -u celery -f

# 3. 在另一个终端提交测试任务
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }'
```

---

## 🔍 如何验证日志工作正常

启动服务后，你应该立即看到：

```
[数据库初始化] 路径: /home/user/remoteCI/data/jobs.db
[数据库初始化] 文件存在: True
```

如果没看到这些日志，可能的原因：
1. ❌ Python 输出缓冲（解决：添加 `PYTHONUNBUFFERED=1` 环境变量）
2. ❌ 日志被重定向到其他地方
3. ❌ 使用了不同的启动脚本

---

## 💡 增强日志输出

如果日志输出被缓冲，添加环境变量：

```bash
# 临时设置（当前会话）
export PYTHONUNBUFFERED=1

# 或在启动命令前添加
PYTHONUNBUFFERED=1 python3 -m server.app

# systemd 服务中添加
[Service]
Environment="PYTHONUNBUFFERED=1"
```

---

## 📝 完整示例：从零开始调试

```bash
# 1. 停止现有服务（如果有）
sudo systemctl stop remote-ci celery
# 或
pkill -f "flask"
pkill -f "celery.*worker"

# 2. 设置环境变量
export CI_DATA_DIR=/home/user/remoteCI/data
export PYTHONUNBUFFERED=1

# 3. 终端 1: 启动 Flask（保持打开）
cd /home/user/remoteCI
python3 -m server.app

# 你应该立即看到：
# [数据库初始化] 路径: /home/user/remoteCI/data/jobs.db
# [数据库初始化] 文件存在: True/False

# 4. 终端 2: 启动 Celery（保持打开）
cd /home/user/remoteCI
export CI_DATA_DIR=/home/user/remoteCI/data
export PYTHONUNBUFFERED=1
celery -A server.celery_app worker --loglevel=info

# 你应该也看到数据库初始化日志

# 5. 终端 3: 提交任务并观察
curl -X POST http://localhost:5000/api/jobs/git \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/octocat/Hello-World.git",
    "branch": "master",
    "script": "echo test",
    "user_id": "test-user"
  }'

# 观察终端 1（Flask）的输出：
# [数据库写入] 准备创建任务记录
# ...

# 观察终端 2（Celery）的输出：
# [数据库更新] 更新任务开始状态
# ...

# 6. 查询任务
curl http://localhost:5000/api/jobs/history

# 观察终端 1 的输出：
# [数据库查询] 查询任务列表
# ✓ 查询完成，返回 X 条记录
```

---

## 🎯 关键检查点

当你提交任务后，应该看到：

### ✅ 在 Flask 日志中：
```
[数据库写入] 准备创建任务记录
  数据库路径: /home/user/remoteCI/data/jobs.db
  任务ID: xxx
  模式: git
  用户ID: test-user
✓ 任务记录创建成功
  验证查询: 找到 1 条记录
  数据库文件大小: 12345 字节
```

### ✅ 在 Celery 日志中：
```
[数据库更新] 更新任务开始状态
  数据库路径: /home/user/remoteCI/data/jobs.db  ← 必须与 Flask 相同！
  任务ID: xxx
✓ 任务状态更新为 running，影响 1 行
```

### ⚠️ 如果路径不同，问题找到了！

比如：
- Flask: `/home/user/remoteCI/data/jobs.db`
- Celery: `/tmp/data/jobs.db` ❌ 不同！

这就是导致任务无法查询的原因！

---

## 🛠️ 故障排除

### 问题 1: 看不到任何日志

**原因：** Python 输出缓冲

**解决：**
```bash
export PYTHONUNBUFFERED=1
python3 -m server.app
```

### 问题 2: systemd 日志为空

**检查：**
```bash
# 查看服务状态
sudo systemctl status remote-ci

# 查看最近的错误
sudo journalctl -u remote-ci -xe

# 确认服务正在运行
ps aux | grep flask
```

### 问题 3: 日志输出到了其他地方

**查找：**
```bash
# 搜索日志文件
find /var/log -name "*remote*" -o -name "*celery*" 2>/dev/null

# 检查 supervisor 配置
cat /etc/supervisor/conf.d/*.conf | grep -E "stdout_logfile|stderr_logfile"

# 检查 systemd 服务配置
systemctl cat remote-ci | grep -E "StandardOutput|StandardError"
```

---

## 📚 相关命令速查

```bash
# 实时查看 systemd 日志
sudo journalctl -u remote-ci -f

# 查看最近的日志
sudo journalctl -u remote-ci -n 100

# 只看数据库相关
sudo journalctl -u remote-ci | grep "数据库"

# 保存到文件
sudo journalctl -u remote-ci --since "1 hour ago" > logs.txt

# 查看进程
ps aux | grep -E "flask|celery"

# 查看进程打开的文件
lsof -p $(pgrep -f flask) | grep ".db"
```
