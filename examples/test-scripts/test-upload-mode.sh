#!/bin/bash
##############################################################################
# 测试脚本 - 上传模式
# 用途：验证上传模式是否正常工作
##############################################################################

set -e

echo "========================================"
echo "Remote CI - 上传模式测试"
echo "========================================"
echo ""

# 配置
REMOTE_CI_API=${REMOTE_CI_API:-"http://localhost:5000"}
REMOTE_CI_TOKEN=${REMOTE_CI_TOKEN:-"your-token"}

echo "配置信息："
echo "  API地址: $REMOTE_CI_API"
echo ""

# 创建测试项目
echo ">>> 步骤1: 创建测试项目"
TEST_DIR="/tmp/test-upload-$$"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

# 创建测试文件
cat > test.sh <<'EOF'
#!/bin/bash
echo "====== 上传模式测试 ======"
echo "当前目录: $(pwd)"
echo "文件列表:"
ls -la
echo ""
echo "运行Python脚本测试:"
python3 hello.py
echo ""
echo "====== 测试成功 ======"
EOF

cat > hello.py <<'EOF'
print("Hello from Remote CI!")
print("Upload mode is working!")
EOF

chmod +x test.sh

echo "✓ 测试项目已创建: $TEST_DIR"
echo ""

# 打包代码
echo ">>> 步骤2: 打包代码"
tar -czf code.tar.gz test.sh hello.py

CODE_SIZE=$(du -h code.tar.gz | cut -f1)
echo "✓ 代码已打包 (大小: $CODE_SIZE)"
echo ""

# 提交任务
echo ">>> 步骤3: 上传并提交任务"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$REMOTE_CI_API/api/jobs/upload" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -F "code=@code.tar.gz" \
    -F "script=bash test.sh" \
    -F "user=test-user")

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
