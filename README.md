# Remote CI

轻量级远程CI系统，基于Celery + Flask，支持rsync和HTTP上传两种代码传输方式。

**适用场景：** 公共CI有30分钟超时限制，需要独立的构建环境，10人左右团队规模。

## 特性

- ✅ **双模式支持**：rsync同步 / HTTP上传 / Git克隆
- ✅ **并发控制**：Celery队列管理，支持自定义并发数
- ✅ **Web界面**：实时查看任务状态和日志
- ✅ **轻量部署**：纯Python，无需Docker
- ✅ **超时友好**：公共CI 30分钟限制内智能处理
- ✅ **商业友好**：BSD/MIT License

## 📋 目录

- [5分钟快速开始](#5分钟快速开始)
- [模式选择建议](#模式选择建议)
- [详细部署指南](#详细部署指南)
- [安全配置](#安全配置)
- [CI系统集成](#公共ci集成示例)
- [使用说明](#使用说明)
- [故障排查](#故障排查)

---

## 5分钟快速开始

### 步骤1: 部署远程CI服务器（2分钟）

```bash
# 在远程CI服务器上执行
git clone https://github.com/your-org/remoteCI.git
cd remoteCI

# 一键安装（自动安装依赖、创建用户、配置服务）
sudo bash deploy/install-server.sh

# 启动服务
sudo systemctl start redis remote-ci-api remote-ci-worker

# ⚠️ 记录安装输出的API Token！
```

### 步骤2: 测试验证（1分钟）

```bash
# 在远程CI服务器上测试
export REMOTE_CI_API="http://localhost:5000"
export REMOTE_CI_TOKEN="$(grep CI_API_TOKEN /opt/remote-ci/.env | cut -d'=' -f2)"

# 运行测试脚本
bash examples/test-scripts/test-upload-mode.sh
```

### 步骤3: 配置公共CI（2分钟）

#### 推荐：上传模式（无需SSH，更安全）

**GitLab CI：**
1. 项目 → Settings → CI/CD → Variables
2. 添加 `REMOTE_CI_TOKEN`（Masked）
3. 添加 `.gitlab-ci.yml`：

```yaml
remote_build:
  stage: build
  timeout: 30m
  variables:
    REMOTE_CI_API: "http://your-server:5000"
  script:
    - curl -O https://raw.githubusercontent.com/your-org/remoteCI/main/client/submit-upload.sh
    - bash submit-upload.sh "npm install && npm test"
```

**GitHub Actions：**
1. 仓库 → Settings → Secrets → New secret
2. 添加 `REMOTE_CI_TOKEN` 和 `REMOTE_CI_API`
3. 创建 `.github/workflows/ci.yml`：

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - name: Submit to Remote CI
        env:
          REMOTE_CI_API: ${{ secrets.REMOTE_CI_API }}
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: |
          curl -O https://raw.githubusercontent.com/your-org/remoteCI/main/client/submit-upload.sh
          bash submit-upload.sh "npm install && npm test"
```

✅ **完成！现在你的CI任务会在远程服务器执行，不受30分钟限制。**

---

## 模式选择建议

### 🎯 快速决策

| 你的情况 | 推荐模式 | 理由 |
|---------|---------|------|
| **项目<10MB，安全优先** | **上传模式** ⭐⭐⭐ | 无SSH风险，速度差距小（1-3秒） |
| **项目<50MB，每天<10次构建** | **上传模式** ⭐⭐⭐ | 简单安全，性能足够 |
| **项目>50MB，频繁构建** | **rsync模式** ⭐⭐ | 增量同步快，但需配置SSH |
| **无SSH权限** | **上传模式** ⭐⭐⭐ | 唯一选择 |

### 📊 性能对比（10MB项目）

| 场景 | rsync | 上传模式 | 差距 |
|------|-------|---------|------|
| **首次构建** | 2.5秒 | 2.3秒 | 0.2秒（可忽略） |
| **后续构建** | 0.8秒 | 2.1秒 | 1.3秒 |
| **总构建时间** | 60秒 | 61秒 | 1.6%（很小） |

**结论：** 10MB以内项目，上传模式的速度劣势可忽略，但安全性高很多！

### 🔒 安全对比

| 维度 | 上传模式 | rsync模式 |
|------|---------|-----------|
| **需要上传私钥** | ❌ 不需要 | ✅ 需要 |
| **私钥泄露风险** | ✅ 无风险 | ⚠️ 有风险 |
| **配置复杂度** | ✅ 简单 | ⚠️ 复杂 |
| **推荐度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

**建议：** 除非项目很大（>50MB）且构建频繁，否则推荐上传模式。

---

## 详细部署指南

### 前置要求

- Linux服务器（Ubuntu 20.04+ / CentOS 7+）
- Python 3.8+
- 2GB+ 内存
- sudo权限

### 一键安装

```bash
# 1. 克隆项目
git clone https://github.com/your-org/remoteCI.git
cd remoteCI

# 2. 运行安装脚本
sudo bash deploy/install-server.sh
```

**安装脚本会自动：**
- ✅ 安装Python、Redis、Git等依赖
- ✅ 创建`ci-user`用户
- ✅ 创建目录结构
- ✅ 安装Python依赖
- ✅ 生成随机API Token
- ✅ 配置systemd服务

### 手动安装步骤

<details>
<summary>点击展开手动安装步骤</summary>

```bash
# 1. 安装系统依赖
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv redis-server git rsync

# 2. 创建用户
sudo useradd -r -m -s /bin/bash ci-user

# 3. 创建目录
sudo mkdir -p /opt/remote-ci
sudo mkdir -p /var/lib/remote-ci/{logs,uploads}
sudo mkdir -p /var/ci-workspace
sudo mkdir -p /var/log/remote-ci

# 4. 复制项目文件
sudo cp -r server requirements.txt .env.example /opt/remote-ci/
cd /opt/remote-ci

# 5. 安装Python依赖
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

# 6. 配置环境变量
sudo cp .env.example .env
sudo sed -i "s/your-secret-token-here/$(openssl rand -hex 32)/" .env

# 7. 设置权限
sudo chown -R ci-user:ci-user /opt/remote-ci
sudo chown -R ci-user:ci-user /var/lib/remote-ci
sudo chown -R ci-user:ci-user /var/ci-workspace

# 8. 创建systemd服务
# （参考 deploy/install-server.sh 中的服务配置）

# 9. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable redis remote-ci-api remote-ci-worker
sudo systemctl start redis remote-ci-api remote-ci-worker
```

</details>

### 验证安装

```bash
# 1. 检查服务状态
sudo systemctl status remote-ci-api
sudo systemctl status remote-ci-worker
sudo systemctl status redis

# 2. 测试API
curl http://localhost:5000/api/health

# 3. 查看Token
grep CI_API_TOKEN /opt/remote-ci/.env

# 4. 访问Web界面
# 浏览器打开: http://your-server-ip:5000
```

---

## 安全配置

### Token配置

#### 1. 获取API Token

```bash
# 在远程CI服务器上查看
grep CI_API_TOKEN /opt/remote-ci/.env

# 输出示例：
# CI_API_TOKEN=8f3a9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

#### 2. 配置到公共CI

**GitLab CI：**
```
项目 → Settings → CI/CD → Variables
添加：REMOTE_CI_TOKEN
值：（粘贴Token）
选项：✅ Masked
```

**GitHub Actions：**
```
仓库 → Settings → Secrets and variables → Actions
添加：REMOTE_CI_TOKEN
值：（粘贴Token）
```

**Jenkins：**
```
Manage Jenkins → Credentials → Add Credentials
Kind: Secret text
Secret: （粘贴Token）
ID: remote-ci-token
```

### SSH配置（仅rsync模式需要）

⚠️ **安全警告：** 上传SSH私钥到GitLab/GitHub存在安全风险！

#### 推荐方案：使用上传模式（无需SSH）

```yaml
# .gitlab-ci.yml - 无需SSH配置
remote_build:
  script:
    - bash client/submit-upload.sh "npm test"
```

#### 如果必须使用rsync：配置受限SSH密钥

<details>
<summary>点击展开安全的SSH配置方法</summary>

**1. 为每个项目创建专用密钥：**

```bash
# 在远程CI服务器上
sudo -u ci-user ssh-keygen -t ed25519 \
  -f /home/ci-user/.ssh/project_myapp_key \
  -C "CI key for myapp" -N ""
```

**2. 配置受限的authorized_keys：**

```bash
# 编辑 /home/ci-user/.ssh/authorized_keys
# 添加（单行）：
command="rrsync -wo /var/ci-workspace/myapp",no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwarding ssh-ed25519 AAAAC3... CI key for myapp
```

**限制说明：**
- ✅ 这个密钥**只能**rsync到指定目录
- ✅ **不能**执行其他命令
- ✅ **不能**SSH登录
- ✅ 即使泄露，影响范围有限

**3. 配置到GitLab/GitHub：**

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
  - bash client/submit-rsync.sh myapp "npm test"
```

</details>

### 安全最佳实践

1. **使用上传模式** - 避免SSH私钥风险
   ```bash
   # ✅ 推荐
   bash client/submit-upload.sh "npm test"
   ```

2. **启用HTTPS**（生产环境必须）
   ```bash
   # 使用nginx反向代理
   sudo apt-get install nginx certbot python3-certbot-nginx
   sudo certbot --nginx -d ci.yourcompany.com
   ```

3. **定期轮换Token**
   ```bash
   # 每季度更换
   NEW_TOKEN=$(openssl rand -hex 32)
   sudo sed -i "s/CI_API_TOKEN=.*/CI_API_TOKEN=$NEW_TOKEN/" /opt/remote-ci/.env
   sudo systemctl restart remote-ci-api
   ```

4. **限制网络访问**
   ```bash
   # 防火墙规则
   sudo ufw allow from 192.168.1.0/24 to any port 5000
   sudo ufw enable
   ```

5. **监控审计日志**
   ```bash
   # 查看API访问
   tail -f /var/log/remote-ci/api.log

   # 查看SSH访问
   sudo tail -f /var/log/auth.log | grep sshd
   ```

### 安全检查清单

- [ ] API Token设置为Masked/Secret
- [ ] Token随机生成（至少32字符）
- [ ] 生产环境启用HTTPS
- [ ] 限制防火墙访问
- [ ] 定期审查日志
- [ ] 定期轮换Token（每季度）
- [ ] 如使用SSH：配置受限密钥
- [ ] 如使用SSH：每个项目独立密钥

## 使用说明

### rsync模式（最快）

适合频繁构建，增量同步速度快。

```bash
# 同步代码到远程workspace
rsync -avz ./ ci-user@remote-ci:/var/ci-workspace/myproject/

# 触发构建
curl -X POST http://remote-ci:5000/api/jobs/rsync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "/var/ci-workspace/myproject",
    "script": "npm install && npm test"
  }'
```

### 上传模式

适合无SSH访问或一次性构建。

#### 基础用法

```bash
# 上传整个项目（自动排除常见临时文件）
bash client/submit-upload.sh "npm install && npm test"

# 或手动打包上传
tar -czf code.tar.gz --exclude='.git' --exclude='node_modules' .
curl -X POST http://remote-ci:5000/api/jobs/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "code=@code.tar.gz" \
  -F "script=npm install && npm test"
```

#### 选择性上传目录 ⭐

只上传必要的代码，减少传输时间：

```bash
# 只上传src和tests目录
bash client/submit-upload.sh "npm test" "src/ tests/"

# 只上传特定文件和目录
bash client/submit-upload-custom.sh "npm test" "package.json src/ Dockerfile" ""

# 上传时排除额外的文件
bash client/submit-upload-custom.sh "npm test" "." "*.log,*.tmp,cache/"
```

**使用场景：**
- ✅ 大型Monorepo，只需构建部分模块
- ✅ 只需要源码，不需要文档和示例
- ✅ 减少上传时间（只传必要文件）

**示例：**

```bash
# 前端项目：只上传src和配置文件
bash client/submit-upload-custom.sh \
  "npm run build" \
  "src/ package.json package-lock.json tsconfig.json" \
  ""

# Python项目：只上传源码和依赖
bash client/submit-upload-custom.sh \
  "pytest" \
  "src/ tests/ requirements.txt setup.py" \
  "*.pyc,__pycache__"

# Monorepo：只上传单个包
bash client/submit-upload.sh \
  "cd packages/api && npm test" \
  "packages/api/"
```

### Git模式

远程CI直接克隆仓库（需要Git访问权限）。

```bash
curl -X POST http://remote-ci:5000/api/jobs/git \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "repo": "https://github.com/user/repo.git",
    "branch": "main",
    "script": "npm install && npm test"
  }'
```

### 查询任务状态

```bash
# 获取任务状态
curl http://remote-ci:5000/api/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"

# 获取任务日志
curl http://remote-ci:5000/api/jobs/{job_id}/logs \
  -H "Authorization: Bearer $TOKEN"
```

## 公共CI集成示例

### GitLab CI

```yaml
# .gitlab-ci.yml
remote_build:
  stage: build
  script:
    - bash client/submit-rsync.sh $CI_PROJECT_NAME "npm test"
  timeout: 30m
```

### GitHub Actions

```yaml
# .github/workflows/build.yml
jobs:
  remote-build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - name: Submit to Remote CI
        env:
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: bash client/submit-upload.sh "npm test"
```

### Jenkins

```groovy
pipeline {
    agent any
    options {
        timeout(time: 30, unit: 'MINUTES')
    }
    stages {
        stage('Remote Build') {
            steps {
                sh 'bash client/submit-rsync.sh ${JOB_NAME} "npm test"'
            }
        }
    }
}
```

## 架构说明

```
┌─────────────────┐         ┌──────────────────────────────┐
│   公共CI        │         │     远程CI服务器              │
│  (30分钟限制)   │         │                               │
│                 │         │  ┌─────────────────────────┐  │
│  1. rsync同步   │────────▶│  │ Flask API (5000)        │  │
│     或上传代码  │         │  └──────────┬──────────────┘  │
│                 │         │             │                 │
│  2. 提交任务    │────────▶│  ┌──────────▼──────────────┐  │
│                 │         │  │ Redis (任务队列)        │  │
│  3. 轮询状态    │◀────────│  └──────────┬──────────────┘  │
│     (最多25分钟)│         │             │                 │
│                 │         │  ┌──────────▼──────────────┐  │
│  4. 获取结果    │◀────────│  │ Celery Worker (执行)    │  │
│                 │         │  │  - 并发控制              │  │
│                 │         │  │  - 超时处理              │  │
└─────────────────┘         │  │  - 日志记录              │  │
                            │  └─────────────────────────┘  │
                            │                               │
                            │  /var/ci-workspace/          │
                            │  (rsync同步目录)              │
                            └──────────────────────────────┘
```

## 配置说明

### 服务器配置 (.env)

```bash
# API配置
CI_API_HOST=0.0.0.0
CI_API_PORT=5000
CI_API_TOKEN=your-secret-token

# Redis配置
CI_BROKER_URL=redis://localhost:6379/0
CI_RESULT_BACKEND=redis://localhost:6379/0

# 任务配置
CI_MAX_CONCURRENT=2        # 最大并发任务数
CI_JOB_TIMEOUT=3600        # 任务超时（秒）
CI_LOG_RETENTION_DAYS=7    # 日志保留天数

# 目录配置
CI_DATA_DIR=./data
CI_WORK_DIR=/tmp/remote-ci
CI_WORKSPACE_DIR=/var/ci-workspace
```

### 客户端配置 (config.sh)

```bash
REMOTE_CI_HOST="ci-user@192.168.1.100"
REMOTE_CI_API="http://192.168.1.100:5000"
REMOTE_CI_TOKEN="your-secret-token"
WORKSPACE_BASE="/var/ci-workspace"
CI_TIMEOUT=1500  # 25分钟
```

## 监控和维护

### 查看服务日志

```bash
# API日志
tail -f /var/log/remote-ci/api.log

# Worker日志
tail -f /var/log/remote-ci/worker.log

# 系统服务状态
sudo systemctl status remote-ci-api
sudo systemctl status remote-ci-worker
```

### Flower监控界面

```bash
# 启动Flower
sudo systemctl start remote-ci-flower

# 访问 http://remote-ci-server:5555
```

### 清理旧日志

```bash
# 自动清理（配置在.env中）
CI_LOG_RETENTION_DAYS=7

# 手动清理
find /var/lib/remote-ci/logs -mtime +7 -delete
```

## 性能优化

### rsync优化

```bash
# 使用压缩
rsync -avz

# 排除大文件
rsync -avz --exclude='*.mp4' --exclude='*.iso'

# 限速避免占满带宽
rsync -avz --bwlimit=5000  # 5MB/s
```

### 并发调整

```bash
# 修改.env
CI_MAX_CONCURRENT=3  # 根据服务器资源调整

# 重启worker
sudo systemctl restart remote-ci-worker
```

## 故障排查

### 问题1: 任务一直排队

```bash
# 检查worker是否运行
sudo systemctl status remote-ci-worker

# 查看worker日志
tail -f /var/log/remote-ci/worker.log

# 重启worker
sudo systemctl restart remote-ci-worker
```

### 问题2: Redis连接失败

```bash
# 检查Redis状态
sudo systemctl status redis

# 测试连接
redis-cli ping

# 检查配置
grep BROKER_URL /opt/remote-ci/.env
```

### 问题3: rsync权限问题

```bash
# 检查workspace权限
ls -la /var/ci-workspace/

# 修复权限
sudo chown -R ci-user:ci-user /var/ci-workspace/
```

---

## 常见问题 FAQ

### Q1: 上传模式和rsync模式到底选哪个？

**A:** 对于10MB以内的项目，强烈推荐**上传模式**：
- ✅ 安全（无SSH私钥风险）
- ✅ 简单（无需配置SSH）
- ✅ 速度差距可忽略（仅1-3秒）
- ✅ 支持选择性上传目录

只有当项目>50MB且构建频繁时，才考虑rsync。

### Q7: 如何只上传部分代码？

**A:** 使用自定义上传脚本：

```bash
# 只上传src目录
bash client/submit-upload.sh "npm test" "src/"

# 只上传多个目录
bash client/submit-upload.sh "npm test" "src/ tests/"

# 使用自定义排除
bash client/submit-upload-custom.sh "npm test" "." "*.log,cache/"
```

**典型场景：**
- Monorepo项目只构建一个包
- 大型项目只需要源码（排除文档、示例）
- 减少传输时间

### Q2: 公共CI超时后，远程CI还会继续执行吗？

**A:** 会的！这正是本系统的设计目标：
- 公共CI在25分钟后退出（避免超时）
- 远程CI继续执行（最长支持1小时）
- 通过Web界面查看最终结果

### Q3: 如何保证安全？

**A:** 多层安全措施：
1. API Token认证（存储在CI系统的Secret中）
2. 生产环境启用HTTPS
3. 防火墙限制访问来源
4. 如使用rsync：配置受限SSH密钥
5. 定期轮换Token和密钥

### Q4: 支持多少并发任务？

**A:** 默认2个并发，可配置：
```bash
# 修改 /opt/remote-ci/.env
CI_MAX_CONCURRENT=3

# 重启worker
sudo systemctl restart remote-ci-worker
```

### Q5: 如何查看任务执行日志？

**A:** 三种方式：
1. Web界面：http://your-server:5000
2. API查询：`curl http://server:5000/api/jobs/{job_id}/logs`
3. 服务器文件：`/var/lib/remote-ci/logs/{job_id}.log`

### Q6: 任务执行失败怎么办？

**A:** 检查步骤：
```bash
# 1. 查看任务日志
curl http://server:5000/api/jobs/{job_id}/logs

# 2. 检查Worker状态
sudo systemctl status remote-ci-worker

# 3. 查看Worker日志
tail -f /var/log/remote-ci/worker.log

# 4. 检查Redis
redis-cli ping
```

---

## 性能优化

### 提升构建速度

1. **优化传输大小**
   ```bash
   # rsync模式：排除不必要的文件
   rsync --exclude='node_modules' --exclude='.git' --exclude='dist'

   # 上传模式：打包时排除
   tar --exclude='node_modules' -czf code.tar.gz .
   ```

2. **利用缓存**（rsync模式）
   ```bash
   # workspace保留依赖，增量安装
   /var/ci-workspace/myapp/node_modules  # 保留
   npm install  # 只安装新增依赖
   ```

3. **调整并发数**
   ```bash
   # 根据服务器资源调整
   CI_MAX_CONCURRENT=3  # 4核CPU可设为3-4
   ```

4. **使用本地缓存镜像**
   ```bash
   # npm淘宝镜像
   npm config set registry https://registry.npmmirror.com

   # pip清华镜像
   pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
   ```

---

## 维护和监控

### 日常维护

```bash
# 查看服务状态
sudo systemctl status remote-ci-api remote-ci-worker

# 重启服务
sudo systemctl restart remote-ci-api remote-ci-worker

# 查看日志
tail -f /var/log/remote-ci/api.log
tail -f /var/log/remote-ci/worker.log

# 清理旧日志（7天前）
find /var/lib/remote-ci/logs -mtime +7 -delete
```

### Flower监控（可选）

```bash
# 启动Flower监控界面
sudo systemctl start remote-ci-flower

# 访问 http://your-server:5555
# 可查看：
# - 实时任务列表
# - Worker状态
# - 任务执行时间统计
# - 失败任务追踪
```

### 备份

```bash
# 备份配置
tar -czf remote-ci-backup.tar.gz \
  /opt/remote-ci/.env \
  /var/ci-workspace/

# 定期备份（crontab）
0 2 * * 0 tar -czf /backup/remote-ci-$(date +\%Y\%m\%d).tar.gz /opt/remote-ci/.env /var/ci-workspace/
```

---

## 技术栈

- **后端**: Python 3.8+
- **Web框架**: Flask 3.0
- **任务队列**: Celery 5.3 + Redis
- **监控**: Flower 2.0
- **License**: BSD 3-Clause

## 项目结构

```
remoteCI/
├── client/              # 公共CI端脚本
│   ├── submit-rsync.sh   # rsync模式提交脚本
│   └── submit-upload.sh  # 上传模式提交脚本
├── server/              # 远程CI服务端
│   ├── app.py           # Flask API服务
│   ├── tasks.py         # Celery任务定义
│   └── config.py        # 配置管理
├── deploy/              # 部署脚本
│   └── install-server.sh # 一键安装脚本
├── examples/            # 示例和用例
│   ├── test-scripts/    # 测试脚本
│   └── use-cases/       # 10个实际用例
└── docs/                # 详细文档
```

## 更多资源

- 📚 [架构设计文档](docs/ARCHITECTURE.md) - 系统架构和技术细节
- 🔐 [安全配置指南](docs/SECURE_SSH_SETUP.md) - 详细的安全配置
- 🎯 [使用用例](examples/use-cases/README.md) - 10个实际场景
- 📦 [选择性上传](examples/selective-upload/README.md) - 只上传必要代码
- 🧪 [测试脚本](examples/test-scripts/) - 验证部署

## 贡献

欢迎提交Issue和Pull Request！

## License

BSD 3-Clause License - 商业友好，可自由用于商业项目

## 致谢

感谢以下开源项目：
- Flask - Web框架
- Celery - 分布式任务队列
- Redis - 内存数据库
- Flower - Celery监控工具

## 联系方式

- Issues: https://github.com/your-org/remoteCI/issues
- Discussions: https://github.com/your-org/remoteCI/discussions
- Email: dev@your-company.com

---

**⭐ 如果这个项目对你有帮助，请给个Star！**