// API Token仅用于创建任务等写操作，查看历史和日志无需Token
const API_TOKEN = sessionStorage.getItem('ci_token') || '';

// ===== 工具函数 =====

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
        // 解析UTC时间，转换为UTC+8显示
        const date = new Date(isoString);
        // 转换为UTC+8时区
        const utc8Date = new Date(date.getTime() + (8 * 60 * 60 * 1000));

        // 格式化为 YYYY-MM-DD HH:mm:ss
        const year = utc8Date.getUTCFullYear();
        const month = String(utc8Date.getUTCMonth() + 1).padStart(2, '0');
        const day = String(utc8Date.getUTCDate()).padStart(2, '0');
        const hours = String(utc8Date.getUTCHours()).padStart(2, '0');
        const minutes = String(utc8Date.getUTCMinutes()).padStart(2, '0');
        const seconds = String(utc8Date.getUTCSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
        return isoString;
    }
}

// ===== 标签切换 =====

function showMainTab(tabName) {
    // 切换标签
    document.querySelectorAll('.main-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    event.target.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');

    // 加载对应数据
    if (tabName === 'quota') {
        loadQuotaData();
    }
}

// ===== 初始化 =====

// 点击模态框外部关闭
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('log-modal').addEventListener('click', (e) => {
        if (e.target.id === 'log-modal') closeModal();
    });
    document.getElementById('user-modal').addEventListener('click', (e) => {
        if (e.target.id === 'user-modal') closeUserModal();
    });

    // 初始加载任务列表页面
    loadData();
});
