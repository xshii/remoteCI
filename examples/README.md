# 示例和用例

本目录包含各种实际使用场景的示例。

## 目录结构

```
examples/
├── nodejs-project/          # Node.js项目示例
│   └── .gitlab-ci.yml      # GitLab CI配置
├── python-project/          # Python项目示例
│   └── .github/            # GitHub Actions配置
├── jenkins-pipeline/        # Jenkins示例
│   └── Jenkinsfile         # Pipeline配置
├── test-scripts/            # 测试脚本
│   ├── test-rsync-mode.sh  # rsync模式测试
│   └── test-upload-mode.sh # 上传模式测试
└── use-cases/               # 详细用例说明
    └── README.md
```

## 快速测试

### 测试rsync模式

```bash
# 配置环境变量
export REMOTE_CI_HOST="ci-user@your-server"
export REMOTE_CI_API="http://your-server:5000"
export REMOTE_CI_TOKEN="your-token"

# 运行测试
bash examples/test-scripts/test-rsync-mode.sh
```

### 测试上传模式

```bash
# 配置环境变量
export REMOTE_CI_API="http://your-server:5000"
export REMOTE_CI_TOKEN="your-token"

# 运行测试
bash examples/test-scripts/test-upload-mode.sh
```

## 使用场景

详细的使用场景说明请查看：[use-cases/README.md](use-cases/README.md)

包括：
- ✅ 前端E2E测试
- ✅ 机器学习模型训练
- ✅ Android APK构建
- ✅ 微服务集成测试
- ✅ 数据库迁移测试
- ✅ Monorepo构建
- ✅ 多平台交叉编译
- ✅ 性能测试
- ✅ 安全扫描
- ✅ 更多...

## CI系统集成

### GitLab CI

查看示例：[nodejs-project/.gitlab-ci.yml](nodejs-project/.gitlab-ci.yml)

关键点：
- 配置SSH密钥
- 使用GitLab Variables存储Token
- 设置30分钟超时

### GitHub Actions

查看示例：[python-project/.github/workflows/ci.yml](python-project/.github/workflows/ci.yml)

关键点：
- 使用GitHub Secrets存储Token
- 通过actions/checkout获取代码
- 设置timeout-minutes

### Jenkins

查看示例：[jenkins-pipeline/Jenkinsfile](jenkins-pipeline/Jenkinsfile)

关键点：
- 使用Jenkins Credentials存储Token
- Pipeline脚本化配置
- 环境变量管理

## 最佳实践

### 1. 选择合适的模式

**使用rsync模式：**
- ✅ 频繁构建（每天多次）
- ✅ 有SSH访问权限
- ✅ 项目有大量依赖（node_modules、.gradle等）
- ✅ 需要最快的构建速度

**使用上传模式：**
- ✅ 偶尔构建
- ✅ 无SSH权限
- ✅ 项目较小
- ✅ 简单快速开始

### 2. 优化构建时间

```bash
# rsync模式：排除不需要的文件
rsync --exclude='node_modules' \
      --exclude='.git' \
      --exclude='dist'

# 上传模式：打包时排除
tar --exclude='node_modules' -czf code.tar.gz .

# 利用缓存
# workspace保留node_modules，npm install增量更新
```

### 3. 处理超时

```bash
# 公共CI：25分钟后退出
CI_TIMEOUT=1500

# 远程CI：配置更长的任务超时
CI_JOB_TIMEOUT=7200  # 2小时
```

### 4. 错误处理

```bash
# 脚本中使用 set -e 立即退出
set -e

# 或使用 && 链接命令
npm install && npm test && npm run build
```

## 性能对比

### Node.js项目（100MB源码）

| 模式 | 首次构建 | 后续构建 | 优势 |
|------|---------|---------|------|
| rsync | 5分20秒 | **4分7秒** | 增量同步快 |
| upload | 5分17秒 | 5分15秒 | 无需SSH |

### Python项目（50MB源码）

| 模式 | 首次构建 | 后续构建 | 优势 |
|------|---------|---------|------|
| rsync | 3分30秒 | **2分45秒** | pip缓存复用 |
| upload | 3分25秒 | 3分20秒 | 简单直接 |

## 故障排查

### 问题1: SSH连接失败

```bash
# 测试SSH连接
ssh ci-user@remote-ci "echo Connected"

# 如果失败，检查：
# 1. SSH密钥是否配置
ssh-keygen -t ed25519
ssh-copy-id ci-user@remote-ci

# 2. known_hosts
ssh-keyscan -H remote-ci >> ~/.ssh/known_hosts
```

### 问题2: API认证失败

```bash
# 测试API连接
curl http://remote-ci:5000/api/health

# 测试认证
curl http://remote-ci:5000/api/stats \
  -H "Authorization: Bearer $TOKEN"

# 检查Token
grep CI_API_TOKEN /opt/remote-ci/.env
```

### 问题3: 任务一直排队

```bash
# 检查Worker状态
sudo systemctl status remote-ci-worker

# 查看Worker日志
tail -f /var/log/remote-ci/worker.log

# 检查Redis
redis-cli ping
```

## 更多帮助

- 📚 完整文档：[../README.md](../README.md)
- 🚀 快速开始：[../docs/QUICKSTART.md](../docs/QUICKSTART.md)
- 🏗️ 架构设计：[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
