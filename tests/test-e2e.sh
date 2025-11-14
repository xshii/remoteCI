#!/bin/bash
# 端到端测试脚本 - 测试本地客户端与Docker远程CI通信

set -e

# 获取项目根目录（tests的上一级目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试配置
REMOTE_CI_API="http://localhost:15000"
REMOTE_CI_TOKEN="test-token-12345678"
TEST_PROJECT="test-project"

# 测试计数器
TESTS_PASSED=0
TESTS_FAILED=0

# 辅助函数
print_header() {
    echo
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

wait_for_job() {
    local job_id=$1
    local max_wait=30
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        status=$(curl -s -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
            "$REMOTE_CI_API/api/jobs/$job_id" | jq -r '.status' 2>/dev/null || echo "unknown")

        if [ "$status" = "success" ] || [ "$status" = "failed" ]; then
            echo "$status"
            return 0
        fi

        sleep 1
        ((elapsed++))
    done

    echo "timeout"
    return 1
}

# ==========================================
# 测试开始
# ==========================================

print_header "Remote CI 端到端测试套件"

# ==========================================
# 步骤1: 启动测试环境
# ==========================================

print_header "步骤1: 启动测试环境"

print_info "停止旧容器..."
docker compose -f tests/docker-compose.test.yml down -v 2>/dev/null || true

print_info "清理测试数据..."
rm -rf test-workspace test-logs
mkdir -p test-workspace test-logs

print_info "启动Docker容器..."
docker compose -f tests/docker-compose.test.yml up -d --build

print_info "等待服务就绪..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s -f "$REMOTE_CI_API/api/health" > /dev/null 2>&1; then
        print_success "远程CI服务已就绪"
        break
    fi
    sleep 1
    ((attempt++))
done

if [ $attempt -eq $max_attempts ]; then
    print_error "远程CI服务启动超时"
    docker compose -f tests/docker-compose.test.yml logs
    exit 1
fi

# ==========================================
# 步骤2: 测试API健康检查
# ==========================================

print_header "步骤2: 测试API健康检查"

response=$(curl -s "$REMOTE_CI_API/api/health")
status=$(echo "$response" | jq -r '.status')

if [ "$status" = "healthy" ]; then
    print_success "健康检查通过"
else
    print_error "健康检查失败: $response"
fi

# ==========================================
# 步骤3: 测试Upload模式
# ==========================================

print_header "步骤3: 测试Upload模式"

# 创建测试项目
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"
echo "console.log('Hello from upload mode');" > index.js
echo "#!/bin/bash" > test.sh
echo "echo 'Upload test passed'" >> test.sh
chmod +x test.sh

print_info "提交upload任务..."
export REMOTE_CI_API
export REMOTE_CI_TOKEN

job_response=$(python3 -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT/client')
from submit import RemoteCIClient

client = RemoteCIClient('$REMOTE_CI_API', '$REMOTE_CI_TOKEN')
result = client.upload_mode(
    script='bash test.sh',
    upload_path='.',
    project_name='test-upload',
    user_id='test-user'
)
" 2>&1 | grep "任务ID:" | awk '{print $2}')

if [ -n "$job_response" ]; then
    print_success "Upload任务已提交: $job_response"

    # 等待任务完成
    print_info "等待任务完成..."
    final_status=$(wait_for_job "$job_response")

    if [ "$final_status" = "success" ]; then
        print_success "Upload任务执行成功"
    else
        print_error "Upload任务执行失败: $final_status"
    fi
else
    print_error "Upload任务提交失败"
fi

cd "$OLDPWD"
rm -rf "$TEST_DIR"

# ==========================================
# 步骤4: 测试Rsync模式（用户隔离）
# ==========================================

print_header "步骤4: 测试Rsync模式（用户隔离）"

# 创建测试workspace
print_info "创建测试workspace..."
mkdir -p test-workspace/test-project-alice
echo "#!/bin/bash" > test-workspace/test-project-alice/build.sh
echo "echo 'Rsync test for Alice passed'" >> test-workspace/test-project-alice/build.sh
chmod +x test-workspace/test-project-alice/build.sh

# 提交rsync任务
print_info "提交rsync任务（user: alice）..."
curl -s -X POST "$REMOTE_CI_API/api/jobs/rsync" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "workspace": "/var/ci-workspace/test-project-alice",
        "script": "bash build.sh",
        "user": "alice",
        "user_id": "alice"
    }' > /tmp/rsync-job.json

job_id=$(jq -r '.job_id' /tmp/rsync-job.json)

if [ -n "$job_id" ] && [ "$job_id" != "null" ]; then
    print_success "Rsync任务已提交: $job_id"

    # 等待任务完成
    print_info "等待任务完成..."
    final_status=$(wait_for_job "$job_id")

    if [ "$final_status" = "success" ]; then
        print_success "Rsync任务执行成功"

        # 验证日志
        logs=$(curl -s -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
            "$REMOTE_CI_API/api/jobs/$job_id/logs")

        if echo "$logs" | grep -q "Rsync test for Alice passed"; then
            print_success "日志验证通过"
        else
            print_error "日志验证失败"
        fi
    else
        print_error "Rsync任务执行失败: $final_status"
    fi
else
    print_error "Rsync任务提交失败"
fi

# ==========================================
# 步骤5: 测试并发隔离
# ==========================================

print_header "步骤5: 测试并发隔离（多用户）"

# 创建Alice的workspace
mkdir -p test-workspace/test-project-alice
echo "#!/bin/bash" > test-workspace/test-project-alice/test.sh
echo "echo 'Alice workspace'" >> test-workspace/test-project-alice/test.sh
chmod +x test-workspace/test-project-alice/test.sh

# 创建Bob的workspace
mkdir -p test-workspace/test-project-bob
echo "#!/bin/bash" > test-workspace/test-project-bob/test.sh
echo "echo 'Bob workspace'" >> test-workspace/test-project-bob/test.sh
chmod +x test-workspace/test-project-bob/test.sh

# 同时提交Alice和Bob的任务
print_info "同时提交Alice和Bob的任务..."

alice_job=$(curl -s -X POST "$REMOTE_CI_API/api/jobs/rsync" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "workspace": "/var/ci-workspace/test-project-alice",
        "script": "bash test.sh",
        "user": "alice"
    }' | jq -r '.job_id')

bob_job=$(curl -s -X POST "$REMOTE_CI_API/api/jobs/rsync" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "workspace": "/var/ci-workspace/test-project-bob",
        "script": "bash test.sh",
        "user": "bob"
    }' | jq -r '.job_id')

# 等待两个任务完成
alice_status=$(wait_for_job "$alice_job")
bob_status=$(wait_for_job "$bob_job")

# 验证日志内容
alice_logs=$(curl -s -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    "$REMOTE_CI_API/api/jobs/$alice_job/logs")
bob_logs=$(curl -s -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    "$REMOTE_CI_API/api/jobs/$bob_job/logs")

if echo "$alice_logs" | grep -q "Alice workspace" && \
   echo "$bob_logs" | grep -q "Bob workspace"; then
    print_success "并发隔离验证通过（Alice和Bob的workspace完全隔离）"
else
    print_error "并发隔离验证失败"
    echo "Alice logs: $alice_logs"
    echo "Bob logs: $bob_logs"
fi

# ==========================================
# 步骤6: 测试Git模式
# ==========================================

print_header "步骤6: 测试Git模式"

print_info "提交Git克隆任务..."
git_job=$(curl -s -X POST "$REMOTE_CI_API/api/jobs/git" \
    -H "Authorization: Bearer $REMOTE_CI_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "repo": "https://github.com/octocat/Hello-World.git",
        "branch": "master",
        "script": "ls -la && echo Git test passed",
        "user": "test-user"
    }' | jq -r '.job_id')

if [ -n "$git_job" ] && [ "$git_job" != "null" ]; then
    print_success "Git任务已提交: $git_job"

    # 等待任务完成
    print_info "等待任务完成..."
    final_status=$(wait_for_job "$git_job")

    if [ "$final_status" = "success" ]; then
        print_success "Git任务执行成功"
    else
        print_error "Git任务执行失败: $final_status"
    fi
else
    print_error "Git任务提交失败"
fi

# ==========================================
# 步骤7: 测试统计API
# ==========================================

print_header "步骤7: 测试统计API"

stats=$(curl -s "$REMOTE_CI_API/api/stats")
total_jobs=$(echo "$stats" | jq -r '.total_jobs')

if [ -n "$total_jobs" ] && [ "$total_jobs" != "null" ]; then
    print_success "统计API工作正常（总任务数: $total_jobs）"
else
    print_error "统计API失败"
fi

# ==========================================
# 步骤8: 验证文件系统
# ==========================================

print_header "步骤8: 验证文件系统"

print_info "检查workspace目录..."
if [ -d "test-workspace/test-project-alice" ] && \
   [ -d "test-workspace/test-project-bob" ]; then
    print_success "Workspace目录结构正确"
    ls -la test-workspace/
else
    print_error "Workspace目录结构异常"
fi

print_info "检查日志文件..."
log_count=$(ls test-logs/*.log 2>/dev/null | wc -l)
if [ "$log_count" -gt 0 ]; then
    print_success "日志文件已生成（$log_count 个）"
else
    print_error "未找到日志文件"
fi

# ==========================================
# 测试总结
# ==========================================

print_header "测试总结"

echo "通过: $TESTS_PASSED"
echo "失败: $TESTS_FAILED"
echo

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================="
    echo "✓ 所有测试通过！"
    echo "==========================================${NC}"

    print_info "查看容器日志: docker compose -f tests/docker-compose.test.yml logs"
    print_info "停止环境: docker compose -f tests/docker-compose.test.yml down -v"

    exit 0
else
    echo -e "${RED}=========================================="
    echo "✗ 部分测试失败"
    echo "==========================================${NC}"

    print_info "查看容器日志: docker compose -f tests/docker-compose.test.yml logs"

    exit 1
fi
