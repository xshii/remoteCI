#!/usr/bin/env python3
"""
Remote CI Flask API服务
支持rsync和HTTP上传两种模式
"""

import os
import json
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
from celery.result import AsyncResult

from server.config import (
    API_HOST, API_PORT, API_TOKEN, DATA_DIR,
    WORKSPACE_DIR, MAX_UPLOAD_SIZE
)
from server.celery_app import celery_app
from server.tasks import execute_build
from server.database import JobDatabase

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE

# 初始化数据库
job_db = JobDatabase(f"{DATA_DIR}/jobs.db")


# ============ 认证装饰器 ============
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if token.startswith('Bearer '):
            token = token[7:]

        if token != API_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 401

        return f(*args, **kwargs)
    return decorated_function


# ============ 辅助函数 ============
def get_job_info(task_id):
    """获取任务信息（优先从数据库获取）"""
    # 1. 先从数据库获取基础信息
    db_job = job_db.get_job(task_id)

    if db_job:
        job_info = {
            'job_id': db_job['job_id'],
            'status': db_job['status'],
            'mode': db_job['mode'],
            'user_id': db_job['user_id'],
            'script': db_job['script'],
            'created_at': db_job['created_at'],
            'started_at': db_job['started_at'],
            'finished_at': db_job['finished_at'],
            'duration': db_job['duration'],
            'exit_code': db_job['exit_code'],
        }

        # 2. 如果任务未完成，从Celery获取实时状态
        if db_job['status'] in ['queued', 'running']:
            result = AsyncResult(task_id, app=celery_app)

            if result.state == 'STARTED' or result.state == 'PROGRESS':
                job_info['status'] = 'running'
                if result.state == 'PROGRESS' and result.info:
                    job_info['progress'] = result.info
            elif result.state == 'SUCCESS':
                job_info['status'] = result.result.get('status', 'success')
                job_info['result'] = result.result
            elif result.state == 'FAILURE':
                job_info['status'] = 'error'
                job_info['error'] = str(result.info)

        return job_info

    # 3. 数据库中没有记录，从Celery获取（兼容旧数据）
    result = AsyncResult(task_id, app=celery_app)

    job_info = {
        'job_id': task_id,
        'status': result.state.lower(),
    }

    if result.state == 'PENDING':
        job_info['status'] = 'queued'
    elif result.state == 'STARTED':
        job_info['status'] = 'running'
    elif result.state == 'PROGRESS':
        job_info['status'] = 'running'
        job_info['progress'] = result.info
    elif result.state == 'SUCCESS':
        job_info['status'] = result.result.get('status', 'success')
        job_info['result'] = result.result
    elif result.state == 'FAILURE':
        job_info['status'] = 'error'
        job_info['error'] = str(result.info)

    return job_info


# ============ API路由 ============

@app.route('/api/jobs/rsync', methods=['POST'])
@require_auth
def create_rsync_job():
    """
    创建rsync模式任务
    请求体: {
        "workspace": "/var/ci-workspace/project-name",
        "script": "npm install && npm test",
        "user_id": "optional-user-id"
    }
    """
    data = request.json

    # 验证参数
    if not all(k in data for k in ['workspace', 'script']):
        return jsonify({'error': 'Missing required fields: workspace, script'}), 400

    workspace = data['workspace']

    # 验证workspace存在
    if not os.path.exists(workspace):
        return jsonify({'error': f'Workspace not found: {workspace}'}), 404

    # 验证workspace在允许的目录下（安全检查）
    workspace_abs = os.path.abspath(workspace)
    workspace_base = os.path.abspath(WORKSPACE_DIR)

    if not workspace_abs.startswith(workspace_base):
        return jsonify({'error': f'Workspace must be under {WORKSPACE_DIR}'}), 403

    # 准备任务数据
    job_data = {
        'mode': 'rsync',
        'workspace': workspace,
        'script': data['script'],
        'user_id': data.get('user_id')
    }

    # 提交任务
    task = execute_build.delay(job_data)

    # 记录到数据库
    job_db.create_job(task.id, {
        **job_data,
        'log_file': f"{DATA_DIR}/logs/{task.id}.log"
    })

    return jsonify({
        'job_id': task.id,
        'status': 'queued',
        'mode': 'rsync'
    }), 201


