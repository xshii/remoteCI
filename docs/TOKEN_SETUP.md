# Token和SSH密钥配置指南

## 概述

rsync模式需要配置两种认证：

| 认证类型 | 用途 | 配置位置 |
|---------|------|---------|
| **API Token** | 调用远程CI的HTTP API | 公共CI环境变量 |
| **SSH密钥** | rsync同步代码 | 公共CI和远程CI |

---

## 第一部分：API Token配置

### 1. 在远程CI服务器上生成Token

#### 方法A：查看安装时生成的Token

```bash
# 在远程CI服务器上
grep CI_API_TOKEN /opt/remote-ci/.env
```

输出示例：
```
CI_API_TOKEN=8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

#### 方法B：生成新Token

```bash
# 生成随机token（64字符）
openssl rand -hex 32

# 输出示例
8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

#### 方法C：自定义Token

```bash
# 编辑配置文件
sudo nano /opt/remote-ci/.env

# 修改这一行（建议至少32字符）
CI_API_TOKEN=your-custom-token-here

# 保存并重启服务
sudo systemctl restart remote-ci-api
```

### 2. 在公共CI上配置Token

#### GitLab CI

**步骤：**
1. 进入项目 → Settings → CI/CD → Variables
2. 点击 "Add Variable"
3. 配置：
   - Key: `REMOTE_CI_TOKEN`
   - Value: `8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0`
   - Type: Variable
   - ✅ Masked (隐藏日志中的token)
   - ✅ Protected (仅保护分支可用，可选)

**使用：**
```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_API: "http://192.168.1.100:5000"
  # REMOTE_CI_TOKEN 从 CI/CD Variables 自动注入

remote_build:
  script:
    - bash client/submit-rsync.sh my-project "npm test"
```

#### GitHub Actions

**步骤：**
1. 进入仓库 → Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 配置：
   - Name: `REMOTE_CI_TOKEN`
   - Secret: `8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0`

**使用：**
```yaml
# .github/workflows/ci.yml
jobs:
  build:
    steps:
      - name: Submit to Remote CI
        env:
          REMOTE_CI_API: "http://192.168.1.100:5000"
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: |
          bash client/submit-rsync.sh my-project "npm test"
```

#### Jenkins

**步骤：**
1. Jenkins → Manage Jenkins → Manage Credentials
2. 选择合适的域 → Add Credentials
3. 配置：
   - Kind: Secret text
   - Scope: Global
   - Secret: `8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0`
   - ID: `remote-ci-token`
   - Description: Remote CI API Token

**使用：**
```groovy
// Jenkinsfile
pipeline {
    environment {
        REMOTE_CI_API = 'http://192.168.1.100:5000'
        REMOTE_CI_TOKEN = credentials('remote-ci-token')
    }
    stages {
        stage('Build') {
            steps {
                sh 'bash client/submit-rsync.sh my-project "npm test"'
            }
        }
    }
}
```

#### 本地开发/测试

```bash
# 方法1：环境变量
export REMOTE_CI_TOKEN="8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0"

# 方法2：配置文件
cp client/config.sh.example client/config.sh
nano client/config.sh

# 添加
export REMOTE_CI_TOKEN="your-token-here"

# 使用
source client/config.sh
bash client/submit-rsync.sh my-project "npm test"
```

---

## 第二部分：SSH密钥配置（rsync专用）

### 1. 在公共CI服务器上生成SSH密钥

```bash
# 生成SSH密钥对
ssh-keygen -t ed25519 -C "gitlab-ci@company.com" -f ~/.ssh/remote_ci_key -N ""

# 参数说明：
# -t ed25519: 使用Ed25519算法（推荐，比RSA更安全更快）
# -C: 注释
# -f: 输出文件路径
# -N "": 无密码（CI环境必须）

# 生成两个文件：
# ~/.ssh/remote_ci_key       (私钥)
# ~/.ssh/remote_ci_key.pub   (公钥)
```

### 2. 复制公钥到远程CI服务器

```bash
# 方法1：使用ssh-copy-id（推荐）
ssh-copy-id -i ~/.ssh/remote_ci_key.pub ci-user@192.168.1.100

# 方法2：手动复制
cat ~/.ssh/remote_ci_key.pub

# 在远程CI服务器上
mkdir -p /home/ci-user/.ssh
nano /home/ci-user/.ssh/authorized_keys
# 粘贴公钥内容，保存

# 设置权限
chmod 700 /home/ci-user/.ssh
chmod 600 /home/ci-user/.ssh/authorized_keys
chown -R ci-user:ci-user /home/ci-user/.ssh
```

