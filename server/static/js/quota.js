// ===== 配额管理页签功能 =====

async function loadQuotaData() {
    await Promise.all([loadQuotaInfo(), loadSpecialUsers()]);
}

async function loadQuotaInfo() {
    try {
        const response = await fetch('/api/admin/quota');
        const data = await response.json();

        // 格式化大小
        const formatGB = (bytes) => (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';

        // 更新总配额
        document.getElementById('quota-total').textContent = formatGB(data.total_bytes);
        document.getElementById('quota-used').textContent = formatGB(data.used_bytes);
        document.getElementById('quota-available').textContent = formatGB(data.available_bytes);
        document.getElementById('quota-percent').textContent = data.usage_percent + '%';

        // 更新进度条
        const progressFill = document.getElementById('quota-progress-fill');
        progressFill.style.width = data.usage_percent + '%';
        progressFill.textContent = data.usage_percent + '%';

        // 设置进度条颜色
        progressFill.classList.remove('warning', 'danger');
        if (data.usage_percent >= 90) {
            progressFill.classList.add('danger');
        } else if (data.usage_percent >= 70) {
            progressFill.classList.add('warning');
        }

        // 更新普通用户配额
        document.getElementById('normal-quota').textContent = formatGB(data.normal_users_quota);
        document.getElementById('normal-used').textContent = formatGB(data.normal_users_used);
        document.getElementById('normal-percent').textContent = data.normal_users_usage_percent + '%';

    } catch (e) {
        console.error('加载配额信息失败:', e);
    }
}

async function loadSpecialUsers() {
    try {
        const response = await fetch('/api/admin/special-users');
        const data = await response.json();

        const list = document.getElementById('special-users-list');

        if (data.special_users.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:40px;color:#999;">暂无特殊用户</div>';
            return;
        }

        list.innerHTML = data.special_users.map(user => `
            <div class="user-item">
                <div class="user-info">
                    <div class="user-name">${user.user_id}</div>
                    <div class="user-quota">
                        配额: ${user.quota_gb.toFixed(2)} GB /
                        已用: ${user.used_gb.toFixed(2)} GB
                        (${user.usage_percent}%)
                    </div>
                    <div class="user-progress">
                        <div class="user-progress-fill" style="width: ${user.usage_percent}%"></div>
                    </div>
                </div>
                <div class="user-actions">
                    <button class="btn-primary" onclick="editUser('${user.user_id}', ${user.quota_gb})">编辑</button>
                    <button class="btn-danger" onclick="deleteUser('${user.user_id}')">删除</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('加载特殊用户失败:', e);
    }
}

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
        alert('请填写正确的用户ID和配额');
        return;
    }

    try {
        const url = editingUserId
            ? `/api/admin/special-users/${userId}`
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

        if (response.ok) {
            closeUserModal();
            loadQuotaData();
            alert(editingUserId ? '更新成功' : '添加成功');
        } else {
            const error = await response.json();
            alert('操作失败: ' + (error.error || '未知错误'));
        }
    } catch (e) {
        console.error('保存用户失败:', e);
        alert('操作失败: ' + e.message);
    }
}

async function deleteUser(userId) {
    if (!confirm(`确定要删除特殊用户 ${userId} 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/special-users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${API_TOKEN}`
            }
        });

        if (response.ok) {
            loadQuotaData();
            alert('删除成功');
        } else {
            const error = await response.json();
            alert('删除失败: ' + (error.error || '未知错误'));
        }
    } catch (e) {
        console.error('删除用户失败:', e);
        alert('删除失败: ' + e.message);
    }
}
