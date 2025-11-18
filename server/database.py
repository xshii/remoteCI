#!/usr/bin/env python3
"""
SQLite数据库模块 - 任务历史记录
"""

import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
import threading

# 定义UTC+8时区
UTC8 = timezone(timedelta(hours=8))


class JobDatabase:
    """任务数据库管理类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def _get_conn(self):
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """初始化数据库表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ci_jobs (
                job_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                script TEXT NOT NULL,
                user_id TEXT,
                project_name TEXT,

                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                duration REAL,

                exit_code INTEGER,
                error_message TEXT,

                workspace TEXT,
                repo_url TEXT,
                branch TEXT,
                commit_hash TEXT,

                log_file TEXT,
                metadata TEXT
            )
        ''')

        # 数据库迁移：为已存在的表添加user_id字段
        try:
            cursor.execute("SELECT user_id FROM ci_jobs LIMIT 1")
        except sqlite3.OperationalError:
            # user_id字段不存在，添加它
            cursor.execute("ALTER TABLE ci_jobs ADD COLUMN user_id TEXT")
            print("✓ 数据库迁移: 添加user_id字段")

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON ci_jobs(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON ci_jobs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON ci_jobs(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_mode ON ci_jobs(mode)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_finished_at ON ci_jobs(finished_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_project_name ON ci_jobs(project_name)')

        conn.commit()
        conn.close()

        print(f"✓ 数据库初始化完成: {self.db_path}")

    def create_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        创建任务记录

        Args:
            job_id: 任务ID
            job_data: 任务数据，包含 mode, script, user_id, workspace, repo, branch 等

        Returns:
            bool: 是否创建成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO ci_jobs (
                    job_id, mode, status, script, user_id, project_name,
                    created_at, log_file, workspace, repo_url, branch, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_id,
                job_data.get('mode', 'unknown'),
                'queued',
                job_data.get('script', ''),
                job_data.get('user_id'),
                job_data.get('project_name', job_data.get('workspace', '').split('/')[-1] if job_data.get('workspace') else None),
                datetime.now(UTC8).isoformat(),
                job_data.get('log_file', ''),
                job_data.get('workspace'),
                job_data.get('repo'),
                job_data.get('branch'),
                json.dumps(job_data)
            ))

            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 创建任务记录失败: {e}")
            return False

    def update_job_started(self, job_id: str) -> bool:
        """
        更新任务为已开始状态

        Args:
            job_id: 任务ID

        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE ci_jobs
                SET status = 'running', started_at = ?
                WHERE job_id = ?
            ''', (datetime.now(UTC8).isoformat(), job_id))

            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 更新任务开始状态失败: {e}")
            return False

    def update_job_finished(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新任务为完成状态

        Args:
            job_id: 任务ID
            status: 最终状态 (success, failed, timeout, error)
            result: 任务结果，包含 exit_code, duration, error 等

        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            result = result or {}

            cursor.execute('''
                UPDATE ci_jobs
                SET status = ?,
                    finished_at = ?,
                    duration = ?,
                    exit_code = ?,
                    error_message = ?
                WHERE job_id = ?
            ''', (
                status,
                datetime.now(UTC8).isoformat(),
                result.get('duration'),
                result.get('exit_code'),
                result.get('error'),
                job_id
            ))

            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 更新任务完成状态失败: {e}")
            return False

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个任务信息

        Args:
            job_id: 任务ID

        Returns:
            任务信息字典，如果不存在返回None
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM ci_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except Exception as e:
            print(f"✗ 获取任务信息失败: {e}")
            return None

    def get_jobs(self, limit: int = 50, offset: int = 0, filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        查询任务列表

        Args:
            limit: 返回数量限制
            offset: 偏移量
            filters: 过滤条件，支持 status, user_id, mode, project_name

        Returns:
            任务列表
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            query = 'SELECT * FROM ci_jobs'
            params = []

            # 构建WHERE子句
            if filters:
                conditions = []
                if filters.get('status'):
                    conditions.append('status = ?')
                    params.append(filters['status'])
                if filters.get('user_id'):
                    # 支持部分匹配
                    conditions.append('user_id LIKE ?')
                    params.append(f"%{filters['user_id']}%")
                if filters.get('mode'):
                    conditions.append('mode = ?')
                    params.append(filters['mode'])
                if filters.get('project_name'):
                    # 支持部分匹配
                    conditions.append('project_name LIKE ?')
                    params.append(f"%{filters['project_name']}%")

                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)

            # 排序和分页
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"✗ 查询任务列表失败: {e}")
            return []

    def count_jobs(self, filters: Optional[Dict[str, str]] = None) -> int:
        """
        统计任务数量

        Args:
            filters: 过滤条件，支持 status, user_id, mode, project_name

        Returns:
            任务总数
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            query = 'SELECT COUNT(*) FROM ci_jobs'
            params = []

            if filters:
                conditions = []
                if filters.get('status'):
                    conditions.append('status = ?')
                    params.append(filters['status'])
                if filters.get('user_id'):
                    # 支持部分匹配
                    conditions.append('user_id LIKE ?')
                    params.append(f"%{filters['user_id']}%")
                if filters.get('mode'):
                    conditions.append('mode = ?')
                    params.append(filters['mode'])
                if filters.get('project_name'):
                    # 支持部分匹配
                    conditions.append('project_name LIKE ?')
                    params.append(f"%{filters['project_name']}%")

                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)

            cursor.execute(query, params)
            return cursor.fetchone()[0]

        except Exception as e:
            print(f"✗ 统计任务数量失败: {e}")
            return 0

    def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        获取统计数据

        Args:
            days: 统计最近几天的数据

        Returns:
            统计信息字典
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cutoff = (datetime.now(UTC8) - timedelta(days=days)).isoformat()

            # 总体统计
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_count,
                    SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued_count,
                    AVG(CASE WHEN duration IS NOT NULL THEN duration ELSE NULL END) as avg_duration
                FROM ci_jobs
                WHERE created_at > ?
            ''', (cutoff,))

            row = cursor.fetchone()

            total = row[0] or 0
            success_count = row[1] or 0
            failed_count = row[2] or 0

            stats = {
                'total': total,
                'success_count': success_count,
                'failed_count': failed_count,
                'running_count': row[3] or 0,
                'queued_count': row[4] or 0,
                'success_rate': round(success_count / total * 100, 2) if total > 0 else 0,
                'avg_duration': round(row[5], 2) if row[5] else 0,
                'days': days
            }

            # 按模式统计
            cursor.execute('''
                SELECT mode, COUNT(*) as count
                FROM ci_jobs
                WHERE created_at > ?
                GROUP BY mode
            ''', (cutoff,))

            stats['by_mode'] = {row[0]: row[1] for row in cursor.fetchall()}

            # 按用户ID统计
            cursor.execute('''
                SELECT user_id, COUNT(*) as count
                FROM ci_jobs
                WHERE created_at > ? AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 10
            ''', (cutoff,))

            stats['by_user_id'] = {row[0]: row[1] for row in cursor.fetchall()}

            return stats

        except Exception as e:
            print(f"✗ 获取统计数据失败: {e}")
            return {
                'total': 0,
                'success_count': 0,
                'failed_count': 0,
                'running_count': 0,
                'queued_count': 0,
                'success_rate': 0,
                'avg_duration': 0,
                'days': days,
                'by_mode': {},
                'by_user_id': {}
            }

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        清理旧的任务记录

        Args:
            days: 保留最近几天的记录

        Returns:
            删除的记录数量
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cutoff = (datetime.now(UTC8) - timedelta(days=days)).isoformat()

            cursor.execute('DELETE FROM ci_jobs WHERE created_at < ?', (cutoff,))
            deleted_count = cursor.rowcount

            conn.commit()

            print(f"✓ 清理了 {deleted_count} 条旧任务记录（>{days}天）")
            return deleted_count

        except Exception as e:
            print(f"✗ 清理旧任务记录失败: {e}")
            return 0


# 测试代码
if __name__ == '__main__':
    # 创建测试数据库
    db = JobDatabase('/tmp/test_ci_jobs.db')

    # 测试创建任务
    test_job_id = 'test-job-001'
    db.create_job(test_job_id, {
        'mode': 'upload',
        'script': 'npm test',
        'user_id': 'test-user-123',
        'log_file': f'/tmp/logs/{test_job_id}.log'
    })

    # 测试更新任务状态
    db.update_job_started(test_job_id)
    db.update_job_finished(test_job_id, 'success', {
        'duration': 123.45,
        'exit_code': 0
    })

    # 测试查询
    job = db.get_job(test_job_id)
    print(f"任务信息: {job}")

    jobs = db.get_jobs(limit=10)
    print(f"任务列表: 共 {len(jobs)} 条")

    stats = db.get_stats(days=7)
    print(f"统计数据: {stats}")

    print("\n✓ 所有测试通过")