@app.route('/api/jobs/upload', methods=['POST'])
@require_auth
def create_upload_job():
    """
    创建上传模式任务
    multipart/form-data:
      - code: 代码包文件 (tar.gz)
      - script: 构建脚本
      - project_name: 项目名称（可选，推荐提供以保持与rsync模式一致）
      - user_id: 可选的用户ID
    """
    # 验证参数
    if 'code' not in request.files:
        return jsonify({'error': 'Missing code archive file'}), 400

    if 'script' not in request.form:
        return jsonify({'error': 'Missing script parameter'}), 400

    code_file = request.files['code']
    script = request.form['script']
    user_id = request.form.get('user_id')
    project_name = request.form.get('project_name', 'default')

    # 验证文件名
    if code_file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    # 保存上传的文件（使用项目名 + 时间戳 + UUID避免冲突）
    import uuid
    filename = secure_filename(code_file.filename)
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    unique_id = uuid.uuid4().hex[:8]
    # 格式: projectname-20241114-103045-abc12345-code.tar.gz
    saved_filename = f"{project_name}-{timestamp}-{unique_id}-{filename}"
    upload_path = f"{DATA_DIR}/uploads/{saved_filename}"

    code_file.save(upload_path)

    # 准备任务数据
    job_data = {
        'mode': 'upload',
        'code_archive': upload_path,
        'script': script,
        'user_id': user_id,
        'project_name': project_name
    }

    # 提交任务
    task = execute_build.delay(job_data)

    # 记录到数据库
    job_db.create_job(task.id, {
        **job_data,
        'log_file': f"{DATA_DIR}/logs/{task.id}.log"
    })

    return jsonify({
        'job_id': task.id,
        'status': 'queued',
        'mode': 'upload',
        'project_name': project_name
    }), 201


@app.route('/api/jobs/git', methods=['POST'])
@require_auth
def create_git_job():
    """
    创建Git模式任务（可选）
    请求体: {
        "repo": "https://github.com/user/repo.git",
        "branch": "main",
        "commit": "optional-commit-hash",
        "script": "npm install && npm test",
        "user_id": "optional-user-id"
    }
    """
    data = request.json

    # 验证参数
    if not all(k in data for k in ['repo', 'branch', 'script']):
        return jsonify({'error': 'Missing required fields: repo, branch, script'}), 400

    # 准备任务数据
    job_data = {
        'mode': 'git',
        'repo': data['repo'],
        'branch': data['branch'],
        'commit': data.get('commit'),
        'script': data['script'],
        'user_id': data.get('user_id')
    }

    # 提交任务
    task = execute_build.delay(job_data)

    # 记录到数据库
    job_db.create_job(task.id, {
        **job_data,
        'repo_url': data['repo'],
        'log_file': f"{DATA_DIR}/logs/{task.id}.log"
    })

    return jsonify({
        'job_id': task.id,
        'status': 'queued',
        'mode': 'git'
    }), 201


@app.route('/api/jobs/<job_id>', methods=['GET'])
@require_auth
def get_job(job_id):
    """获取任务状态"""
    job_info = get_job_info(job_id)
    return jsonify(job_info)


@app.route('/api/jobs/<job_id>/logs', methods=['GET'])
@require_auth
def get_job_logs(job_id):
    """获取任务日志"""
    log_file = f"{DATA_DIR}/logs/{job_id}.log"

    if not os.path.exists(log_file):
        # 如果任务还没开始，返回空日志
        return '', 200, {'Content-Type': 'text/plain; charset=utf-8'}

    # 支持tail参数
    lines = request.args.get('lines', type=int)

    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        if lines:
            content = ''.join(f.readlines()[-lines:])
        else:
            content = f.read()

    return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/api/jobs/history', methods=['GET'])
def get_job_history():
    """
    获取任务历史（免Token认证，支持分页和过滤）

    Query参数:
      - page: 页码（默认1）
      - per_page: 每页数量（默认20，最大100）
      - status: 按状态过滤 (queued, running, success, failed, timeout, error)
      - user_id: 按用户ID过滤
      - mode: 按模式过滤 (rsync, upload, git)
      - project_name: 按项目名过滤
    """
    # 获取参数
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # 最大100条

    filters = {}
    if request.args.get('status'):
        filters['status'] = request.args.get('status')
    if request.args.get('user_id'):
        filters['user_id'] = request.args.get('user_id')
    if request.args.get('mode'):
        filters['mode'] = request.args.get('mode')
    if request.args.get('project_name'):
        filters['project_name'] = request.args.get('project_name')

    # 查询任务列表
    jobs = job_db.get_jobs(
        limit=per_page,
        offset=(page - 1) * per_page,
        filters=filters if filters else None
    )

    # 统计总数
    total = job_db.count_jobs(filters=filters if filters else None)

    return jsonify({
        'jobs': jobs,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    })


