// Remote CI 管理中心 - 配额管理功能
// 注意：查询操作无需Token，修改操作需要Token

// 从 sessionStorage 获取 Token（如果有的话）
let API_TOKEN = '';

// ===== 工具函数 =====

function formatGB(bytes) {
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

function promptForToken() {
    const token = prompt('请输入 API Token 以进行管理操作:');
    if (token) {
        API_TOKEN = token.trim();
        sessionStorage.setItem('ci_admin_token', API_TOKEN);
        return true;
    }
    return false;
}

// 尝试从 sessionStorage 加载 Token
if (sessionStorage.getItem('ci_admin_token')) {
    API_TOKEN = sessionStorage.getItem('ci_admin_token');
}

// ===== 配额信息加载 =====

async function loadQuotaInfo() {
    try {
        const response = await fetch('/api/admin/quota');
        const data = await response.json();

        if (data.error) {
            console.error('加载配额信息失败:', data.error);
            return;
        }

        // 更新总配额卡片
        document.getElementById('quota-total').textContent = formatGB(data.total_bytes);
        document.getElementById('quota-used').textContent = formatGB(data.used_bytes);
        document.getElementById('quota-available').textContent = formatGB(data.available_bytes);
        document.getElementById('quota-percent').textContent = data.usage_percent + '%';

        // 更新进度条
        const progressFill = document.getElementById('quota-progress-fill');
        const percentage = Math.min(data.usage_percent, 100);
        progressFill.style.width = percentage + '%';
        progressFill.textContent = percentage.toFixed(1) + '%';

        // 设置进度条颜色
        progressFill.classList.remove('warning', 'danger');
        if (data.usage_percent >= 90) {
            progressFill.classList.add('danger');
        } else if (data.usage_percent >= 70) {
            progressFill.classList.add('warning');
        }

        // 更新普通用户配额信息
        document.getElementById('normal-quota').textContent = formatGB(data.normal_users_quota);
        document.getElementById('normal-used').textContent = formatGB(data.normal_users_used);
        document.getElementById('normal-percent').textContent = data.normal_users_usage_percent.toFixed(1) + '%';

    } catch (e) {
        console.error('加载配额信息失败:', e);
        alert('加载配额信息失败: ' + e.message);
    }
}

// ===== 特殊用户管理 =====

async function loadSpecialUsers() {
    try {
        const response = await fetch('/api/admin/special-users');
        const data = await response.json();

        if (data.error) {
            console.error('加载特殊用户失败:', data.error);
            return;
        }

        const list = document.getElementById('special-users-list');

        if (!data.special_users || data.special_users.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="icon">👤</div>
                    <div>暂无特殊用户</div>
                    <div style="margin-top: 10px; font-size: 14px;">点击上方"添加特殊用户"按钮开始配置</div>
                </div>
            `;
            return;
        }

        list.innerHTML = data.special_users.map(user => {
            let progressClass = '';
            if (user.usage_percent >= 90) {
                progressClass = 'danger';
            } else if (user.usage_percent >= 70) {
                progressClass = 'warning';
            }

            return `
                <div class="user-item">
                    <div class="user-info">
                        <div class="user-name">👤 ${escapeHtml(user.user_id)}</div>
                        <div class="user-quota">
                            配额: ${user.quota_gb.toFixed(2)} GB |
                            已用: ${user.used_gb.toFixed(2)} GB |
                            使用率: ${user.usage_percent.toFixed(1)}%
                        </div>
                        <div class="user-progress">
                            <div class="user-progress-fill ${progressClass}" style="width: ${Math.min(user.usage_percent, 100)}%"></div>
                        </div>
                    </div>
                    <div class="user-actions">
                        <button class="btn-primary" onclick="editUser('${escapeHtml(user.user_id)}', ${user.quota_gb})">✏️ 编辑</button>
                        <button class="btn-danger" onclick="deleteUser('${escapeHtml(user.user_id)}')">🗑️ 删除</button>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.error('加载特殊用户失败:', e);
        alert('加载特殊用户失败: ' + e.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ===== 模态框管理 =====

let editingUserId = null;

function showAddUserModal() {
    editingUserId = null;
    document.getElementById('user-modal-title').textContent = '添加特殊用户';
    document.getElementById('user-id-input').value = '';
    document.getElementById('user-id-input').disabled = false;
    document.getElementById('quota-input').value = '';
    document.getElementById('user-modal').style.display = 'block';
}

function editUser(userId, quotaGb) {
    editingUserId = userId;
    document.getElementById('user-modal-title').textContent = '编辑特殊用户';
    document.getElementById('user-id-input').value = userId;
    document.getElementById('user-id-input').disabled = true;
    document.getElementById('quota-input').value = quotaGb;
    document.getElementById('user-modal').style.display = 'block';
}

function closeUserModal() {
    document.getElementById('user-modal').style.display = 'none';
    editingUserId = null;
}

async function saveUser() {
    const userId = document.getElementById('user-id-input').value.trim();
    const quotaGb = parseFloat(document.getElementById('quota-input').value);

    if (!userId || !quotaGb || quotaGb <= 0) {
        alert('请填写正确的用户 ID 和配额（必须大于 0）');
        return;
    }

    // 检查是否有 Token
    if (!API_TOKEN) {
        if (!promptForToken()) {
            alert('需要 Token 才能执行管理操作');
            return;
        }
    }

    try {
        const url = editingUserId
            ? `/api/admin/special-users/${encodeURIComponent(userId)}`
            : '/api/admin/special-users';

        const method = editingUserId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_TOKEN}`
            },
            body: JSON.stringify({
                user_id: userId,
                quota_gb: quotaGb
            })
        });

        if (response.status === 401) {
            // Token 无效，清除并重新提示
            API_TOKEN = '';
            sessionStorage.removeItem('ci_admin_token');
            alert('Token 无效或已过期，请重新输入');
            if (promptForToken()) {
                // 重试
                return saveUser();
            }
            return;
        }

        const result = await response.json();

        if (response.ok) {
            closeUserModal();
            await loadQuotaData();
            alert(editingUserId ? '✅ 更新成功' : '✅ 添加成功');
        } else {
            alert('❌ 操作失败: ' + (result.error || '未知错误'));
        }
    } catch (e) {
        console.error('保存用户失败:', e);
        alert('❌ 操作失败: ' + e.message);
    }
}

async function deleteUser(userId) {
    if (!confirm(`确定要删除特殊用户 "${userId}" 吗？\n\n删除后该用户将使用普通共享配额。`)) {
        return;
    }

    // 检查是否有 Token
    if (!API_TOKEN) {
        if (!promptForToken()) {
            alert('需要 Token 才能执行管理操作');
            return;
        }
    }

    try {
        const response = await fetch(`/api/admin/special-users/${encodeURIComponent(userId)}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${API_TOKEN}`
            }
        });

        if (response.status === 401) {
            // Token 无效，清除并重新提示
            API_TOKEN = '';
            sessionStorage.removeItem('ci_admin_token');
            alert('Token 无效或已过期，请重新输入');
            if (promptForToken()) {
                // 重试
                return deleteUser(userId);
            }
            return;
        }

        const result = await response.json();

        if (response.ok) {
            await loadQuotaData();
            alert('✅ 删除成功');
        } else {
            alert('❌ 删除失败: ' + (result.error || '未知错误'));
        }
    } catch (e) {
        console.error('删除用户失败:', e);
        alert('❌ 删除失败: ' + e.message);
    }
}

// ===== 主加载函数 =====

async function loadQuotaData() {
    await Promise.all([loadQuotaInfo(), loadSpecialUsers()]);
}

// ===== 页面初始化 =====

document.addEventListener('DOMContentLoaded', () => {
    // 点击模态框外部关闭
    document.getElementById('user-modal').addEventListener('click', (e) => {
        if (e.target.id === 'user-modal') {
            closeUserModal();
        }
    });

    // 初始加载数据
    loadQuotaData();

    // 设置自动刷新（每 5 秒）
    setInterval(() => {
        loadQuotaData();
    }, 5000);
});
