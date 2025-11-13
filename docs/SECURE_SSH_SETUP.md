# 安全的SSH配置方案

## 安全问题

**问题：** 把SSH私钥上传到GitLab/GitHub的CI/CD系统是否安全？

**答案：** 有风险！如果账号被攻破或配置不当，私钥可能泄露。

## 更安全的替代方案

### 方案1：专用受限SSH密钥（推荐）⭐

为每个项目创建**独立的、权限受限的SSH密钥**。

#### 优势
- ✅ 即使密钥泄露，只影响单个项目
- ✅ 可以限制密钥只能执行特定命令
- ✅ 随时可以撤销单个密钥

#### 实施步骤

##### 1. 为项目创建专用密钥

```bash
# 在远程CI服务器上，为每个项目创建独立密钥
sudo -u ci-user ssh-keygen -t ed25519 \
  -f /home/ci-user/.ssh/project_myapp_key \
  -C "CI key for myapp project" \
  -N ""

# 生成：
# /home/ci-user/.ssh/project_myapp_key       (私钥)
# /home/ci-user/.ssh/project_myapp_key.pub   (公钥)
```

##### 2. 配置受限的authorized_keys

在远程CI服务器上添加**受限的公钥配置**：

```bash
# 编辑authorized_keys
sudo -u ci-user nano /home/ci-user/.ssh/authorized_keys

# 添加受限配置（单行）
command="rrsync -wo /var/ci-workspace/myapp",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA... CI key for myapp project
```

**参数说明：**
- `command="rrsync -wo /var/ci-workspace/myapp"` - 只允许rsync写入到指定目录
- `no-agent-forwarding` - 禁止SSH agent转发
- `no-port-forwarding` - 禁止端口转发
- `no-pty` - 禁止分配终端
- `no-user-rc` - 禁止执行~/.ssh/rc
- `no-X11-forwarding` - 禁止X11转发

##### 3. 安装rrsync（受限rsync）

```bash
# Ubuntu/Debian
sudo apt-get install rsync

# 下载rrsync脚本
sudo wget https://raw.githubusercontent.com/WayneD/rsync/master/support/rrsync -O /usr/local/bin/rrsync
sudo chmod +x /usr/local/bin/rrsync

# 或从rsync包中复制
gunzip < /usr/share/doc/rsync/scripts/rrsync.gz > /usr/local/bin/rrsync
sudo chmod +x /usr/local/bin/rrsync
```

##### 4. 配置到GitLab/GitHub

**私钥配置同之前**，但现在即使泄露也只能访问 `/var/ci-workspace/myapp` 目录。

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_HOST: "ci-user@192.168.1.100"

before_script:
  - mkdir -p ~/.ssh
  - cp $SSH_PRIVATE_KEY_MYAPP ~/.ssh/id_ed25519
  - chmod 600 ~/.ssh/id_ed25519
  - ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts

script:
  # 只能同步到 /var/ci-workspace/myapp
  - rsync -avz ./ $REMOTE_CI_HOST:/var/ci-workspace/myapp/
```

##### 5. 撤销密钥

```bash
# 如果密钥泄露，只需删除authorized_keys中的对应行
sudo -u ci-user nano /home/ci-user/.ssh/authorized_keys
# 删除该项目的密钥行

# 无需重启服务，立即生效
```

---

### 方案2：使用上传模式（完全避免SSH）⭐⭐ 最简单

**不需要SSH密钥**，只使用HTTP API和Token。

#### 优势
- ✅ 无需SSH配置
- ✅ 无私钥泄露风险
- ✅ 配置简单
- ✅ 适合大多数场景

#### 劣势
- ❌ 每次都要上传完整代码（但可以压缩）
- ❌ 不能利用增量同步

#### 使用方法

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_API: "http://192.168.1.100:5000"
  # REMOTE_CI_TOKEN 从 CI/CD Variables 注入

remote_build:
  script:
    # 无需SSH配置！
    - bash client/submit-upload.sh "npm install && npm test"
```

