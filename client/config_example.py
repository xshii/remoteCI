#!/usr/bin/env python3
"""
Remote CI 客户端配置文件示例

使用方法:
1. 复制此文件为 config.py
2. 修改下面的配置项
3. 在脚本中导入: from config import *

或者直接设置环境变量:
  export REMOTE_CI_API="http://192.168.1.100:5000"
  export REMOTE_CI_TOKEN="your-secret-token"
"""

# ============================================
# 远程CI服务器配置
# ============================================

# 远程CI服务器SSH地址（rsync模式使用）
REMOTE_CI_HOST = "ci-user@192.168.1.100"

# 远程CI API地址
REMOTE_CI_API = "http://192.168.1.100:5000"

# API认证Token
# 警告: 请勿将Token提交到版本控制系统
# 建议使用环境变量或CI系统的Secret功能
REMOTE_CI_TOKEN = "your-secret-token-here"

# Workspace基础目录（rsync模式使用）
WORKSPACE_BASE = "/var/ci-workspace"

# 等待超时时间（秒）默认25分钟
CI_TIMEOUT = 1500


# ============================================
# 高级配置
# ============================================

# 轮询间隔（秒）
POLL_INTERVAL = 10

# 请求超时（秒）
REQUEST_TIMEOUT = 30

# 重试次数
MAX_RETRIES = 3


# ============================================
# 环境变量覆盖
# ============================================
# 如果设置了环境变量，优先使用环境变量的值

import os

REMOTE_CI_HOST = os.environ.get('REMOTE_CI_HOST', REMOTE_CI_HOST)
REMOTE_CI_API = os.environ.get('REMOTE_CI_API', REMOTE_CI_API)
REMOTE_CI_TOKEN = os.environ.get('REMOTE_CI_TOKEN', REMOTE_CI_TOKEN)
WORKSPACE_BASE = os.environ.get('WORKSPACE_BASE', WORKSPACE_BASE)
CI_TIMEOUT = int(os.environ.get('CI_TIMEOUT', str(CI_TIMEOUT)))


# ============================================
# 验证配置
# ============================================

def validate_config():
    """验证配置是否正确"""
    issues = []

    if REMOTE_CI_TOKEN == "your-secret-token-here":
        issues.append("⚠ 警告: 请设置正确的 REMOTE_CI_TOKEN")

    if REMOTE_CI_API == "http://192.168.1.100:5000":
        issues.append("⚠ 提示: 请修改 REMOTE_CI_API 为实际的服务器地址")

    if REMOTE_CI_HOST == "ci-user@192.168.1.100":
        issues.append("⚠ 提示: 请修改 REMOTE_CI_HOST 为实际的SSH地址")

    return issues


if __name__ == '__main__':
    print("Remote CI 配置检查")
    print("=" * 50)
    print(f"REMOTE_CI_HOST    = {REMOTE_CI_HOST}")
    print(f"REMOTE_CI_API     = {REMOTE_CI_API}")
    print(f"REMOTE_CI_TOKEN   = {REMOTE_CI_TOKEN[:10]}..." if len(REMOTE_CI_TOKEN) > 10 else f"REMOTE_CI_TOKEN   = {REMOTE_CI_TOKEN}")
    print(f"WORKSPACE_BASE    = {WORKSPACE_BASE}")
    print(f"CI_TIMEOUT        = {CI_TIMEOUT}s")
    print("=" * 50)

    issues = validate_config()
    if issues:
        print("\n配置问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n✓ 配置检查通过")
