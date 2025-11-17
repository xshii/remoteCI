#!/bin/bash
# 测试workspace隔离功能

set -e

echo "=========================================="
echo "测试 Workspace 隔离功能"
echo "=========================================="
echo

# 检查环境
if [ ! -f "submit.py" ]; then
    echo "错误: 请在 client/ 目录下运行此脚本"
    exit 1
fi

# 测试1：自动检测用户
echo "测试1: 自动用户检测"
echo "当前系统用户: $USER"
python3 submit.py rsync test-project "echo 'test'" --help | grep -A 5 "Rsync模式" || true
echo

# 测试2: 手动指定用户
echo "测试2: 手动指定用户ID"
export REMOTE_CI_USER_ID="alice"
python3 -c "
import sys
sys.path.insert(0, '.')
from submit import detect_user_id, generate_workspace_name

user_id = detect_user_id()
print(f'检测到用户: {user_id}')

workspace = generate_workspace_name('myproject', user_id=user_id)
print(f'Workspace: {workspace}')
"
echo

# 测试3: UUID模式
echo "测试3: UUID模式"
python3 -c "
import sys
sys.path.insert(0, '.')
from submit import generate_workspace_name

workspace1 = generate_workspace_name('myproject', use_uuid=True)
workspace2 = generate_workspace_name('myproject', use_uuid=True)

print(f'UUID 1: {workspace1}')
print(f'UUID 2: {workspace2}')
print(f'唯一性: {\"✓ 通过\" if workspace1 != workspace2 else \"✗ 失败\"}')
"
echo

# 测试4: 多种CI环境变量
echo "测试4: 模拟不同CI系统"

# GitLab CI
export GITLAB_USER_LOGIN="bob"
python3 -c "
import sys, os
sys.path.insert(0, '.')
from submit import detect_user_id
print(f'GitLab CI: {detect_user_id()}')
"

# GitHub Actions
unset GITLAB_USER_LOGIN
export GITHUB_ACTOR="charlie"
python3 -c "
import sys, os
sys.path.insert(0, '.')
from submit import detect_user_id
print(f'GitHub Actions: {detect_user_id()}')
"

# Jenkins
unset GITHUB_ACTOR
export BUILD_USER="dave"
python3 -c "
import sys, os
sys.path.insert(0, '.')
from submit import detect_user_id
print(f'Jenkins: {detect_user_id()}')
"
echo

# 测试5: 显示帮助信息
echo "测试5: 查看新增参数"
python3 submit.py rsync --help | grep -E "(--uuid|--no-user-suffix)" || true
echo

echo "=========================================="
echo "✓ 所有测试完成"
echo "=========================================="
echo
echo "使用方法："
echo "  python3 submit.py rsync myproject 'make'           # 自动用户隔离"
echo "  python3 submit.py rsync myproject 'make' --uuid    # UUID隔离"
echo "  python3 submit.py rsync myproject 'make' --user-id bob  # 指定用户"
echo
