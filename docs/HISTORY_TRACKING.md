# Remote CI 历史任务记录问题分析与解决方案

## 🔍 问题描述

当前系统**无法显示历史任务记录**，Web界面只能看到正在执行或排队中的任务。一旦任务完成（成功或失败），它就从任务列表中消失了。

## 📊 当前实现分析

### 代码实现（app.py 第230-253行）

```python
@app.route('/api/jobs', methods=['GET'])
@require_auth
def list_jobs():
    """列出最近的任务"""
    # 从Celery获取活跃任务
    inspect = celery_app.control.inspect()

    active_tasks = inspect.active() or {}      # 正在执行的任务
    scheduled_tasks = inspect.scheduled() or {}  # 已调度的任务
    reserved_tasks = inspect.reserved() or {}    # 已保留的任务

    # ⚠️ 只收集活跃任务，不包括已完成的任务
    jobs = []
    for worker_tasks in [active_tasks, scheduled_tasks, reserved_tasks]:
        for worker, tasks in worker_tasks.items():
            for task in tasks:
                job_info = get_job_info(task['id'])
                jobs.append(job_info)

    return jsonify({
        'jobs': jobs,
        'total': len(jobs)
    })
```

### 问题分析

| 任务状态 | 是否显示 | 原因 |
|---------|---------|------|
| 排队中（queued） | ✅ 显示 | 在 reserved_tasks 中 |
| 执行中（running） | ✅ 显示 | 在 active_tasks 中 |
| 已完成（success/failed） | ❌ **不显示** | 不在 inspect 结果中 |

### 数据留存情况

1. **Celery结果（Redis）**
   ```python
   # config.py 第51行
   'result_expires': 86400 * LOG_RETENTION_DAYS,  # 默认7天
   ```
   - ✅ 任务结果在Redis中保留7天
   - ✅ 可以通过 `AsyncResult(task_id)` 查询
   - ❌ 但没有办法列出所有历史任务ID

2. **日志文件**
   ```python
   # tasks.py 第63行
   log_file = f"{DATA_DIR}/logs/{task_id}.log"
   ```
   - ✅ 每个任务的日志文件都保留
   - ✅ 文件路径：`data/logs/{task_id}.log`
   - ❌ 但只有任务ID，无法获取其他元数据（提交时间、用户、脚本等）

3. **上传文件**
   ```python
   # app.py 第143-147行
   timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
   saved_filename = f"{timestamp}-{filename}"
   upload_path = f"{DATA_DIR}/uploads/{saved_filename}"
   ```
   - ✅ 上传的代码包保存在 uploads 目录
   - ❌ 任务完成后会被删除（tasks.py 第261-266行）

## 🎯 用户需求

### 场景1：查看最近的构建历史

```
用户登录Web界面，希望看到：
- 今天提交的所有任务
- 每个任务的状态（成功/失败）
- 任务的提交时间、执行时长
- 可以点击查看日志
```

### 场景2：调试失败的构建

```
开发者想知道：
- 上次失败是什么时候？
- 失败的原因是什么？
- 最近几次构建的趋势（是否频繁失败）
```

### 场景3：统计分析

```
团队leader想了解：
- 本周的构建次数
- 成功率是多少
- 平均构建时长
- 哪个分支构建最频繁
```

## 💡 解决方案

### 方案1：基于日志文件的简单实现（推荐⭐⭐⭐）

#### 优点
- ✅ 无需额外依赖
- ✅ 实现简单
- ✅ 利用现有日志文件

#### 实现思路

1. **扫描日志目录获取任务列表**
   ```python
   import os
   import re
   from datetime import datetime

   def list_all_jobs():
       """列出所有任务（活跃 + 历史）"""
       jobs = []

       # 1. 从日志文件获取历史任务
       log_dir = f"{DATA_DIR}/logs"
       for log_file in os.listdir(log_dir):
           if log_file.endswith('.log'):
               job_id = log_file[:-4]  # 去掉 .log 后缀
               job_info = parse_job_from_log(job_id)
               jobs.append(job_info)

       # 2. 更新活跃任务的状态（覆盖日志中的状态）
       inspect = celery_app.control.inspect()
       active_ids = set()
       for tasks in [inspect.active(), inspect.scheduled(), inspect.reserved()]:
           if tasks:
               for worker, task_list in tasks.items():
                   for task in task_list:
                       active_ids.add(task['id'])

       # 3. 合并结果
       for job in jobs:
           if job['job_id'] in active_ids:
               # 更新为实时状态
               result = AsyncResult(job['job_id'], app=celery_app)
               job['status'] = get_real_status(result)

       # 4. 按时间排序
       jobs.sort(key=lambda x: x['start_time'], reverse=True)

       return jobs
   ```

