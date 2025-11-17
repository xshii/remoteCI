# 构建脚本编写指南

## 概述

`build-demo.sh` 是一个完整的构建脚本示例，展示了如何编写在Remote CI上执行的构建脚本。

## 核心功能

### 1. 共享资源管理

从CI服务器的共享目录复制固定资产文件到构建目录：

```bash
# 复制配置文件
cp "${CI_SHARED}/config/app.conf" ./config/

# 复制证书
cp -r "${CI_SHARED}/certs/"* ./certs/

# 复制预编译库
cp -r "${CI_SHARED}/libs/"* ./libs/
```

### 2. 构建缓存

利用缓存加速构建：

```bash
# 恢复 node_modules 缓存
if [ -d "${CI_CACHE}/node_modules" ]; then
    cp -r "${CI_CACHE}/node_modules" ./
fi

# 更新缓存（构建结束后）
cp -r node_modules "${CI_CACHE}/"
```

### 3. 多语言支持

脚本自动检测项目类型并执行相应构建：

- **Node.js**: 检测 `package.json`
- **Python**: 检测 `requirements.txt`
- **Go**: 检测 `go.mod`
- **Java/Maven**: 检测 `pom.xml`

### 4. 构建产物管理

将构建产物保存到指定目录：

```bash
ARTIFACTS_DIR="${CI_WORKSPACE}/artifacts"
cp -r dist "${ARTIFACTS_DIR}/"
cp -r coverage "${ARTIFACTS_DIR}/"
```

## 环境变量

脚本可以使用以下环境变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| `CI_WORKSPACE` | 当前workspace路径 | `/var/ci-workspace/myproject-alice` |
| `CI_SHARED` | 共享资源目录 | `/var/ci-shared` |
| `CI_CACHE` | 缓存目录 | `/var/ci-cache` |
| `PWD` | 当前工作目录 | `/tmp/remote-ci/job-abc123` |

## 使用方法

### 1. 基于demo创建自己的构建脚本

```bash
# 复制demo脚本
cp client/build-demo.sh my-build.sh

# 根据项目需求修改
vim my-build.sh
```

### 2. 使用客户端提交构建

```bash
# Upload模式
python submit.py upload "bash my-build.sh" --user-id alice

# Rsync模式
python submit.py rsync myproject "bash my-build.sh" --user-id alice

# Git模式
python submit.py git https://github.com/user/repo.git main "bash my-build.sh"
```

### 3. 直接使用demo脚本测试

```bash
# 测试完整构建流程
python submit.py upload "bash client/build-demo.sh"
```

## 典型构建场景

### 场景1: Node.js项目

```bash
#!/bin/bash
set -e

echo ">>> 复制共享npm配置"
cp "${CI_SHARED}/config/.npmrc" ./

echo ">>> 恢复node_modules缓存"
[ -d "${CI_CACHE}/node_modules" ] && cp -r "${CI_CACHE}/node_modules" ./

echo ">>> 安装依赖"
npm install --prefer-offline

echo ">>> 运行测试"
npm test

echo ">>> 构建生产版本"
npm run build

echo ">>> 保存构建产物"
mkdir -p "${CI_WORKSPACE}/artifacts"
cp -r dist "${CI_WORKSPACE}/artifacts/"

echo ">>> 更新缓存"
cp -r node_modules "${CI_CACHE}/"

echo "✓ 构建完成"
```

### 场景2: Python项目

```bash
#!/bin/bash
set -e

echo ">>> 复制共享pip配置"
mkdir -p ~/.pip
cp "${CI_SHARED}/config/pip.conf" ~/.pip/

echo ">>> 恢复虚拟环境缓存"
[ -d "${CI_CACHE}/.venv" ] && cp -r "${CI_CACHE}/.venv" ./

echo ">>> 创建虚拟环境"
python3 -m venv .venv
source .venv/bin/activate

echo ">>> 安装依赖"
pip install -r requirements.txt

echo ">>> 运行测试"
pytest tests/ -v --cov=src --cov-report=html

echo ">>> 保存测试报告"
mkdir -p "${CI_WORKSPACE}/artifacts"
cp -r htmlcov "${CI_WORKSPACE}/artifacts/"

echo ">>> 更新缓存"
cp -r .venv "${CI_CACHE}/"

echo "✓ 构建完成"
```

