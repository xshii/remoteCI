#!/bin/bash
##############################################################################
# 测试脚本 - rsync模式
# 用途：验证rsync模式是否正常工作
##############################################################################

set -e

echo "========================================"
echo "Remote CI - rsync模式测试"
echo "========================================"
echo ""

# 配置
REMOTE_CI_HOST=${REMOTE_CI_HOST:-"ci-user@localhost"}
REMOTE_CI_API=${REMOTE_CI_API:-"http://localhost:5000"}
REMOTE_CI_TOKEN=${REMOTE_CI_TOKEN:-"your-token"}
TEST_PROJECT="test-rsync-$$"
WORKSPACE_PATH="/var/ci-workspace/$TEST_PROJECT"

echo "配置信息："
echo "  远程主机: $REMOTE_CI_HOST"
echo "  API地址: $REMOTE_CI_API"
echo "  项目名称: $TEST_PROJECT"
echo ""

# 创建测试项目
echo ">>> 步骤1: 创建测试项目"
TEST_DIR="/tmp/$TEST_PROJECT"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# 创建测试文件
cat > test.sh <<'EOF'
#!/bin/bash
echo "====== 测试开始 ======"
echo "当前目录: $(pwd)"
echo "文件列表:"
ls -la
echo "测试文件内容:"
cat test.txt
echo "====== 测试成功 ======"
EOF

echo "Hello from Remote CI Test" > test.txt

chmod +x test.sh

echo "✓ 测试项目已创建: $TEST_DIR"
echo ""

# 同步代码
echo ">>> 步骤2: 同步代码到远程CI"

# 创建远程目录
ssh $REMOTE_CI_HOST "mkdir -p $WORKSPACE_PATH" || {
    echo "✗ SSH连接失败，请检查："
    echo "  1. SSH密钥是否配置"
    echo "  2. 主机地址是否正确"
    echo "  3. 用户是否有权限"
    exit 1
}

# rsync同步
rsync -avz ./ $REMOTE_CI_HOST:$WORKSPACE_PATH/ || {
    echo "✗ rsync同步失败"
    exit 1
}

echo "✓ 代码同步完成"
echo ""

# 提交任务
echo ">>> 步骤3: 提交任务"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$REMOTE_CI_API/api/jobs/rsync" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"workspace\": \"$WORKSPACE_PATH\",
        \"script\": \"bash test.sh\",
        \"user\": \"test-user\"
    }")

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
echo ""

# 等待结果
echo ">>> 步骤4: 等待执行结果"
echo ""

MAX_WAIT=120
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID" \
        -H "Authorization: Bearer $REMOTE_CI_TOKEN")

    STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*' | cut -d'"' -f4)

    printf "\r[%03ds] 状态: %-10s" $ELAPSED "$STATUS"

    case "$STATUS" in
        "success")
            echo ""
            echo ""
            echo "========================================"
            echo "✓ 测试成功"
            echo "========================================"
            echo ""
            echo "任务日志:"
            echo "----------------------------------------"
            curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID/logs" \
                -H "Authorization: Bearer $REMOTE_CI_TOKEN"
            echo "----------------------------------------"

            # 清理
            echo ""
            echo "清理测试数据..."
            ssh $REMOTE_CI_HOST "rm -rf $WORKSPACE_PATH"
            rm -rf "$TEST_DIR"

            exit 0
            ;;

        "failed"|"error")
            echo ""
            echo ""
            echo "========================================"
            echo "✗ 测试失败"
            echo "========================================"
            echo ""
            echo "任务日志:"
            echo "----------------------------------------"
            curl -s "$REMOTE_CI_API/api/jobs/$JOB_ID/logs" \
                -H "Authorization: Bearer $REMOTE_CI_TOKEN"
            echo "----------------------------------------"

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

echo ""
echo "✗ 测试超时"
exit 1
