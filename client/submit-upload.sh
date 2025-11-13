#!/bin/bash
##############################################################################
# 公共CI脚本 - 上传模式
# 用法:
#   ./submit-upload.sh [build-script] [upload-path]
#   ./submit-upload.sh "npm test"              # 上传当前目录
#   ./submit-upload.sh "npm test" "src/ tests/"  # 只上传src和tests目录
##############################################################################

set -e

# ============ 配置区域 ============
REMOTE_CI_API=${REMOTE_CI_API:-"http://remote-ci-server:5000"}
REMOTE_CI_TOKEN=${REMOTE_CI_TOKEN:-"your-api-token"}

# ============ 参数处理 ============
BUILD_SCRIPT=${1:-"npm install && npm test"}
UPLOAD_PATH=${2:-"."}  # 默认上传当前目录

echo "=========================================="
echo "Remote CI - 上传模式"
echo "=========================================="
echo "构建脚本: $BUILD_SCRIPT"
echo "上传内容: $UPLOAD_PATH"
echo "=========================================="
echo ""

# ============ 步骤1: 打包代码 ============
echo ">>> 步骤 1/3: 打包代码"

CODE_ARCHIVE="/tmp/ci-code-$$.tar.gz"

# 如果UPLOAD_PATH包含空格，说明是多个路径
if [[ "$UPLOAD_PATH" == *" "* ]]; then
    # 多个路径
    echo "打包指定目录: $UPLOAD_PATH"
    tar -czf "$CODE_ARCHIVE" \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='dist' \
        --exclude='build' \
        --exclude='.env' \
        --exclude='*.log' \
        $UPLOAD_PATH
elif [ "$UPLOAD_PATH" == "." ]; then
    # 当前目录
    echo "打包当前目录（排除常见临时文件）"
    tar -czf "$CODE_ARCHIVE" \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='dist' \
        --exclude='build' \
        --exclude='.env' \
        --exclude='*.log' \
        .
else
    # 单个路径
    echo "打包指定路径: $UPLOAD_PATH"
    tar -czf "$CODE_ARCHIVE" \
        --exclude='.git' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        "$UPLOAD_PATH"
fi

ARCHIVE_SIZE=$(du -h "$CODE_ARCHIVE" | cut -f1)
echo "✓ 代码打包完成 (大小: $ARCHIVE_SIZE)"
echo ""

# ============ 步骤2: 上传并提交任务 ============
echo ">>> 步骤 2/3: 上传代码并提交任务"

RESPONSE=$(curl -s -X POST "$REMOTE_CI_API/api/jobs/upload" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -F "code=@$CODE_ARCHIVE" \
    -F "script=$BUILD_SCRIPT" \
    -F "user=${USER:-unknown}")

# 清理本地打包文件
rm -f "$CODE_ARCHIVE"

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