2. **从日志文件解析元数据**
   ```python
   def parse_job_from_log(job_id):
       """从日志文件解析任务信息"""
       log_file = f"{DATA_DIR}/logs/{job_id}.log"

       if not os.path.exists(log_file):
           return None

       metadata = {
           'job_id': job_id,
           'status': 'unknown',
           'start_time': None,
           'end_time': None,
           'duration': None,
           'mode': 'unknown',
           'user': 'unknown',
           'exit_code': None
       }

       with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
           content = f.read()

           # 解析开始时间
           match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\].*开始时间', content)
           if match:
               metadata['start_time'] = match.group(1)

           # 解析模式
           match = re.search(r'模式: (\w+)', content)
           if match:
               metadata['mode'] = match.group(1)

           # 解析提交者
           match = re.search(r'提交者: (\S+)', content)
           if match:
               metadata['user'] = match.group(1)

           # 解析结束时间
           match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\].*结束时间', content)
           if match:
               metadata['end_time'] = match.group(1)

           # 解析耗时
           match = re.search(r'总耗时: ([\d.]+) 秒', content)
           if match:
               metadata['duration'] = float(match.group(1))

           # 解析退出码
           match = re.search(r'退出码: (-?\d+)', content)
           if match:
               metadata['exit_code'] = int(match.group(1))

           # 判断状态
           if '✓ 构建成功' in content:
               metadata['status'] = 'success'
           elif '✗ 构建失败' in content:
               metadata['status'] = 'failed'
           elif '✗ 任务超时' in content:
               metadata['status'] = 'timeout'
           elif '✗ 任务执行错误' in content:
               metadata['status'] = 'error'
           elif '任务异常终止' in content:
               metadata['status'] = 'error'
           else:
               metadata['status'] = 'running'

       return metadata
   ```

3. **添加分页和过滤**
   ```python
   @app.route('/api/jobs/history', methods=['GET'])
   @require_auth
   def get_job_history():
       """获取任务历史（支持分页和过滤）"""
       # 获取参数
       page = request.args.get('page', 1, type=int)
       per_page = request.args.get('per_page', 20, type=int)
       status = request.args.get('status')  # success, failed, running
       user = request.args.get('user')
       mode = request.args.get('mode')  # rsync, upload, git

       # 获取所有任务
       all_jobs = list_all_jobs()

       # 过滤
       if status:
           all_jobs = [j for j in all_jobs if j['status'] == status]
       if user:
           all_jobs = [j for j in all_jobs if j['user'] == user]
       if mode:
           all_jobs = [j for j in all_jobs if j['mode'] == mode]

       # 分页
       total = len(all_jobs)
       start = (page - 1) * per_page
       end = start + per_page
       jobs = all_jobs[start:end]

       return jsonify({
           'jobs': jobs,
           'total': total,
           'page': page,
           'per_page': per_page,
           'pages': (total + per_page - 1) // per_page
       })
   ```

4. **更新Web界面**
   ```javascript
   // 添加历史记录标签页
   async function loadAllJobs() {
       const response = await apiCall('/api/jobs/history?per_page=50');
       const data = await response.json();

       // 显示所有任务（包括历史）
       displayJobs(data.jobs);
   }

   // 添加过滤器
   function filterJobs(status) {
       loadJobsWithFilter({ status: status });
   }
   ```

#### 性能优化