### 3. 测试SSH连接

```bash
# 从公共CI服务器测试
ssh -i ~/.ssh/remote_ci_key ci-user@192.168.1.100 "echo 'SSH连接成功'"

# 如果成功，输出：SSH连接成功
```

### 4. 在公共CI系统中配置SSH密钥

#### GitLab CI

**步骤：**
1. 复制私钥内容：
   ```bash
   cat ~/.ssh/remote_ci_key
   ```

2. GitLab项目 → Settings → CI/CD → Variables
3. 添加变量：
   - Key: `SSH_PRIVATE_KEY`
   - Value: (粘贴私钥完整内容，包括`-----BEGIN...`和`-----END...`)
   - Type: File (重要！)
   - ✅ Masked

**使用：**
```yaml
# .gitlab-ci.yml
remote_build:
  before_script:
    # 配置SSH
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - cp $SSH_PRIVATE_KEY ~/.ssh/id_ed25519
    - chmod 600 ~/.ssh/id_ed25519
    - ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts
  script:
    - bash client/submit-rsync.sh my-project "npm test"
```

#### GitHub Actions

**步骤：**
1. 复制私钥内容：
   ```bash
   cat ~/.ssh/remote_ci_key
   ```

2. GitHub仓库 → Settings → Secrets → New repository secret
3. 配置：
   - Name: `SSH_PRIVATE_KEY`
   - Secret: (粘贴私钥完整内容)

**使用：**
```yaml
# .github/workflows/ci.yml
jobs:
  build:
    steps:
      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts

      - name: Submit to Remote CI
        run: |
          bash client/submit-rsync.sh my-project "npm test"
```

#### Jenkins

**方法1：使用SSH Agent插件（推荐）**

1. Jenkins → Manage Credentials → Add Credentials
2. 配置：
   - Kind: SSH Username with private key
   - ID: `remote-ci-ssh`
   - Username: `ci-user`
   - Private Key: Enter directly (粘贴私钥)

```groovy
// Jenkinsfile
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sshagent(['remote-ci-ssh']) {
                    sh 'bash client/submit-rsync.sh my-project "npm test"'
                }
            }
        }
    }
}
```

**方法2：使用Secret File**

同GitLab的方式，将私钥存为Secret File。

---

## 完整配置示例

### GitLab CI 完整配置

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_HOST: "ci-user@192.168.1.100"
  REMOTE_CI_API: "http://192.168.1.100:5000"
  # 以下变量在 CI/CD Settings -> Variables 中配置：
  # - REMOTE_CI_TOKEN (Variable, Masked)
  # - SSH_PRIVATE_KEY (File, Masked)

remote_build:
  stage: build
  timeout: 30m

  before_script:
    # 配置SSH密钥
    - mkdir -p ~/.ssh
    - chmod 700 ~/.ssh
    - cp $SSH_PRIVATE_KEY ~/.ssh/id_ed25519
    - chmod 600 ~/.ssh/id_ed25519
    - ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts

  script:
    # 提交远程构建
    - |
      export REMOTE_CI_HOST="$REMOTE_CI_HOST"
      export REMOTE_CI_API="$REMOTE_CI_API"
      export REMOTE_CI_TOKEN="$REMOTE_CI_TOKEN"

      bash client/submit-rsync.sh $CI_PROJECT_NAME "npm install && npm test"

  only:
    - main
```

### GitHub Actions 完整配置

```yaml
# .github/workflows/ci.yml
name: Remote CI Build

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v3

      - name: Setup SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_ed25519
          chmod 600 ~/.ssh/id_ed25519
          ssh-keyscan -H ${{ secrets.REMOTE_CI_HOST }} >> ~/.ssh/known_hosts

      - name: Submit to Remote CI
        env:
          REMOTE_CI_HOST: ${{ secrets.REMOTE_CI_HOST }}
          REMOTE_CI_API: ${{ secrets.REMOTE_CI_API }}
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: |
          bash client/submit-rsync.sh my-project "npm install && npm test"
```

**需要配置的Secrets：**
- `SSH_PRIVATE_KEY` - SSH私钥
- `REMOTE_CI_HOST` - `ci-user@192.168.1.100`
- `REMOTE_CI_API` - `http://192.168.1.100:5000`
- `REMOTE_CI_TOKEN` - API Token

---

## 安全最佳实践

### 1. Token安全

