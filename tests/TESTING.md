# 端到端测试指南

## 🎯 概述

本项目提供完整的Docker端到端测试环境，模拟真实的远程CI服务器，验证客户端与服务器的通信。

## 📋 测试架构

```
本地环境                       Docker容器（远程CI服务器）
┌─────────────┐               ┌──────────────────────────┐
│ 测试脚本    │  HTTP/API     │  Flask API (5000)        │
│ test-e2e.sh │──────────────▶│  ├─ Token认证            │
│             │               │  └─ RESTful API          │
└─────────────┘               │                          │
                              │  Redis (队列)            │
                              │                          │
                              │  Celery Worker (执行)    │
                              │                          │
                              │  /var/ci-workspace       │
                              │  /var/lib/remote-ci/logs │
                              └──────────────────────────┘
```

## 🚀 快速开始

### 前置要求

```bash
# 1. Docker和Docker Compose
docker --version          # 需要 20.10+
docker-compose --version  # 需要 2.0+

# 2. Python和依赖
python3 --version         # 需要 3.8+
pip3 install requests

# 3. jq（JSON解析工具）
brew install jq           # macOS
# 或
apt install jq            # Linux
```

### 运行完整测试

```bash
# 一键运行所有测试（推荐）
make test-all
```

### 分步运行

```bash
# 1. 启动测试环境
make test-start

# 2. 运行测试
make test-e2e

# 3. 查看日志
make test-logs

# 4. 停止环境
make test-stop
```

## 📝 测试内容

### 测试1: 环境启动
- ✅ Docker容器启动
- ✅ Redis连接
- ✅ API健康检查
- ✅ Worker就绪

### 测试2: Upload模式
- ✅ 代码打包上传
- ✅ 任务提交
- ✅ 任务执行
- ✅ 日志生成

### 测试3: Rsync模式
- ✅ Workspace准备
- ✅ 任务提交
- ✅ 用户隔离
- ✅ 任务执行

### 测试4: 并发隔离
- ✅ 多用户同时提交
- ✅ Workspace隔离
- ✅ 日志独立
- ✅ 无冲突

### 测试5: Git模式
- ✅ 仓库克隆
- ✅ 代码执行
- ✅ 结果返回

### 测试6: 统计API
- ✅ 任务统计
- ✅ 状态查询
- ✅ 历史记录

### 测试7: 文件系统
- ✅ Workspace目录
- ✅ 日志文件
- ✅ 权限正确

## 🔍 测试输出示例

```bash
$ make test-all

==========================================
步骤1: 启动测试环境
==========================================
ℹ 停止旧容器...
ℹ 清理测试数据...
ℹ 启动Docker容器...
[+] Building 5.2s (12/12) FINISHED
[+] Running 2/2
 ✔ Container remoteCI-test-redis    Started
 ✔ Container remoteCI-test-server   Started
ℹ 等待服务就绪...
✓ 远程CI服务已就绪

==========================================
步骤2: 测试API健康检查
==========================================
✓ 健康检查通过

==========================================
步骤3: 测试Upload模式
==========================================
ℹ 提交upload任务...
✓ Upload任务已提交: abc123...
ℹ 等待任务完成...
✓ Upload任务执行成功

==========================================
步骤4: 测试Rsync模式（用户隔离）
==========================================
ℹ 创建测试workspace...
ℹ 提交rsync任务（user: alice）...
✓ Rsync任务已提交: def456...
ℹ 等待任务完成...
✓ Rsync任务执行成功
✓ 日志验证通过

==========================================
步骤5: 测试并发隔离（多用户）
==========================================
ℹ 同时提交Alice和Bob的任务...
✓ 并发隔离验证通过（Alice和Bob的workspace完全隔离）

==========================================
步骤6: 测试Git模式
==========================================
ℹ 提交Git克隆任务...
✓ Git任务已提交: ghi789...
ℹ 等待任务完成...
✓ Git任务执行成功

==========================================
步骤7: 测试统计API
==========================================
✓ 统计API工作正常（总任务数: 6）

==========================================
步骤8: 验证文件系统
==========================================
ℹ 检查workspace目录...
✓ Workspace目录结构正确
ℹ 检查日志文件...
✓ 日志文件已生成（6 个）

==========================================
测试总结
==========================================
通过: 18
失败: 0

==========================================
✓ 所有测试通过！
==========================================
```

## 🛠️ Makefile命令

| 命令 | 说明 |
|------|------|
| `make test-all` | 运行完整测试（推荐） |
| `make test-start` | 启动测试环境 |
| `make test-e2e` | 运行端到端测试 |
| `make test-logs` | 查看容器日志 |
| `make test-stop` | 停止测试环境 |
| `make test-clean` | 清理环境和数据 |
| `make test-shell` | 进入容器shell |
| `make test-check` | 检查环境依赖 |

