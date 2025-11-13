# 架构设计文档

## 系统架构

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         公共CI环境                               │
│  - GitHub Actions / GitLab CI / Jenkins                         │
│  - 30分钟超时限制                                                │
│  - 受限的计算资源                                                │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ 1. rsync同步代码
                   │ 2. HTTP提交任务
                   │ 3. 轮询状态（最多25分钟）
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      远程CI服务器                                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Flask API Server (Port 5000)                            │  │
│  │  - RESTful API                                           │  │
│  │  - Token认证                                             │  │
│  │  - Web管理界面                                           │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                               │
│                 │ 提交任务                                      │
│                 ▼                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Redis (Port 6379)                                       │  │
│  │  - 任务队列（Broker）                                    │  │
│  │  - 结果存储（Backend）                                   │  │
│  └──────────────┬───────────────────────────────────────────┘  │
│                 │                                               │
│                 │ 获取任务                                      │
│                 ▼                                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Celery Worker (可启动多个)                             │  │
│  │  - 并发控制（默认2个）                                   │  │
│  │  - 任务执行                                              │  │
│  │  - 超时处理                                              │  │
│  │  - 日志记录                                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  文件系统                                                │  │
│  │  - /var/ci-workspace/  (rsync同步目录)                  │  │
│  │  - /var/lib/remote-ci/logs/  (任务日志)                 │  │
│  │  - /var/lib/remote-ci/uploads/  (上传文件)              │  │
│  │  - /tmp/remote-ci/  (临时工作目录)                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Flower (可选，Port 5555)                                │  │
│  │  - 任务监控                                              │  │
│  │  - Worker状态                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. Flask API Server

**职责：**
- 接收任务提交请求
- 处理代码上传
- 提供任务状态查询
- 提供日志查询
- Web管理界面

**API端点：**
```
POST /api/jobs/rsync    # rsync模式任务提交
POST /api/jobs/upload   # 上传模式任务提交
POST /api/jobs/git      # Git模式任务提交
GET  /api/jobs/<id>     # 查询任务状态
GET  /api/jobs/<id>/logs # 获取任务日志
GET  /api/jobs          # 列出所有任务
GET  /api/stats         # 统计信息
GET  /api/health        # 健康检查
GET  /                  # Web界面
```

### 2. Celery Worker

**职责：**
- 从Redis队列获取任务
- 执行构建任务
- 记录执行日志
- 更新任务状态
- 清理临时文件

**工作流程：**
```python
1. 获取任务参数
2. 准备代码
   - rsync模式：复制workspace代码
   - upload模式：解压上传的tar.gz
   - git模式：克隆仓库
3. 执行构建脚本
4. 记录输出到日志文件
5. 返回结果（success/failed/timeout/error）
6. 清理临时文件
```

### 3. Redis

**职责：**
- 作为Celery的消息队列（Broker）
- 存储任务结果（Result Backend）
- 支持任务状态查询

**数据结构：**
```
celery:tasks:<task_id>      # 任务元数据
celery:result:<task_id>     # 任务结果
celery:workers              # Worker注册信息
```

## 任务执行流程

### rsync模式

```
1. 公共CI: rsync同步代码到/var/ci-workspace/project/
   ↓
2. 公共CI: POST /api/jobs/rsync
   {
     "workspace": "/var/ci-workspace/project",
     "script": "npm test"
   }
   ↓
3. Flask API: 验证workspace路径，提交到Celery队列
   ↓
4. Celery Worker: 从队列获取任务
   ↓
5. Worker: 复制workspace代码到临时目录
   ↓
6. Worker: 在临时目录执行脚本
   ↓
7. Worker: 记录日志，更新状态
   ↓
8. 公共CI: 轮询GET /api/jobs/<id>，获取状态
   ↓
9. 状态=success/failed: 公共CI获取日志并退出
```

### 上传模式

```
1. 公共CI: 打包代码 tar -czf code.tar.gz .
   ↓
2. 公共CI: POST /api/jobs/upload (multipart/form-data)
   - code: code.tar.gz文件
   - script: "npm test"
   ↓
3. Flask API: 保存上传文件到/var/lib/remote-ci/uploads/
   ↓
4. Flask API: 提交任务到Celery队列
   ↓
5. Celery Worker: 从队列获取任务
   ↓
6. Worker: 解压tar.gz到临时目录
   ↓
7. Worker: 执行脚本
   ↓
8. Worker: 记录日志，清理上传文件
   ↓
9. 公共CI: 轮询并获取结果
```

## 并发控制机制

### Celery并发设置

```python
# Celery Worker启动参数
celery -A server.celery_app worker --concurrency=2

# 配置说明
worker_prefetch_multiplier = 1  # 每次只预取1个任务
# 这确保了精确的并发控制
```

### Redis队列机制