```bash
# ✅ 好的做法
- 使用CI/CD系统的密钥管理
- 启用Masked（隐藏日志输出）
- 定期轮换token
- 使用随机生成的强token（至少32字符）

# ❌ 坏的做法
- 不要在代码中硬编码token
- 不要提交token到Git仓库
- 不要在脚本中echo $REMOTE_CI_TOKEN
```

### 2. SSH密钥安全

```bash
# ✅ 好的做法
- 使用ed25519算法（比RSA更安全）
- SSH密钥不设置密码（CI环境）
- 限制密钥权限（chmod 600）
- 每个项目使用独立的SSH密钥
- 定期轮换密钥

# ❌ 坏的做法
- 不要共享私钥
- 不要提交私钥到Git仓库
- 不要使用弱加密算法（如RSA 1024位）
```

### 3. 远程CI服务器安全

```bash
# 限制SSH访问
# /etc/ssh/sshd_config
AllowUsers ci-user@192.168.1.0/24  # 只允许内网访问

# 或使用专用密钥
AuthorizedKeysFile /home/ci-user/.ssh/authorized_keys_ci

# 禁用密码登录
PasswordAuthentication no
```

### 4. Token轮换

```bash
# 定期更换token（建议每季度）

# 1. 生成新token
NEW_TOKEN=$(openssl rand -hex 32)

# 2. 更新远程CI配置
sudo sed -i "s/CI_API_TOKEN=.*/CI_API_TOKEN=$NEW_TOKEN/" /opt/remote-ci/.env
sudo systemctl restart remote-ci-api

# 3. 更新公共CI的密钥管理系统中的token

# 4. 验证
curl http://remote-ci:5000/api/health \
  -H "Authorization: Bearer $NEW_TOKEN"
```

---

## 故障排查

### 问题1: API认证失败

```bash
# 症状
{"error": "Unauthorized"}

# 排查步骤
# 1. 检查远程CI的token
ssh ci-user@remote-ci "grep CI_API_TOKEN /opt/remote-ci/.env"

# 2. 测试API
curl http://remote-ci:5000/api/health \
  -H "Authorization: Bearer $REMOTE_CI_TOKEN"

# 3. 检查公共CI的环境变量
echo "Token前5个字符: ${REMOTE_CI_TOKEN:0:5}"
```

### 问题2: SSH连接失败

```bash
# 症状
Permission denied (publickey)

# 排查步骤
# 1. 测试SSH连接
ssh -vvv ci-user@remote-ci

# 2. 检查远程CI的authorized_keys
ssh ci-user@remote-ci "cat ~/.ssh/authorized_keys"

# 3. 检查权限
ssh ci-user@remote-ci "ls -la ~/.ssh"
# 应该是：
# drwx------ .ssh/
# -rw------- authorized_keys

# 4. 检查公共CI的私钥
ls -la ~/.ssh/id_ed25519
# 应该是：-rw------- id_ed25519
```

### 问题3: rsync同步失败

```bash
# 症状
rsync: connection unexpectedly closed

# 排查步骤
# 1. 测试SSH
ssh ci-user@remote-ci "echo test"

# 2. 测试rsync
rsync -avz --dry-run ./ ci-user@remote-ci:/var/ci-workspace/test/

# 3. 检查远程目录权限
ssh ci-user@remote-ci "ls -la /var/ci-workspace"
# 应该是 ci-user:ci-user
```

---

## 快速检查清单

部署前的检查清单：

### 远程CI服务器
- [ ] API服务运行中 (`systemctl status remote-ci-api`)
- [ ] Worker运行中 (`systemctl status remote-ci-worker`)
- [ ] Redis运行中 (`systemctl status redis`)
- [ ] API Token已生成 (`grep CI_API_TOKEN /opt/remote-ci/.env`)
- [ ] ci-user用户存在
- [ ] workspace目录存在且权限正确 (`/var/ci-workspace`)

### 公共CI配置
- [ ] API Token已配置到密钥管理系统
- [ ] SSH私钥已配置到密钥管理系统
- [ ] SSH公钥已添加到远程CI的authorized_keys
- [ ] 环境变量配置正确（REMOTE_CI_HOST, REMOTE_CI_API）

### 连接测试
- [ ] API健康检查通过 (`curl http://remote-ci:5000/api/health`)
- [ ] API认证通过 (`curl -H "Authorization: Bearer $TOKEN" ...`)
- [ ] SSH连接通过 (`ssh ci-user@remote-ci "echo OK"`)
- [ ] rsync测试通过 (`rsync --dry-run ...`)

---

## 相关文档

- [快速开始](./QUICKSTART.md)
- [架构设计](./ARCHITECTURE.md)
- [示例配置](../examples/README.md)
