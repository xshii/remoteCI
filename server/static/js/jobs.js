// ===== 任务列表页签功能 =====

function showMode(mode) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.mode-desc').forEach(d => d.style.display = 'none');
    event.target.classList.add('active');
    document.getElementById('mode-' + mode).style.display = 'block';
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
        const filterResult = document.getElementById('filter-result');

        // 显示查询结果数量
        if (userId) {
            filterResult.textContent = `找到 ${data.total} 条匹配记录`;
        } else {
            filterResult.textContent = `共 ${data.total} 条记录`;
        }

        if (data.jobs.length === 0) {
            if (userId) {
                jobList.innerHTML = `<div class="empty-state">未找到包含 "${userId}" 的用户ID<br><small>提示：支持部分匹配，例如输入"alice"可以匹配"alice"、"alice-test"等</small></div>`;
            } else {
                jobList.innerHTML = '<div class="empty-state">暂无任务记录</div>';
            }
            return;
        }

        jobList.innerHTML = data.jobs.map(job => `
            <div class="job-item">
                <div onclick="showLogs('${job.job_id}')" style="flex:1;cursor:pointer;">
                    <div class="job-header">
                        <span class="job-id">${job.project_name ? `${job.project_name} - ` : ''}${job.job_id}</span>
                        <div class="badges">
                            ${job.mode ? `<span class="badge mode">${job.mode}</span>` : ''}
                            <span class="badge status ${job.status}">${getStatusText(job.status)}</span>
                            ${job.is_expired ? '<span class="badge" style="background:#ff9800;color:#000;">已过期</span>' : ''}
                        </div>
                    </div>
                    <div class="job-info">
                        ${job.user_id ? `👤 ${job.user_id} ` : ''}
                        ${job.created_at ? `📅 ${formatTime(job.created_at)} ` : ''}
                        ${job.duration ? `⏱ ${job.duration.toFixed(1)}s` : ''}
                    </div>
                </div>
                ${job.status === 'success' && job.artifacts_path && !job.is_expired ? `
                    <button class="btn-primary" onclick="event.stopPropagation(); downloadArtifacts('${job.job_id}')" style="margin-left:10px;">
                        📦 下载产物
                    </button>
                ` : ''}
            </div>
        `).join('');
    } catch (e) {
        console.error('Failed to load jobs:', e);
    }
}

function clearFilter() {
    document.getElementById('user-id-filter').value = '';
    document.getElementById('filter-result').textContent = '';
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

async function loadData() {
    await Promise.all([loadStats(), loadJobs()]);
}

function downloadArtifacts(jobId) {
    // 直接打开下载链接
    window.open(`/api/jobs/${jobId}/artifacts`, '_blank');
}

// 自动刷新
setInterval(() => {
    if (document.getElementById('auto-refresh').checked) {
        loadData();
    }
}, 5000);