@app.route('/api/jobs/history/<job_id>', methods=['GET'])
def get_history_job(job_id):
    """获取单个历史任务详情（免Token认证）"""
    job = job_db.get_job(job_id)

    if not job:
        # 尝试从Celery获取（兼容旧数据）
        job_info = get_job_info(job_id)
        if job_info.get('status') != 'queued':
            return jsonify(job_info)
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job)


@app.route('/api/jobs/history/<job_id>/logs', methods=['GET'])
def get_history_job_logs(job_id):
    """获取历史任务日志（免Token认证）"""
    log_file = f"{DATA_DIR}/logs/{job_id}.log"

    if not os.path.exists(log_file):
        return '', 200, {'Content-Type': 'text/plain; charset=utf-8'}

    # 支持tail参数
    lines = request.args.get('lines', type=int)

    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
        if lines:
            content = ''.join(f.readlines()[-lines:])
        else:
            content = f.read()

    return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/api/jobs', methods=['GET'])
@require_auth
def list_jobs():
    """列出最近的任务"""
    # 从Celery获取活跃任务
    inspect = celery_app.control.inspect()

    active_tasks = inspect.active() or {}
    scheduled_tasks = inspect.scheduled() or {}
    reserved_tasks = inspect.reserved() or {}

    jobs = []

    # 收集所有任务ID
    for worker_tasks in [active_tasks, scheduled_tasks, reserved_tasks]:
        for worker, tasks in worker_tasks.items():
            for task in tasks:
                job_info = get_job_info(task['id'])
                jobs.append(job_info)

    return jsonify({
        'jobs': jobs,
        'total': len(jobs)
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息（免Token认证，从数据库获取）"""
    days = request.args.get('days', 7, type=int)

    # 从数据库获取详细统计
    stats = job_db.get_stats(days=days)

    # 同时获取当前活跃任务数（来自Celery）
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active() or {}
        scheduled = inspect.scheduled() or {}

        active_count = sum(len(tasks) for tasks in active.values())
        queued_count = sum(len(tasks) for tasks in scheduled.values())

        stats['workers'] = len(active)
        # 如果数据库中的数字与Celery不一致，使用Celery的数字（更准确）
        if stats['running_count'] == 0 and active_count > 0:
            stats['running_count'] = active_count
        if stats['queued_count'] == 0 and queued_count > 0:
            stats['queued_count'] = queued_count
    except Exception as e:
        print(f"获取Celery统计失败: {e}")
        stats['workers'] = 0

    # 为了兼容旧的Web界面，添加别名
    stats['running'] = stats['running_count']
    stats['queued'] = stats['queued_count']

    return jsonify(stats)


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查（无需认证）"""
    try:
        # 检查Celery连接
        inspect = celery_app.control.inspect()
        stats = inspect.stats()

        if stats:
            return jsonify({'status': 'healthy', 'workers': len(stats)})
        else:
            return jsonify({'status': 'degraded', 'message': 'No workers available'}), 503
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


# ============ Web界面 ============

@app.route('/')
def index():
    """Web管理界面"""
    return render_template_string(WEB_TEMPLATE)


# Web界面HTML模板
WEB_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Remote CI Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-card h3 { color: #666; font-size: 14px; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #333; }

        .jobs-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .jobs-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .jobs-header h2 { color: #333; }
        .refresh-btn {
            padding: 8px 16px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .refresh-btn:hover { background: #0056b3; }

        .job-list { padding: 20px; }
        .job-item {
            padding: 15px;
            border: 1px solid #eee;
            border-radius: 4px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .job-item:hover { background: #f9f9f9; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }

        .job-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .job-id { font-family: monospace; font-size: 13px; color: #666; }
        .badges { display: flex; gap: 8px; }
        .badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .badge.mode { background: #e3f2fd; color: #1976d2; }
        .badge.status { color: white; }
        .badge.queued { background: #ffc107; color: #000; }
        .badge.running { background: #17a2b8; }
        .badge.success { background: #28a745; }
        .badge.failed { background: #dc3545; }
        .badge.error { background: #dc3545; }
        .badge.timeout { background: #ff9800; }

        .job-info { font-size: 14px; color: #666; }

        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        .modal-content {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            width: 90%;
            max-width: 900px;
            max-height: 85vh;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .modal-header {
            padding: 20px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .modal-body {
            padding: 20px;
            overflow-y: auto;
            flex: 1;
        }
        .close-btn {
            background: none;
            border: none;
            font-size: 28px;
            cursor: pointer;
            color: #999;
            line-height: 1;
        }
        .close-btn:hover { color: #333; }

        .log-content {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 4px;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 13px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 600px;
            overflow-y: auto;
        }

        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #666;
        }

        .filter-input {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
            width: 200px;
        }
        .filter-input:focus {
            outline: none;
            border-color: #007bff;
        }
        .clear-filter-btn {
            padding: 6px 12px;
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .clear-filter-btn:hover { background: #5a6268; }

        .mode-tabs {
            margin-bottom: 20px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .mode-tabs h3 { margin-bottom: 15px; color: #333; font-size: 16px; }
        .tabs {
            display: flex;
            gap: 10px;
        }
        .tab {
            padding: 8px 16px;
            border: 1px solid #ddd;
            background: #f9f9f9;
            cursor: pointer;
            border-radius: 4px;
            font-size: 14px;
        }
        .tab:hover { background: #e9e9e9; }
        .tab.active { background: #007bff; color: white; border-color: #007bff; }
        .mode-desc {
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-left: 3px solid #007bff;
            font-size: 13px;
            color: #666;
            line-height: 1.6;
        }
        .mode-desc code {
            background: #e9ecef;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Remote CI Dashboard</h1>

        <div class="stats">
            <div class="stat-card">
                <h3>执行中</h3>
                <div class="value" id="stat-running">-</div>
            </div>
            <div class="stat-card">
                <h3>队列中</h3>
                <div class="value" id="stat-queued">-</div>
            </div>
            <div class="stat-card">
                <h3>Worker数量</h3>
                <div class="value" id="stat-workers">-</div>
            </div>
        </div>

        <div class="mode-tabs">
            <h3>使用说明</h3>
            <div class="tabs">
                <div class="tab active" onclick="showMode('rsync')">rsync模式</div>
                <div class="tab" onclick="showMode('upload')">上传模式</div>
                <div class="tab" onclick="showMode('git')">Git模式</div>
            </div>
            <div id="mode-rsync" class="mode-desc">
                <strong>rsync模式（推荐）</strong><br>
                1. 使用rsync同步代码到服务器的workspace目录<br>
                2. 调用API触发构建<br>
                <code>rsync -avz ./ ci-user@remote-ci:/var/ci-workspace/myproject/</code><br>
                <code>curl -X POST .../api/jobs/rsync -d '{"workspace":"/var/ci-workspace/myproject","script":"npm test"}'</code>
            </div>
            <div id="mode-upload" class="mode-desc" style="display:none;">
                <strong>上传模式</strong><br>
                直接上传代码包（tar.gz）到远程CI<br>
                <code>tar -czf code.tar.gz .</code><br>
                <code>curl -X POST .../api/jobs/upload -F "code=@code.tar.gz" -F "script=npm test"</code>
            </div>
            <div id="mode-git" class="mode-desc" style="display:none;">
                <strong>Git模式</strong><br>
                远程CI直接克隆Git仓库<br>
                <code>curl -X POST .../api/jobs/git -d '{"repo":"https://...","branch":"main","script":"npm test"}'</code>
            </div>
        </div>

        <div class="jobs-container">
            <div class="jobs-header">
                <h2>任务列表</h2>
                <div class="controls">
                    <input type="text" id="user-id-filter" class="filter-input" placeholder="按用户ID筛选..." onkeypress="if(event.key==='Enter')loadData()">
                    <button class="clear-filter-btn" onclick="clearFilter()">清除</button>
                    <div class="auto-refresh">
                        <input type="checkbox" id="auto-refresh" checked>
                        <label for="auto-refresh">自动刷新 (5s)</label>
                    </div>
                    <button class="refresh-btn" onclick="loadData()">刷新</button>
                </div>
            </div>
            <div class="job-list" id="job-list"></div>
        </div>
    </div>

    <div class="modal" id="log-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">任务日志</h3>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="log-content" id="log-content">加载中...</div>
            </div>
        </div>
    </div>

    <script>
        // API Token仅用于创建任务等写操作，查看历史和日志无需Token
        const API_TOKEN = sessionStorage.getItem('ci_token') || '';

        function showMode(mode) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.mode-desc').forEach(d => d.style.display = 'none');
            event.target.classList.add('active');
            document.getElementById('mode-' + mode).style.display = 'block';
        }

        async function apiCall(url) {
            const response = await fetch(url, {
                headers: { 'Authorization': `Bearer ${API_TOKEN}` }
            });
            if (response.status === 401) {
                sessionStorage.removeItem('ci_token');
                alert('认证失败，请刷新页面重新输入Token');
                throw new Error('Unauthorized');
            }
            return response;
        }

        async function loadStats() {
            try {
                // 统计接口已改为免Token
                const response = await fetch('/api/stats');
                const stats = await response.json();

                document.getElementById('stat-running').textContent = stats.running || 0;
                document.getElementById('stat-queued').textContent = stats.queued || 0;
                document.getElementById('stat-workers').textContent = stats.workers || 0;
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }

        async function loadJobs() {
            try {
                // 构建查询参数
                const params = new URLSearchParams({ per_page: '50' });

                // 添加用户ID筛选
                const userId = document.getElementById('user-id-filter').value.trim();
                if (userId) {
                    params.append('user_id', userId);
                }

                // 使用免Token的历史接口
                const response = await fetch(`/api/jobs/history?${params}`);
                const data = await response.json();

                const jobList = document.getElementById('job-list');

                if (data.jobs.length === 0) {
                    jobList.innerHTML = '<div class="empty-state">暂无任务记录</div>';
                    return;
                }

                jobList.innerHTML = data.jobs.map(job => `
                    <div class="job-item" onclick="showLogs('${job.job_id}')">
                        <div class="job-header">
                            <span class="job-id">${job.project_name ? `${job.project_name} - ` : ''}${job.job_id}</span>
                            <div class="badges">
                                ${job.mode ? `<span class="badge mode">${job.mode}</span>` : ''}
                                <span class="badge status ${job.status}">${getStatusText(job.status)}</span>
                            </div>
                        </div>
                        <div class="job-info">
                            ${job.user_id ? `👤 ${job.user_id} ` : ''}
                            ${job.created_at ? `📅 ${formatTime(job.created_at)} ` : ''}
                            ${job.duration ? `⏱ ${job.duration.toFixed(1)}s` : ''}
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to load jobs:', e);
            }
        }

        function clearFilter() {
            document.getElementById('user-id-filter').value = '';
            loadData();
        }

        async function showLogs(jobId) {
            document.getElementById('log-modal').style.display = 'block';
            document.getElementById('modal-title').textContent = `任务日志 - ${jobId}`;
            document.getElementById('log-content').textContent = '加载中...';

            try {
                // 使用免Token的历史接口
                const response = await fetch(`/api/jobs/history/${jobId}/logs`);
                const logs = await response.text();
                document.getElementById('log-content').textContent = logs || '暂无日志';
            } catch (e) {
                document.getElementById('log-content').textContent = '加载日志失败: ' + e.message;
            }
        }

        function closeModal() {
            document.getElementById('log-modal').style.display = 'none';
        }

        function getStatusText(status) {
            const map = {
                'queued': '队列中',
                'running': '执行中',
                'success': '成功',
                'failed': '失败',
                'error': '错误',
                'timeout': '超时'
            };
            return map[status] || status;
        }

        function formatTime(isoString) {
            try {
                const date = new Date(isoString);
                // 格式化为 YYYY-MM-DD HH:mm:ss
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const seconds = String(date.getSeconds()).padStart(2, '0');
                return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
            } catch (e) {
                return isoString;
            }
        }

        async function loadData() {
            await Promise.all([loadStats(), loadJobs()]);
        }

        // 自动刷新
        setInterval(() => {
            if (document.getElementById('auto-refresh').checked) {
                loadData();
            }
        }, 5000);

        // 点击模态框外部关闭
        document.getElementById('log-modal').addEventListener('click', (e) => {
            if (e.target.id === 'log-modal') closeModal();
        });

        // 初始加载
        loadData();
    </script>
</body>
</html>'''


if __name__ == '__main__':
    print("=" * 60)
    print("Remote CI Server Starting...")
    print(f"API Host: {API_HOST}:{API_PORT}")
    print(f"API Token: {API_TOKEN}")
    print(f"Workspace Directory: {WORKSPACE_DIR}")
    print("=" * 60)
    print("\nAPI Endpoints:")
    print("  POST /api/jobs/rsync   - 提交rsync模式任务")
    print("  POST /api/jobs/upload  - 提交上传模式任务")
    print("  POST /api/jobs/git     - 提交Git模式任务")
    print("  GET  /api/jobs/<id>    - 查询任务状态")
    print("  GET  /api/jobs/<id>/logs - 获取任务日志")
    print("=" * 60)

    app.run(
        host=API_HOST,
        port=API_PORT,
        debug=False
    )
