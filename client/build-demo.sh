#!/bin/bash
# Remote CI 构建脚本示例
# 此脚本在远程CI服务器上的workspace目录中执行
#
# 环境变量:
#   CI_WORKSPACE - 当前workspace路径 (例如: /var/ci-workspace/myproject-alice)
#   CI_SHARED    - 共享资源目录 (例如: /var/ci-shared)
#   CI_CACHE     - 缓存目录 (例如: /var/ci-cache)

set -e  # 遇到错误立即退出

echo "=========================================="
echo "Remote CI 构建脚本"
echo "=========================================="
echo "工作目录: $(pwd)"
echo "用户: $(whoami)"
echo "时间: $(date)"
echo "=========================================="
echo

# ============================================
# 步骤 1: 复制远端CI的固定资产文件
# ============================================
echo ">>> 步骤 1/5: 复制共享资源"

# 示例1: 复制共享配置文件
if [ -f "${CI_SHARED}/config/app.conf" ]; then
    echo "  复制共享配置: app.conf"
    cp "${CI_SHARED}/config/app.conf" ./config/
fi

# 示例2: 复制证书/密钥文件
if [ -d "${CI_SHARED}/certs" ]; then
    echo "  复制证书目录"
    mkdir -p ./certs
    cp -r "${CI_SHARED}/certs/"* ./certs/
fi

# 示例3: 复制预编译的依赖库
if [ -d "${CI_SHARED}/libs" ]; then
    echo "  复制预编译库"
    mkdir -p ./libs
    cp -r "${CI_SHARED}/libs/"* ./libs/
fi

# 示例4: 复制测试数据
if [ -d "${CI_SHARED}/test-data" ]; then
    echo "  复制测试数据"
    mkdir -p ./test-data
    cp -r "${CI_SHARED}/test-data/"* ./test-data/
fi

echo "✓ 共享资源复制完成"
echo

# ============================================
# 步骤 2: 使用缓存加速构建
# ============================================
echo ">>> 步骤 2/5: 恢复构建缓存"

# Node.js 缓存示例
if [ -d "${CI_CACHE}/node_modules" ]; then
    echo "  恢复 node_modules 缓存"
    cp -r "${CI_CACHE}/node_modules" ./
else
    echo "  无可用缓存"
fi

# Python 缓存示例
if [ -d "${CI_CACHE}/.venv" ]; then
    echo "  恢复 Python 虚拟环境缓存"
    cp -r "${CI_CACHE}/.venv" ./
fi

# Maven 缓存示例
if [ -d "${CI_CACHE}/.m2" ]; then
    echo "  恢复 Maven 缓存"
    mkdir -p ~/.m2
    cp -r "${CI_CACHE}/.m2/"* ~/.m2/
fi

echo "✓ 缓存恢复完成"
echo

# ============================================
# 步骤 3: 安装依赖
# ============================================
echo ">>> 步骤 3/5: 安装项目依赖"

# Node.js 项目
if [ -f "package.json" ]; then
    echo "  检测到 Node.js 项目"
    npm install --prefer-offline
fi

# Python 项目
if [ -f "requirements.txt" ]; then
    echo "  检测到 Python 项目"
    python3 -m venv .venv || true
    source .venv/bin/activate || true
    pip install -r requirements.txt
fi

# Go 项目
if [ -f "go.mod" ]; then
    echo "  检测到 Go 项目"
    go mod download
fi

# Java/Maven 项目
if [ -f "pom.xml" ]; then
    echo "  检测到 Maven 项目"
    mvn dependency:go-offline
fi

echo "✓ 依赖安装完成"
echo

# ============================================
# 步骤 4: 构建/测试
# ============================================
echo ">>> 步骤 4/5: 执行构建和测试"

# Node.js 构建示例
if [ -f "package.json" ]; then
    echo "  运行 npm 构建"
    npm run build || true

    echo "  运行单元测试"
    npm test

    echo "  运行代码检查"
    npm run lint || true
fi

# Python 测试示例
if [ -f "pytest.ini" ] || [ -f "setup.py" ]; then
    echo "  运行 Python 测试"
    source .venv/bin/activate || true
    pytest tests/ -v --tb=short
fi

# Go 测试示例
if [ -f "go.mod" ]; then
    echo "  运行 Go 测试"
    go test ./... -v
fi

# Java/Maven 构建示例
if [ -f "pom.xml" ]; then
    echo "  运行 Maven 构建"
    mvn clean package -DskipTests=false
fi

echo "✓ 构建和测试完成"
echo

# ============================================
# 步骤 5: 保存构建产物和缓存
# ============================================
echo ">>> 步骤 5/5: 保存构建产物"

# 创建构建产物目录
ARTIFACTS_DIR="${CI_WORKSPACE}/artifacts"
mkdir -p "${ARTIFACTS_DIR}"

# 保存 Node.js 构建产物
if [ -d "dist" ]; then
    echo "  保存 dist/ 目录"
    cp -r dist "${ARTIFACTS_DIR}/"
fi

if [ -d "build" ]; then
    echo "  保存 build/ 目录"
    cp -r build "${ARTIFACTS_DIR}/"
fi

# 保存测试报告
if [ -d "coverage" ]; then
    echo "  保存测试覆盖率报告"
    cp -r coverage "${ARTIFACTS_DIR}/"
fi

# 保存 Java 构建产物
if [ -d "target" ]; then
    echo "  保存 Maven target/ 目录"
    cp -r target "${ARTIFACTS_DIR}/"
fi

# 更新缓存（提速后续构建）
echo "  更新构建缓存"
mkdir -p "${CI_CACHE}"

if [ -d "node_modules" ]; then
    echo "    缓存 node_modules"
    rm -rf "${CI_CACHE}/node_modules"
    cp -r node_modules "${CI_CACHE}/"
fi

if [ -d ".venv" ]; then
    echo "    缓存 Python 虚拟环境"
    rm -rf "${CI_CACHE}/.venv"
    cp -r .venv "${CI_CACHE}/"
fi

echo "✓ 构建产物保存完成"
echo

# ============================================
# 构建总结
# ============================================
echo "=========================================="
echo "✓ 构建成功完成！"
echo "=========================================="
echo "构建产物位置: ${ARTIFACTS_DIR}"
echo "构建时间: $(date)"
echo

# 显示产物列表
if [ -d "${ARTIFACTS_DIR}" ]; then
    echo "产物列表:"
    ls -lh "${ARTIFACTS_DIR}"
fi

echo "=========================================="

exit 0