**只需配置API Token，无需SSH密钥！**

---

### 方案3：SSH证书认证（企业级）

使用SSH证书而不是密钥对，支持短期证书和集中管理。

#### 优势
- ✅ 证书可以设置过期时间（如1小时）
- ✅ 集中的证书颁发机构（CA）
- ✅ 可以实时撤销
- ✅ 支持细粒度权限

#### 实施步骤

##### 1. 创建CA密钥（在远程CI服务器上）

```bash
# 生成CA密钥（只做一次，妥善保管）
ssh-keygen -t ed25519 -f /etc/ssh/ca_key -C "CI SSH CA"
```

##### 2. 配置sshd接受证书

```bash
# 编辑 /etc/ssh/sshd_config
TrustedUserCAKeys /etc/ssh/ca_key.pub

# 重启sshd
sudo systemctl restart sshd
```

##### 3. 签发短期证书（在CA服务器或脚本中）

```bash
# 生成临时密钥对（在CI任务中动态生成）
ssh-keygen -t ed25519 -f /tmp/temp_key -N ""

# 签发1小时有效的证书
ssh-keygen -s /etc/ssh/ca_key \
  -I "ci-job-12345" \
  -n ci-user \
  -V +1h \
  /tmp/temp_key.pub

# 生成 /tmp/temp_key-cert.pub（1小时后自动失效）
```

##### 4. 在CI中使用证书

```yaml
before_script:
  # 从证书服务获取短期证书
  - curl -X POST https://cert-service/issue -d '{"job_id":"$CI_JOB_ID"}' > cert.tar.gz
  - tar -xzf cert.tar.gz
  - chmod 600 temp_key
  - ssh -i temp_key ci-user@remote-ci "echo OK"

  # 证书1小时后自动失效，无需清理
```

**优势：** 即使证书泄露，1小时后自动失效。

---

### 方案4：专用跳板机（堡垒机）

通过专用的跳板机访问远程CI，隔离风险。

```
公共CI → 跳板机 → 远程CI
         (SSH转发)
```

#### 配置SSH ProxyJump

```bash
# ~/.ssh/config
Host remote-ci-via-bastion
    HostName 192.168.1.100
    User ci-user
    ProxyJump bastion-user@bastion.company.com
    IdentityFile ~/.ssh/bastion_key

# 使用
rsync -avz ./ remote-ci-via-bastion:/var/ci-workspace/myapp/
```

---

## 方案对比

| 方案 | 安全性 | 复杂度 | 速度 | 推荐度 |
|------|--------|--------|------|--------|
| **受限SSH密钥** | ⭐⭐⭐⭐ | 中 | 快 | 🥇 推荐 |
| **上传模式** | ⭐⭐⭐⭐⭐ | 低 | 中 | 🥈 简单 |
| **SSH证书** | ⭐⭐⭐⭐⭐ | 高 | 快 | 企业级 |
| **跳板机** | ⭐⭐⭐⭐ | 高 | 中 | 大型团队 |

---

## 推荐方案选择

### 小团队（10人以下）→ 上传模式

```yaml
# 无需SSH，只用API Token
remote_build:
  script:
    - bash client/submit-upload.sh "npm test"
```

**优势：** 简单、安全、无SSH风险

### 中型团队（频繁构建）→ 受限SSH密钥

```bash
# 每个项目独立密钥 + 目录限制
command="rrsync -wo /var/ci-workspace/myapp" ssh-ed25519 ...
```

**优势：** 快速、受限、可撤销

### 大型团队/企业 → SSH证书

```bash
# 短期证书（1小时有效）
ssh-keygen -s ca_key -V +1h -n ci-user temp_key.pub
```

**优势：** 集中管理、自动过期、细粒度权限

---

## 最佳实践

### 1. 最小权限原则

```bash
# authorized_keys 受限配置
command="rrsync -wo /var/ci-workspace/PROJECT",no-agent-forwarding,no-port-forwarding,no-pty ssh-ed25519 ...
```

### 2. 密钥隔离

