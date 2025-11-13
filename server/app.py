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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_SIZE


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
    """获取任务信息"""
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
        "user": "optional-username"
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

    # 提交任务
    task = execute_build.delay({
        'mode': 'rsync',
        'workspace': workspace,
        'script': data['script'],
        'user': data.get('user', 'anonymous')
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
      - user: 可选的用户名
    """
    # 验证参数
    if 'code' not in request.files:
        return jsonify({'error': 'Missing code archive file'}), 400

    if 'script' not in request.form:
        return jsonify({'error': 'Missing script parameter'}), 400

    code_file = request.files['code']
    script = request.form['script']
    user = request.form.get('user', 'anonymous')

    # 验证文件名
    if code_file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    # 保存上传的文件
    filename = secure_filename(code_file.filename)
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    saved_filename = f"{timestamp}-{filename}"
    upload_path = f"{DATA_DIR}/uploads/{saved_filename}"

    code_file.save(upload_path)

    # 提交任务
    task = execute_build.delay({
        'mode': 'upload',
        'code_archive': upload_path,
        'script': script,
        'user': user
    })

    return jsonify({
        'job_id': task.id,
        'status': 'queued',
        'mode': 'upload'
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
        "user": "optional-username"
    }
    """
    data = request.json

    # 验证参数
    if not all(k in data for k in ['repo', 'branch', 'script']):
        return jsonify({'error': 'Missing required fields: repo, branch, script'}), 400

    # 提交任务
    task = execute_build.delay({
        'mode': 'git',
        'repo': data['repo'],
        'branch': data['branch'],
        'commit': data.get('commit'),
        'script': data['script'],
        'user': data.get('user', 'anonymous')
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
@require_auth
def get_stats():
    """获取统计信息"""
    inspect = celery_app.control.inspect()

    active = inspect.active() or {}
    scheduled = inspect.scheduled() or {}

    active_count = sum(len(tasks) for tasks in active.values())
    queued_count = sum(len(tasks) for tasks in scheduled.values())

    return jsonify({
        'running': active_count,
        'queued': queued_count,
        'workers': len(active)
    })


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
        const API_TOKEN = sessionStorage.getItem('ci_token') || prompt('请输入API Token:') || '';
        if (API_TOKEN) sessionStorage.setItem('ci_token', API_TOKEN);

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
                const response = await apiCall('/api/stats');
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
                const response = await apiCall('/api/jobs');
                const data = await response.json();

                const jobList = document.getElementById('job-list');

                if (data.jobs.length === 0) {
                    jobList.innerHTML = '<div class="empty-state">暂无活跃任务</div>';
                    return;
                }

                jobList.innerHTML = data.jobs.map(job => `
                    <div class="job-item" onclick="showLogs('${job.job_id}')">
                        <div class="job-header">
                            <span class="job-id">${job.job_id}</span>
                            <div class="badges">
                                <span class="badge status ${job.status}">${getStatusText(job.status)}</span>
                            </div>
                        </div>
                        <div class="job-info">
                            ${job.progress ? `📊 进度: ${job.progress.step} ${job.progress.percent}%` : ''}
                            ${job.result ? `⏱ 耗时: ${job.result.duration.toFixed(1)}s` : ''}
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to load jobs:', e);
            }
        }

        async function showLogs(jobId) {
            document.getElementById('log-modal').style.display = 'block';
            document.getElementById('modal-title').textContent = `任务日志 - ${jobId}`;
            document.getElementById('log-content').textContent = '加载中...';

            try {
                const response = await apiCall(`/api/jobs/${jobId}/logs`);
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
