#!/usr/bin/env python3
"""
远程CI配置文件
支持rsync和HTTP上传两种模式
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础目录
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = os.getenv('CI_DATA_DIR', str(BASE_DIR / 'data'))
WORK_DIR = os.getenv('CI_WORK_DIR', '/tmp/remote-ci')
WORKSPACE_DIR = os.getenv('CI_WORKSPACE_DIR', '/var/ci-workspace')

# API配置
API_HOST = os.getenv('CI_API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('CI_API_PORT', '5000'))
API_TOKEN = os.getenv('CI_API_TOKEN', 'change-me-in-production')

# Celery配置
CELERY_BROKER_URL = os.getenv('CI_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CI_RESULT_BACKEND', 'redis://localhost:6379/0')

# 任务配置
MAX_CONCURRENT_JOBS = int(os.getenv('CI_MAX_CONCURRENT', '2'))
JOB_TIMEOUT = int(os.getenv('CI_JOB_TIMEOUT', '3600'))  # 1小时
LOG_RETENTION_DAYS = int(os.getenv('CI_LOG_RETENTION_DAYS', '7'))

# 上传文件大小限制（500MB）
MAX_UPLOAD_SIZE = 500 * 1024 * 1024

# Celery任务配置
CELERY_CONFIG = {
    'broker_url': CELERY_BROKER_URL,
    'result_backend': CELERY_RESULT_BACKEND,
    'task_serializer': 'msgpack',
    'result_serializer': 'msgpack',
    'accept_content': ['msgpack', 'json'],
    'timezone': 'Asia/Shanghai',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': JOB_TIMEOUT,
    'task_soft_time_limit': JOB_TIMEOUT - 60,
    'worker_prefetch_multiplier': 1,  # 每次只取一个任务，确保并发控制
    'worker_max_tasks_per_child': 10,  # 每10个任务重启worker，防止内存泄漏
    'result_expires': 86400 * LOG_RETENTION_DAYS,  # 结果保留时间
}

# 确保目录存在
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
Path(f"{DATA_DIR}/logs").mkdir(parents=True, exist_ok=True)
Path(f"{DATA_DIR}/uploads").mkdir(parents=True, exist_ok=True)
Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
Path(WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)