```bash
# ✅ 好的做法
project-a → key-a → /var/ci-workspace/project-a/
project-b → key-b → /var/ci-workspace/project-b/

# ❌ 坏的做法
所有项目 → 同一个key → /var/ci-workspace/
```

### 3. 定期轮换

```bash
# 每季度轮换密钥
ssh-keygen -t ed25519 -f new_key
# 更新authorized_keys
# 更新GitLab/GitHub Secrets
# 删除旧密钥
```

### 4. 审计日志

```bash
# 启用SSH日志
# /etc/ssh/sshd_config
LogLevel VERBOSE

# 查看SSH访问日志
sudo tail -f /var/log/auth.log | grep sshd

# 查看rsync日志
sudo journalctl -u rsync -f
```

### 5. 监控异常

```bash
# 监控异常SSH登录
sudo fail2ban-client status sshd

# 监控workspace异常修改
sudo apt-get install inotify-tools
inotifywait -m -r /var/ci-workspace/
```

---

## 安全检查清单

### SSH密钥安全

- [ ] 每个项目使用独立SSH密钥
- [ ] authorized_keys配置了命令限制
- [ ] 禁用了不必要的SSH功能（agent-forwarding等）
- [ ] 私钥在GitLab/GitHub中设置为Masked
- [ ] 私钥文件权限正确（600）
- [ ] 定期审查authorized_keys

### API Token安全

- [ ] Token随机生成（至少32字符）
- [ ] Token在CI系统中设置为Secret/Masked
- [ ] 定期轮换Token（每季度）
- [ ] 限制API访问来源IP（可选）
- [ ] 启用HTTPS（生产环境）

### 网络安全

- [ ] 远程CI服务器防火墙配置正确
- [ ] SSH端口限制访问来源
- [ ] API端口限制访问来源
- [ ] 使用VPN或专用网络（推荐）

### 监控和审计

- [ ] SSH访问日志启用
- [ ] API访问日志启用
- [ ] 异常登录告警
- [ ] 定期审查访问日志

---

## 实际配置示例

### 安全的GitLab CI配置

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_API: "http://192.168.1.100:5000"
  REMOTE_CI_HOST: "ci-user@192.168.1.100"

# 方案1: 上传模式（最安全，推荐）
upload_mode:
  script:
    - bash client/submit-upload.sh "npm test"
  only:
    - main

# 方案2: 受限SSH密钥（频繁构建）
rsync_mode:
  before_script:
    # 使用项目专用的受限密钥
    - mkdir -p ~/.ssh
    - cp $SSH_KEY_MYAPP ~/.ssh/id_ed25519
    - chmod 600 ~/.ssh/id_ed25519
    - ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts
  script:
    # 只能访问指定目录（由authorized_keys限制）
    - bash client/submit-rsync.sh myapp "npm test"
  only:
    - main
```

### 受限authorized_keys配置

```bash
# /home/ci-user/.ssh/authorized_keys

# project-a 的受限密钥（只能写入project-a目录）
command="rrsync -wo /var/ci-workspace/project-a",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxx... project-a-ci-key

# project-b 的受限密钥（只能写入project-b目录）
command="rrsync -wo /var/ci-workspace/project-b",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIyyy... project-b-ci-key
```

---

## 总结

### 我的建议

**对于10人团队，推荐顺序：**

1. **首选：上传模式** - 无SSH风险，配置简单
   ```bash
   bash client/submit-upload.sh "npm test"
   ```

2. **次选：受限SSH密钥** - 如果需要rsync的速度优势
   ```bash
   # 每个项目独立密钥 + rrsync限制
   command="rrsync -wo /path" ssh-ed25519 ...
   ```

3. **不推荐：直接上传完整私钥** - 风险太高

### 安全原则

1. **最小权限** - 密钥只能访问必要的目录
2. **隔离** - 每个项目独立密钥
3. **监控** - 记录所有SSH和API访问
4. **轮换** - 定期更换密钥和Token
5. **审查** - 定期审查配置和日志

**记住：安全 > 便利！**
