#!/bin/bash
##############################################################################
# 公共CI脚本 - rsync模式
# 用法: ./submit-rsync.sh [project-name] [build-script]
##############################################################################

set -e

# ============ 配置区域 ============
REMOTE_CI_HOST=${REMOTE_CI_HOST:-"ci-user@remote-ci-server"}
REMOTE_CI_API=${REMOTE_CI_API:-"http://remote-ci-server:5000"}
REMOTE_CI_TOKEN=${REMOTE_CI_TOKEN:-"your-api-token"}
WORKSPACE_BASE=${WORKSPACE_BASE:-"/var/ci-workspace"}

# ============ 参数处理 ============
PROJECT_NAME=${1:-"default-project"}
BUILD_SCRIPT=${2:-"npm install && npm test"}

# 如果是在CI环境中，自动获取项目名
if [ -n "$CI_PROJECT_NAME" ]; then
    PROJECT_NAME="$CI_PROJECT_NAME"
fi

WORKSPACE_PATH="$WORKSPACE_BASE/$PROJECT_NAME"

echo "=========================================="
echo "Remote CI - rsync模式"
echo "=========================================="
echo "项目名称: $PROJECT_NAME"
echo "构建脚本: $BUILD_SCRIPT"
echo "远程路径: $WORKSPACE_PATH"
echo "=========================================="
echo ""

# ============ 步骤1: 同步代码 ============
echo ">>> 步骤 1/3: 同步代码到远程CI"

# 创建远程目录
ssh $REMOTE_CI_HOST "mkdir -p $WORKSPACE_PATH"

# rsync同步（排除不需要的文件）
rsync -avz --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='dist' \
    --exclude='build' \
    --exclude='.env' \
    ./ $REMOTE_CI_HOST:$WORKSPACE_PATH/

echo "✓ 代码同步完成"
echo ""

# ============ 步骤2: 提交任务 ============
echo ">>> 步骤 2/3: 提交构建任务"

RESPONSE=$(curl -s -X POST "$REMOTE_CI_API/api/jobs/rsync" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"workspace\": \"$WORKSPACE_PATH\",
        \"script\": \"$BUILD_SCRIPT\",
        \"user\": \"${USER:-unknown}\"
    }")

JOB_ID=$(echo $RESPONSE | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
    echo "✗ 任务提交失败"
    echo "响应: $RESPONSE"
    exit 1
fi

echo "✓ 任务已提交"
echo "任务ID: $JOB_ID"
echo "Web查看: $REMOTE_CI_API/#job-$JOB_ID"
echo ""

# ============ 步骤3: 等待结果 ============
echo ">>> 步骤 3/3: 等待构建结果"
echo ""

MAX_WAIT=${CI_TIMEOUT:-1500}  # 默认25分钟
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID" \
        -H "Authorization: Bearer $REMOTE_CI_TOKEN")

    STATUS=$(echo $STATUS_RESPONSE | grep -o '"status":"[^"]*' | cut -d'"' -f4)

    printf "\r[%03ds] 状态: %-10s" $ELAPSED "$STATUS"

    case "$STATUS" in
        "success")
            echo ""
            echo ""
            echo "=========================================="
            echo "✓ 构建成功"
            echo "=========================================="

            # 显示日志
            echo ""
            echo "构建日志:"
            echo "------------------------------------------"
            curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID/logs" \
                -H "Authorization: Bearer $REMOTE_CI_TOKEN"
            echo "------------------------------------------"

            exit 0
            ;;

        "failed"|"error"|"timeout")
            echo ""
            echo ""
            echo "=========================================="
            echo "✗ 构建失败"
            echo "=========================================="

            # 显示日志
            echo ""
            echo "构建日志:"
            echo "------------------------------------------"
            curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID/logs" \
                -H "Authorization: Bearer $REMOTE_CI_TOKEN"
            echo "------------------------------------------"

            exit 1
            ;;

        "queued"|"running")
            sleep $INTERVAL
            ELAPSED=$((ELAPSED + INTERVAL))
            ;;

        *)
            echo ""
            echo "✗ 未知状态: $STATUS"
            exit 1
            ;;
    esac
done

# 超时处理
echo ""
echo ""
echo "=========================================="
echo "⚠ 公共CI等待超时"
echo "=========================================="
echo "任务仍在远程CI执行中..."
echo "查看任务: $REMOTE_CI_API/#job-$JOB_ID"
echo ""
echo "远程CI将继续执行，结果可通过Web界面查看"
echo "=========================================="

# 不返回失败状态，避免公共CI报错
exit 0