```python
# 使用缓存避免频繁扫描文件系统
from functools import lru_cache
from datetime import datetime, timedelta

_job_cache = None
_cache_time = None

def list_all_jobs(use_cache=True):
    global _job_cache, _cache_time

    # 缓存30秒
    if use_cache and _cache_time and (datetime.now() - _cache_time).seconds < 30:
        return _job_cache

    jobs = scan_log_directory()
    _job_cache = jobs
    _cache_time = datetime.now()

    return jobs
```

---

### 方案2：使用SQLite持久化（生产推荐⭐⭐⭐⭐⭐）

#### 优点
- ✅ 查询速度快
- ✅ 支持复杂过滤和统计
- ✅ 支持大量历史记录
- ✅ 无需额外服务（SQLite是文件数据库）

#### 数据库设计

```sql
CREATE TABLE ci_jobs (
    job_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,           -- rsync, upload, git
    status TEXT NOT NULL,         -- queued, running, success, failed, timeout, error
    script TEXT NOT NULL,         -- 构建脚本
    user TEXT NOT NULL,           -- 提交者

    -- 时间信息
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    duration REAL,                -- 秒

    -- 结果信息
    exit_code INTEGER,
    error_message TEXT,

    -- 代码信息
    workspace TEXT,               -- rsync模式的workspace路径
    repo_url TEXT,                -- git模式的仓库URL
    branch TEXT,                  -- git模式的分支
    commit_hash TEXT,             -- git模式的commit

    -- 其他
    log_file TEXT,                -- 日志文件路径
    metadata TEXT                 -- JSON格式的其他元数据
);

-- 创建索引
CREATE INDEX idx_jobs_status ON ci_jobs(status);
CREATE INDEX idx_jobs_user ON ci_jobs(user);
CREATE INDEX idx_jobs_created_at ON ci_jobs(created_at DESC);
CREATE INDEX idx_jobs_mode ON ci_jobs(mode);
```

#### 实现代码

```python
import sqlite3
import json
from datetime import datetime

class JobDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ci_jobs (
                job_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                script TEXT NOT NULL,
                user TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                duration REAL,
                exit_code INTEGER,
                error_message TEXT,
                workspace TEXT,
                repo_url TEXT,
                branch TEXT,
                commit_hash TEXT,
                log_file TEXT,
                metadata TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON ci_jobs(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON ci_jobs(created_at DESC)')
        conn.commit()
        conn.close()

    def create_job(self, job_id, job_data):
        """创建任务记录"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ci_jobs (
                job_id, mode, status, script, user,
                created_at, log_file, workspace, repo_url, branch, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id,
            job_data['mode'],
            'queued',
            job_data['script'],
            job_data.get('user', 'anonymous'),
            datetime.now().isoformat(),
            f"{DATA_DIR}/logs/{job_id}.log",
            job_data.get('workspace'),
            job_data.get('repo'),
            job_data.get('branch'),
            json.dumps(job_data)
        ))
        conn.commit()
        conn.close()

    def update_job_status(self, job_id, status, result=None):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status == 'running':
            cursor.execute('''
                UPDATE ci_jobs
                SET status = ?, started_at = ?
                WHERE job_id = ?
            ''', (status, datetime.now().isoformat(), job_id))

        elif status in ['success', 'failed', 'timeout', 'error']:
            cursor.execute('''
                UPDATE ci_jobs
                SET status = ?, finished_at = ?, duration = ?, exit_code = ?, error_message = ?
                WHERE job_id = ?
            ''', (
                status,
                datetime.now().isoformat(),
                result.get('duration') if result else None,
                result.get('exit_code') if result else None,
                result.get('error') if result else None,
                job_id
            ))

        conn.commit()
        conn.close()

    def get_jobs(self, limit=50, offset=0, filters=None):
        """查询任务列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = 'SELECT * FROM ci_jobs'
        params = []

        if filters:
            conditions = []
            if filters.get('status'):
                conditions.append('status = ?')
                params.append(filters['status'])
            if filters.get('user'):
                conditions.append('user = ?')
                params.append(filters['user'])
            if filters.get('mode'):
                conditions.append('mode = ?')
                params.append(filters['mode'])

            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)

        query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        jobs = [dict(row) for row in rows]
        conn.close()

        return jobs

    def get_stats(self, days=7):
        """获取统计数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                AVG(CASE WHEN duration IS NOT NULL THEN duration ELSE NULL END) as avg_duration
            FROM ci_jobs
            WHERE created_at > ?
        ''', (cutoff,))

        row = cursor.fetchone()
        conn.close()

        return {
            'total': row[0],
            'success_count': row[1] or 0,
            'failed_count': row[2] or 0,
            'success_rate': (row[1] or 0) / row[0] if row[0] > 0 else 0,
            'avg_duration': row[3]
        }
```