### 场景3: 需要私有依赖的项目

```bash
#!/bin/bash
set -e

echo ">>> 复制私有npm包"
cp -r "${CI_SHARED}/private-packages" ./

echo ">>> 复制Git credentials"
cp "${CI_SHARED}/credentials/.git-credentials" ~/.git-credentials

echo ">>> 安装依赖（包含私有包）"
npm install

echo ">>> 构建"
npm run build

echo ">>> 清理敏感信息"
rm -f ~/.git-credentials

echo "✓ 构建完成"
```

### 场景4: 多阶段构建

```bash
#!/bin/bash
set -e

echo ">>> 阶段1: 编译"
npm run build

echo ">>> 阶段2: 单元测试"
npm test

echo ">>> 阶段3: E2E测试"
npm run test:e2e

echo ">>> 阶段4: 代码质量检查"
npm run lint
npm run type-check

echo ">>> 阶段5: 性能测试"
npm run test:performance

echo ">>> 保存所有报告"
mkdir -p "${CI_WORKSPACE}/artifacts"
cp -r dist coverage lighthouse-report "${CI_WORKSPACE}/artifacts/"

echo "✓ 所有阶段完成"
```

## 最佳实践

### 1. 错误处理

```bash
set -e  # 遇到错误立即退出
set -u  # 使用未定义变量时报错
set -o pipefail  # 管道中任何命令失败都报错
```

### 2. 显示详细信息

```bash
echo ">>> 当前步骤"
echo "  详细操作说明"
echo "✓ 步骤完成"
```

### 3. 条件检查

```bash
# 检查文件存在
if [ -f "package.json" ]; then
    npm install
fi

# 检查目录存在
if [ -d "${CI_SHARED}/config" ]; then
    cp -r "${CI_SHARED}/config/"* ./
fi
```

### 4. 清理临时文件

```bash
# 构建前清理
rm -rf dist/ coverage/

# 构建后清理敏感文件
rm -f .env .git-credentials
```

### 5. 构建时间优化

```bash
# 并行执行测试
npm test -- --parallel

# 使用缓存
npm ci --prefer-offline

# 增量构建
npm run build -- --incremental
```

## 调试技巧

### 查看环境信息

```bash
echo "工作目录: $(pwd)"
echo "用户: $(whoami)"
echo "环境变量:"
env | grep CI_
```

### 查看文件列表

```bash
echo "当前目录文件:"
ls -la

echo "共享资源:"
ls -la "${CI_SHARED}"
```

### 保留构建目录用于调试

```bash
# 构建失败时保留工作目录
trap 'echo "构建失败，工作目录: $(pwd)"' ERR
```

## 常见问题

### Q: 如何访问私有Git仓库？

```bash
# 方法1: 复制SSH密钥
cp "${CI_SHARED}/credentials/id_rsa" ~/.ssh/
chmod 600 ~/.ssh/id_rsa

# 方法2: 使用Git credentials
cp "${CI_SHARED}/credentials/.git-credentials" ~/
git config --global credential.helper store
```

### Q: 如何使用私有npm包？

```bash
# 复制.npmrc（包含token）
cp "${CI_SHARED}/config/.npmrc" ./
npm install
```

### Q: 如何加速Docker构建？

```bash
# 使用缓存的Docker镜像
docker load < "${CI_CACHE}/docker-images.tar"
docker build --cache-from=myapp:latest .
docker save myapp:latest > "${CI_CACHE}/docker-images.tar"
```

## 下一步

1. 根据项目需求修改 `build-demo.sh`
2. 测试构建脚本
3. 配置共享资源目录
4. 优化构建缓存策略
5. 集成到CI/CD流程

## 参考资料

- [Remote CI 使用文档](../README.md)
- [Client提交工具](./submit.py)
- [Docker测试环境](../test/README.md)