## 🔧 手动测试

### 1. 启动环境

```bash
docker-compose -f docker-compose.test.yml up -d
```

### 2. 测试API

```bash
# 健康检查
curl http://localhost:15000/api/health

# 提交测试任务
curl -X POST http://localhost:15000/api/jobs/upload \
  -H "Authorization: Bearer test-token-12345678" \
  -F "code=@code.tar.gz" \
  -F "script=echo test"

# 查看任务状态
curl -H "Authorization: Bearer test-token-12345678" \
  http://localhost:15000/api/jobs/{job_id}

# 查看日志
curl -H "Authorization: Bearer test-token-12345678" \
  http://localhost:15000/api/jobs/{job_id}/logs
```

### 3. 使用Python客户端

```bash
export REMOTE_CI_API="http://localhost:15000"
export REMOTE_CI_TOKEN="test-token-12345678"

# Upload模式
python3 client/submit.py upload "echo test"

# Rsync模式（需要先创建workspace）
mkdir -p test-workspace/myproject
echo "echo test" > test-workspace/myproject/test.sh

curl -X POST http://localhost:15000/api/jobs/rsync \
  -H "Authorization: Bearer test-token-12345678" \
  -H "Content-Type: application/json" \
  -d '{
    "workspace": "/var/ci-workspace/myproject",
    "script": "bash test.sh"
  }'

# Git模式
python3 client/submit.py git \
  https://github.com/octocat/Hello-World.git \
  master "ls -la"
```

## 📁 测试文件结构

```
remoteCI/
├── docker-compose.test.yml    # Docker编排配置
├── Dockerfile.test            # 测试镜像定义
├── test-e2e.sh               # 端到端测试脚本
├── Makefile                   # 测试工具
├── TESTING.md                 # 本文件
│
├── test-workspace/            # 测试workspace（自动生成）
│   ├── test-project-alice/
│   └── test-project-bob/
│
└── test-logs/                 # 测试日志（自动生成）
    ├── {job-id-1}.log
    └── {job-id-2}.log
```

## 🐛 故障排查

### 问题1: 容器启动失败

```bash
# 查看日志
docker-compose -f docker-compose.test.yml logs

# 检查端口占用
lsof -i :15000

# 重新构建
docker-compose -f docker-compose.test.yml up -d --build --force-recreate
```

### 问题2: 健康检查失败

```bash
# 检查服务状态
docker-compose -f docker-compose.test.yml ps

# 查看API日志
docker-compose -f docker-compose.test.yml logs remote-ci-server

# 手动测试
curl -v http://localhost:15000/api/health
```

### 问题3: 任务一直pending

```bash
# 检查Worker是否运行
docker exec remoteCI-test-server ps aux | grep celery

# 查看Worker日志
docker-compose -f docker-compose.test.yml logs remote-ci-server | grep celery

# 检查Redis连接
docker exec remoteCI-test-redis redis-cli ping
```

### 问题4: 测试脚本失败

```bash
# 检查jq是否安装
which jq || brew install jq

# 检查Python依赖
pip3 list | grep requests

# 手动运行单个测试
bash -x test-e2e.sh
```

## 🧹 清理环境

```bash
# 停止并删除所有容器
make test-clean

# 或手动清理
docker-compose -f docker-compose.test.yml down -v
rm -rf test-workspace test-logs
```

## 🎓 高级用法

### 持续集成（CI/CD）

```yaml
# .github/workflows/test.yml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install dependencies
        run: |
          pip3 install requests
          sudo apt-get install jq

      - name: Run E2E tests
        run: make test-all
```

### 性能测试

```bash
# 并发测试（10个任务）
for i in {1..10}; do
  curl -X POST http://localhost:15000/api/jobs/upload \
    -H "Authorization: Bearer test-token-12345678" \
    -F "code=@test.tar.gz" \
    -F "script=echo test-$i" &
done
wait

# 查看统计
curl http://localhost:15000/api/stats | jq .
```

### 调试模式

```bash
# 进入容器
docker exec -it remoteCI-test-server bash

# 查看目录
ls -la /var/ci-workspace
ls -la /var/lib/remote-ci/logs

# 查看进程
ps aux | grep celery
ps aux | grep python

# 查看环境变量
env | grep CI_
```

## 📚 相关文档

- [主README](README.md) - 项目概述
- [客户端文档](client/README_PYTHON.md) - Python客户端使用
- [架构文档](docs/ARCHITECTURE.md) - 系统架构
- [并发分析](docs/CONCURRENCY_ANALYSIS.md) - 并发问题分析

---

**提示**：首次运行 `make test-all` 会下载Docker镜像和构建容器，可能需要几分钟。后续运行会快很多。
