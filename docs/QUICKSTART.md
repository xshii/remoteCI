# 快速启动指南

## 5分钟部署远程CI

### 前置要求

- Linux服务器（Ubuntu 20.04+ / CentOS 7+）
- Python 3.8+
- sudo权限

### 步骤1: 安装（2分钟）

```bash
# 克隆项目
git clone https://github.com/your-org/remoteCI.git
cd remoteCI

# 一键安装
sudo bash deploy/install-server.sh
```

安装脚本会自动：
- ✅ 安装Python、Redis等依赖
- ✅ 创建ci-user用户
- ✅ 配置systemd服务
- ✅ 生成随机API Token

### 步骤2: 启动服务（30秒）

```bash
# 启动Redis
sudo systemctl start redis

# 启动API服务
sudo systemctl start remote-ci-api

# 启动Worker
sudo systemctl start remote-ci-worker

# 检查状态
sudo systemctl status remote-ci-api
sudo systemctl status remote-ci-worker
```

### 步骤3: 测试（1分钟）

#### 方法1: Web界面测试

浏览器访问：`http://your-server-ip:5000`

输入API Token（在安装时输出，或查看 `/opt/remote-ci/.env`）

#### 方法2: 命令行测试

```bash
# 获取API Token
TOKEN=$(grep CI_API_TOKEN /opt/remote-ci/.env | cut -d'=' -f2)

# 测试健康检查
curl http://localhost:5000/api/health

# 提交测试任务（上传模式）
echo "echo 'Hello Remote CI'" > test.sh
tar -czf code.tar.gz test.sh

curl -X POST http://localhost:5000/api/jobs/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "code=@code.tar.gz" \
  -F "script=bash test.sh"
```

### 步骤4: 配置公共CI（1分钟）

#### 方式A: rsync模式（推荐）

```bash
# 1. 配置SSH密钥（在公共CI服务器上）
ssh-keygen -t ed25519
ssh-copy-id ci-user@your-remote-ci-ip

# 2. 测试连接
ssh ci-user@your-remote-ci-ip "echo Connected"

# 3. 在公共CI中使用
cd your-project
bash /path/to/remoteCI/client/submit-rsync.sh my-project "npm test"
```

#### 方式B: 上传模式

```bash
# 在公共CI中使用
cd your-project
export REMOTE_CI_API="http://your-remote-ci-ip:5000"
export REMOTE_CI_TOKEN="your-api-token"

bash /path/to/remoteCI/client/submit-upload.sh "npm test"
```

## 常见场景示例

### 场景1: Node.js项目

```bash
# rsync模式
bash client/submit-rsync.sh myapp "npm install && npm test && npm run build"

# 上传模式
bash client/submit-upload.sh "npm install && npm test"
```

### 场景2: Python项目

```bash
bash client/submit-rsync.sh myapp "pip install -r requirements.txt && pytest"
```

### 场景3: Docker构建（远程CI需要Docker）

```bash
bash client/submit-rsync.sh myapp "docker build -t myapp . && docker run myapp npm test"
```

### 场景4: 长时间任务（>30分钟）

```bash
# 使用较长的超时时间（但公共CI会在25分钟后退出）
export CI_TIMEOUT=7200  # 2小时

bash client/submit-rsync.sh myapp "npm run long-build"

# 任务会继续在远程CI执行，通过Web界面查看结果
```

## GitLab CI集成

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_HOST: "ci-user@192.168.1.100"
  REMOTE_CI_API: "http://192.168.1.100:5000"
  # Token配置在GitLab CI/CD Settings -> Variables

remote_build:
  stage: build
  timeout: 30m
  before_script:
    # 配置SSH（只需首次）
    - mkdir -p ~/.ssh
    - echo "$SSH_PRIVATE_KEY" > ~/.ssh/id_rsa
    - chmod 600 ~/.ssh/id_rsa
    - ssh-keyscan -H 192.168.1.100 >> ~/.ssh/known_hosts
  script:
    - bash client/submit-rsync.sh $CI_PROJECT_NAME "npm test"
  artifacts:
    when: always
    reports:
      junit: test-results.xml
```

## GitHub Actions集成

```yaml
# .github/workflows/remote-ci.yml
name: Remote CI Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - uses: actions/checkout@v3

      - name: Setup SSH (rsync模式)
        if: ${{ env.USE_RSYNC == 'true' }}
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan -H ${{ secrets.REMOTE_CI_HOST }} >> ~/.ssh/known_hosts

      - name: Submit to Remote CI
        env:
          REMOTE_CI_API: ${{ secrets.REMOTE_CI_API }}
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
          REMOTE_CI_HOST: ${{ secrets.REMOTE_CI_HOST }}
        run: |
          bash client/submit-upload.sh "npm install && npm test"
```

## 下一步

- 📚 阅读完整文档：[README.md](../README.md)
- 🔧 配置优化：[docs/CONFIGURATION.md](./CONFIGURATION.md)
- 🐛 故障排查：[docs/TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- 🔒 安全加固：[docs/SECURITY.md](./SECURITY.md)

## 获取帮助

- GitHub Issues: https://github.com/your-org/remoteCI/issues
- 文档: https://github.com/your-org/remoteCI/wiki