```
Redis队列是FIFO（先进先出）

任务提交顺序：Job1 -> Job2 -> Job3 -> Job4

Worker1处理：Job1
Worker2处理：Job2
队列中：Job3, Job4

Job1完成 -> Worker1处理Job3
Job2完成 -> Worker2处理Job4
```

## 超时处理策略

### 公共CI侧超时（25分钟）

```bash
MAX_WAIT=1500  # 25分钟
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    # 轮询任务状态
    if [ 任务完成 ]; then
        获取结果并退出
    fi
    sleep 10
    ELAPSED += 10
done

# 超时但不返回失败
echo "任务仍在执行，请通过Web界面查看"
exit 0
```

### 远程CI侧超时（1小时）

```python
# Celery配置
task_time_limit = 3600  # 硬超时1小时
task_soft_time_limit = 3540  # 软超时59分钟

# 超过软超时会抛出SoftTimeLimitExceeded
# 超过硬超时会强制终止
```

## 数据持久化

### 任务元数据

```python
# Redis存储（临时）
保留时间 = LOG_RETENTION_DAYS（默认7天）

# 不持久化到数据库，原因：
# - 10人团队规模小
# - Redis足够
# - 减少复杂度
```

### 日志文件

```
路径: /var/lib/remote-ci/logs/<job_id>.log
格式: 纯文本
保留: 手动清理或定时清理
大小: 无限制（依赖磁盘空间）
```

### 代码存储

```
rsync模式: /var/ci-workspace/<project>/
  - 持久化，支持增量同步
  - 需要手动管理

upload模式: /var/lib/remote-ci/uploads/<timestamp>-<filename>
  - 任务完成后自动删除
  - 临时存储

Git模式: /tmp/remote-ci/<job_id>/
  - 任务完成后自动删除
  - 临时存储
```

## 安全设计

### 认证机制

```python
# Token认证
Authorization: Bearer <API_TOKEN>

# Token验证
def require_auth(f):
    token = request.headers.get('Authorization')
    if token != API_TOKEN:
        return 401
```

### 路径验证（防止目录遍历）

```python
# rsync模式workspace验证
workspace_abs = os.path.abspath(workspace)
workspace_base = os.path.abspath(WORKSPACE_DIR)

if not workspace_abs.startswith(workspace_base):
    return 403  # 禁止访问workspace目录外的路径
```

### 文件上传限制

```python
# 最大上传500MB
MAX_CONTENT_LENGTH = 500 * 1024 * 1024

# 文件名安全处理
filename = secure_filename(code_file.filename)
```

## 扩展性设计

### 横向扩展Worker

```bash
# 启动多个Worker进程
celery -A server.celery_app worker --concurrency=4

# 或在多台机器上启动Worker
# 只需连接同一个Redis
```

### 多项目隔离

```bash
# 使用workspace隔离
/var/ci-workspace/project-a/
/var/ci-workspace/project-b/

# 每个项目独立的rsync目录
```

### 多用户支持

```python
# 当前：单Token
# 扩展：用户表 + 每用户独立Token
# 扩展：项目级别权限控制
```

## 性能优化

### rsync增量同步

```bash
# 首次同步：传输全部文件
rsync -avz ./ remote:/workspace/

# 后续同步：只传输变化的文件
rsync -avz ./ remote:/workspace/
# 速度提升10倍+
```

### 日志流式写入

```python
# 不缓存日志，实时写入
with open(log_file, 'w') as log:
    log.write(message)
    log.flush()  # 立即刷新到磁盘
```

### Redis连接池

```python
# Celery自动使用连接池
broker_pool_limit = 10
```

## 监控和可观测性

### 指标收集

```python
GET /api/stats
{
  "running": 2,      # 正在执行的任务
  "queued": 5,       # 队列中的任务
  "workers": 2       # 活跃Worker数
}
```

### 日志聚合

```bash
/var/log/remote-ci/api.log       # API访问日志
/var/log/remote-ci/worker.log    # Worker执行日志
/var/lib/remote-ci/logs/<id>.log # 任务构建日志
```

### Flower监控

```
访问: http://server:5555
功能:
  - 实时任务列表
  - Worker状态
  - 任务执行时间统计
  - 失败任务追踪
```

## 技术选型理由

| 技术 | 理由 |
|------|------|
| Python + Flask | 轻量、易部署、生态丰富 |
| Celery + Redis | 成熟的任务队列，并发控制完善 |
| 无Docker | 降低部署复杂度，满足需求 |
| systemd | Linux标准服务管理 |
| rsync | 增量同步快，标准工具 |
| 纯文本日志 | 简单直接，易于查看和处理 |

## 未来扩展方向

1. **数据库持久化**：PostgreSQL存储任务历史
2. **Webhook通知**：任务完成后回调
3. **多租户支持**：项目级别隔离
4. **产物存储**：保存构建产物
5. **定时任务**：Cron风格的定时构建
6. **Pipeline支持**：多阶段构建流程
