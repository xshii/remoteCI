#!/usr/bin/env python3
"""
Celery应用初始化
"""

from celery import Celery
from server.config import CELERY_CONFIG

# 创建Celery应用
celery_app = Celery('remote_ci')
celery_app.config_from_object(CELERY_CONFIG)

# 自动发现任务
celery_app.autodiscover_tasks(['server'])

if __name__ == '__main__':
    celery_app.start()