#### 集成到API

```python
# 初始化数据库
job_db = JobDatabase(f"{DATA_DIR}/jobs.db")

@app.route('/api/jobs/rsync', methods=['POST'])
@require_auth
def create_rsync_job():
    # ... 验证代码 ...

    # 提交任务
    task = execute_build.delay(job_data)

    # 记录到数据库
    job_db.create_job(task.id, job_data)

    return jsonify({
        'job_id': task.id,
        'status': 'queued',
        'mode': 'rsync'
    }), 201

@app.route('/api/jobs/history', methods=['GET'])
@require_auth
def get_job_history():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    filters = {
        'status': request.args.get('status'),
        'user': request.args.get('user'),
        'mode': request.args.get('mode')
    }

    jobs = job_db.get_jobs(
        limit=per_page,
        offset=(page - 1) * per_page,
        filters={k: v for k, v in filters.items() if v}
    )

    return jsonify({
        'jobs': jobs,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_stats():
    days = request.args.get('days', 7, type=int)
    stats = job_db.get_stats(days=days)
    return jsonify(stats)
```

#### 在tasks.py中更新状态

```python
@celery_app.task(base=BuildTask, bind=True, name='remote_ci.build')
def execute_build(self, job_data):
    task_id = self.request.id

    # 更新为运行中
    job_db.update_job_status(task_id, 'running')

    try:
        # ... 执行构建 ...

        # 更新为成功/失败
        job_db.update_job_status(task_id, status, result)

        return result
    except Exception as e:
        job_db.update_job_status(task_id, 'error', {'error': str(e)})
        raise
```

---

### 方案3：使用PostgreSQL/MySQL（企业级⭐⭐⭐⭐）

#### 优点
- ✅ 支持高并发
- ✅ 更强大的查询能力
- ✅ 支持分布式部署

#### 缺点
- ❌ 需要额外的数据库服务
- ❌ 增加部署复杂度
- ❌ 对于轻量级CI系统过于复杂

---

## 📋 实现对比

| 方案 | 复杂度 | 性能 | 扩展性 | 推荐场景 |
|-----|-------|-----|-------|---------|
| 方案1（日志扫描） | ⭐ 简单 | ⭐⭐ 中等 | ⭐⭐ 一般 | 小团队、任务量<1000/天 |
| 方案2（SQLite） | ⭐⭐ 中等 | ⭐⭐⭐⭐ 快 | ⭐⭐⭐⭐ 好 | **推荐**，适合大部分场景 |
| 方案3（PostgreSQL） | ⭐⭐⭐ 复杂 | ⭐⭐⭐⭐⭐ 很快 | ⭐⭐⭐⭐⭐ 优秀 | 企业级、高并发 |

## 🎯 推荐实施步骤

### 第一阶段：快速修复（方案1）

1. 实现 `parse_job_from_log()` 函数
2. 添加 `/api/jobs/history` 接口
3. 更新Web界面显示历史任务
4. **预计工作量：2-3小时**

### 第二阶段：生产化（方案2）

1. 设计并创建SQLite数据库
2. 实现 `JobDatabase` 类
3. 在任务创建和更新时写入数据库
4. 添加统计分析接口
5. 更新Web界面支持过滤和分页
6. **预计工作量：1-2天**

### 第三阶段：优化（可选）

1. 添加数据导出功能（CSV/Excel）
2. 添加趋势图表
3. 添加邮件/Webhook通知
4. **预计工作量：1-2天**

## 🚀 快速开始

想要立即修复这个问题？我可以帮您实现：

1. **方案1（快速）**：基于日志文件的历史记录查询
2. **方案2（推荐）**：基于SQLite的完整解决方案

请告诉我您希望使用哪个方案，我将立即开始实现！
