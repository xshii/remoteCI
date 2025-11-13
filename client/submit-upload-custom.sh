#!/bin/bash
##############################################################################
# 公共CI脚本 - 上传模式（自定义排除）
# 用法:
#   ./submit-upload-custom.sh [build-script] [include-paths] [exclude-patterns]
#
# 示例:
#   # 只上传src和tests目录
#   ./submit-upload-custom.sh "npm test" "src/ tests/" ""
#
#   # 上传当前目录，但排除指定文件
#   ./submit-upload-custom.sh "npm test" "." "*.log,*.tmp,cache/"
#
#   # 只上传特定文件
#   ./submit-upload-custom.sh "npm test" "package.json src/ Dockerfile" ""
##############################################################################

set -e

# ============ 配置区域 ============
REMOTE_CI_API=${REMOTE_CI_API:-"http://remote-ci-server:5000"}
REMOTE_CI_TOKEN=${REMOTE_CI_TOKEN:-"your-api-token"}

# ============ 参数处理 ============
BUILD_SCRIPT=${1:-"npm install && npm test"}
INCLUDE_PATHS=${2:-"."}
EXCLUDE_PATTERNS=${3:-""}  # 逗号分隔的排除模式

echo "=========================================="
echo "Remote CI - 上传模式（自定义）"
echo "=========================================="
echo "构建脚本: $BUILD_SCRIPT"
echo "包含路径: $INCLUDE_PATHS"
echo "排除模式: ${EXCLUDE_PATTERNS:-默认排除}"
echo "=========================================="
echo ""

# ============ 步骤1: 打包代码 ============
echo ">>> 步骤 1/3: 打包代码"

CODE_ARCHIVE="/tmp/ci-code-$$.tar.gz"

# 构建tar命令
TAR_CMD="tar -czf $CODE_ARCHIVE"

# 添加默认排除
DEFAULT_EXCLUDES=(
    '.git'
    'node_modules'
    '__pycache__'
    '*.pyc'
    '.pytest_cache'
    'dist'
    'build'
    '.env'
    '*.log'
)

for exclude in "${DEFAULT_EXCLUDES[@]}"; do
    TAR_CMD="$TAR_CMD --exclude='$exclude'"
done

# 添加自定义排除
if [ -n "$EXCLUDE_PATTERNS" ]; then
    IFS=',' read -ra EXCLUDES <<< "$EXCLUDE_PATTERNS"
    for exclude in "${EXCLUDES[@]}"; do
        exclude=$(echo "$exclude" | xargs)  # 去除空格
        if [ -n "$exclude" ]; then
            TAR_CMD="$TAR_CMD --exclude='$exclude'"
            echo "  排除: $exclude"
        fi
    done
fi

# 添加包含路径
TAR_CMD="$TAR_CMD $INCLUDE_PATHS"

# 执行打包
echo "执行打包..."
eval $TAR_CMD

ARCHIVE_SIZE=$(du -h "$CODE_ARCHIVE" | cut -f1)
echo "✓ 代码已打包 (大小: $ARCHIVE_SIZE)"
echo ""

# ============ 步骤2: 上传并提交任务 ============
echo ">>> 步骤 2/3: 上传代码并提交任务"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$REMOTE_CI_API/api/jobs/upload" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -F "code=@$CODE_ARCHIVE" \
    -F "script=$BUILD_SCRIPT" \
    -F "user=${USER:-unknown}")

# 清理本地打包文件
rm -f "$CODE_ARCHIVE"

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" != "201" ]; then
    echo "✗ 任务提交失败 (HTTP $HTTP_CODE)"
    echo "$BODY"
    exit 1
fi

JOB_ID=$(echo "$BODY" | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$JOB_ID" ]; then
    echo "✗ 无法获取任务ID"
    echo "$BODY"
    exit 1
fi

echo "✓ 任务已提交"
echo "  任务ID: $JOB_ID"
echo "  Web查看: $REMOTE_CI_API/#job-$JOB_ID"
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

    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)

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
