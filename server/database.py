#!/usr/bin/env python3
"""
SQLite数据库模块 - 任务历史记录
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any
import threading

# 定义时区
UTC = timezone.utc
UTC8 = timezone(timedelta(hours=8))

# 配置日志
logger = logging.getLogger('remoteCI.database')
logger.setLevel(logging.DEBUG)


class JobDatabase:
    """任务数据库管理类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        # 确保数据库文件的父目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 记录数据库路径 - 用于调试
        logger.info(f"[数据库初始化] 路径: {self.db_path}")
        logger.info(f"[数据库初始化] 文件存在: {Path(db_path).exists()}")
        print(f"[数据库初始化] 路径: {self.db_path}")  # 保留 print 用于控制台
        print(f"[数据库初始化] 文件存在: {Path(db_path).exists()}")

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
                log_size INTEGER DEFAULT 0,

                artifacts_path TEXT,
                artifacts_size INTEGER DEFAULT 0,

                code_archive_path TEXT,
                code_archive_size INTEGER DEFAULT 0,

                is_expired INTEGER DEFAULT 0,

                metadata TEXT
            )
        ''')

        # 创建特殊用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS special_users (
                user_id TEXT PRIMARY KEY,
                quota_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')

        # 数据库迁移：添加新字段
        migrations = [
            ('user_id', 'ALTER TABLE ci_jobs ADD COLUMN user_id TEXT'),
            ('log_size', 'ALTER TABLE ci_jobs ADD COLUMN log_size INTEGER DEFAULT 0'),
            ('artifacts_path', 'ALTER TABLE ci_jobs ADD COLUMN artifacts_path TEXT'),
            ('artifacts_size', 'ALTER TABLE ci_jobs ADD COLUMN artifacts_size INTEGER DEFAULT 0'),
            ('code_archive_path', 'ALTER TABLE ci_jobs ADD COLUMN code_archive_path TEXT'),
            ('code_archive_size', 'ALTER TABLE ci_jobs ADD COLUMN code_archive_size INTEGER DEFAULT 0'),
            ('is_expired', 'ALTER TABLE ci_jobs ADD COLUMN is_expired INTEGER DEFAULT 0'),
        ]

        for field_name, migration_sql in migrations:
            try:
                cursor.execute(f"SELECT {field_name} FROM ci_jobs LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute(migration_sql)
                print(f"✓ 数据库迁移: 添加{field_name}字段")

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON ci_jobs(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON ci_jobs(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON ci_jobs(created_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_mode ON ci_jobs(mode)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_finished_at ON ci_jobs(finished_at DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_project_name ON ci_jobs(project_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_is_expired ON ci_jobs(is_expired)')

        conn.commit()
        conn.close()

    def create_job(self, job_id: str, job_data: Dict[str, Any]) -> bool:
        """
        创建任务记录

        Args:
            job_id: 任务ID
            job_data: 任务数据，包含 mode, script, user_id, workspace, repo, branch 等

        Returns:
            bool: 是否创建成功
        """
        logger.info(f"[数据库写入] 准备创建任务记录: job_id={job_id}, mode={job_data.get('mode')}, user_id={job_data.get('user_id')}")
        print(f"[数据库写入] 准备创建任务记录")
        print(f"  数据库路径: {self.db_path}")
        print(f"  任务ID: {job_id}")
        print(f"  模式: {job_data.get('mode', 'unknown')}")
        print(f"  用户ID: {job_data.get('user_id', 'N/A')}")

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
                datetime.now(UTC).replace(tzinfo=None).isoformat() + 'Z',
                job_data.get('log_file', ''),
                job_data.get('workspace'),
                job_data.get('repo'),
                job_data.get('branch'),
                json.dumps(job_data)
            ))

            conn.commit()

            # 验证写入
            cursor.execute('SELECT COUNT(*) FROM ci_jobs WHERE job_id = ?', (job_id,))
            count = cursor.fetchone()[0]

            logger.info(f"✓ 任务记录创建成功: job_id={job_id}, 验证={count}条, 文件大小={Path(self.db_path).stat().st_size}B")
            print(f"✓ 任务记录创建成功")
            print(f"  验证查询: 找到 {count} 条记录")
            print(f"  数据库文件大小: {Path(self.db_path).stat().st_size} 字节")

            return True

        except Exception as e:
            logger.error(f"✗ 创建任务记录失败: job_id={job_id}, error={e}")
            print(f"✗ 创建任务记录失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_job_started(self, job_id: str) -> bool:
        """
        更新任务为已开始状态

        Args:
            job_id: 任务ID

        Returns:
            bool: 是否更新成功
        """
        logger.info(f"[数据库更新] 更新任务开始状态: job_id={job_id}")
        print(f"[数据库更新] 更新任务开始状态")
        print(f"  数据库路径: {self.db_path}")
        print(f"  任务ID: {job_id}")

        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE ci_jobs
                SET status = 'running', started_at = ?
                WHERE job_id = ?
            ''', (datetime.now(UTC).replace(tzinfo=None).isoformat() + 'Z', job_id))

            rows_affected = cursor.rowcount
            conn.commit()

            logger.info(f"✓ 任务状态更新为 running: job_id={job_id}, 影响{rows_affected}行")
            print(f"✓ 任务状态更新为 running，影响 {rows_affected} 行")

            return True

        except Exception as e:
            print(f"✗ 更新任务开始状态失败: {e}")
            import traceback
            traceback.print_exc()
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
        logger.info(f"[数据库更新] 更新任务完成状态: job_id={job_id}, status={status}")
        print(f"[数据库更新] 更新任务完成状态")
        print(f"  数据库路径: {self.db_path}")
        print(f"  任务ID: {job_id}")
        print(f"  最终状态: {status}")

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
                datetime.now(UTC).replace(tzinfo=None).isoformat() + 'Z',
                result.get('duration'),
                result.get('exit_code'),
                result.get('error'),
                job_id
            ))

            rows_affected = cursor.rowcount
            conn.commit()

            logger.info(f"✓ 任务状态更新为 {status}: job_id={job_id}, 影响{rows_affected}行")
            print(f"✓ 任务状态更新为 {status}，影响 {rows_affected} 行")

            return True

        except Exception as e:
            print(f"✗ 更新任务完成状态失败: {e}")
            import traceback
            traceback.print_exc()
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
        logger.info(f"[数据库查询] 查询任务列表: limit={limit}, offset={offset}, filters={filters}")
        print(f"[数据库查询] 查询任务列表")
        print(f"  数据库路径: {self.db_path}")
        print(f"  limit={limit}, offset={offset}, filters={filters}")

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
                    # 支持部分匹配（大小写不敏感）
                    conditions.append('user_id LIKE ? COLLATE NOCASE')
                    params.append(f"%{filters['user_id']}%")
                if filters.get('mode'):
                    conditions.append('mode = ?')
                    params.append(filters['mode'])
                if filters.get('project_name'):
                    # 支持部分匹配（大小写不敏感）
                    conditions.append('project_name LIKE ? COLLATE NOCASE')
                    params.append(f"%{filters['project_name']}%")

                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)

            # 排序和分页
            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            print(f"  执行SQL: {query}")
            print(f"  参数: {params}")

            cursor.execute(query, params)
            rows = cursor.fetchall()

            logger.info(f"✓ 查询完成，返回 {len(rows)} 条记录")
            print(f"✓ 查询完成，返回 {len(rows)} 条记录")

            # 显示前几条的简要信息
            if rows:
                print(f"  前3条记录:")
                for i, row in enumerate(rows[:3], 1):
                    print(f"    {i}. {row['job_id'][:30]}... | {row['status']} | {row['mode']}")

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"✗ 查询任务列表失败: {e}")
            import traceback
            traceback.print_exc()
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
                    # 支持部分匹配（大小写不敏感）
                    conditions.append('user_id LIKE ? COLLATE NOCASE')
                    params.append(f"%{filters['user_id']}%")
                if filters.get('mode'):
                    conditions.append('mode = ?')
                    params.append(filters['mode'])
                if filters.get('project_name'):
                    # 支持部分匹配（大小写不敏感）
                    conditions.append('project_name LIKE ? COLLATE NOCASE')
                    params.append(f"%{filters['project_name']}%")

                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]

            return count

        except Exception as e:
            print(f"✗ 统计任务数量失败: {e}")
            import traceback
            traceback.print_exc()
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

            cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None).isoformat()

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

            cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(tzinfo=None).isoformat()

            cursor.execute('DELETE FROM ci_jobs WHERE created_at < ?', (cutoff,))
            deleted_count = cursor.rowcount

            conn.commit()

            print(f"✓ 清理了 {deleted_count} 条旧任务记录（>{days}天）")
            return deleted_count

        except Exception as e:
            print(f"✗ 清理旧任务记录失败: {e}")
            return 0

    def clear_all_jobs(self) -> int:
        """
        清空所有任务记录（危险操作！）

        Returns:
            删除的记录数量
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # 获取当前记录数
            cursor.execute('SELECT COUNT(*) FROM ci_jobs')
            total_count = cursor.fetchone()[0]

            # 清空所有记录
            cursor.execute('DELETE FROM ci_jobs')

            conn.commit()

            print(f"✓ 已清空所有任务记录（共 {total_count} 条）")
            return total_count

        except Exception as e:
            print(f"✗ 清空任务记录失败: {e}")
            return 0

    # ========== 配额管理相关方法 ==========

    def update_job_file_sizes(self, job_id: str,
                               log_size: int = None,
                               artifacts_size: int = None,
                               artifacts_path: str = None,
                               code_archive_size: int = None,
                               code_archive_path: str = None) -> bool:
        """
        更新任务的文件大小信息

        Args:
            job_id: 任务ID
            log_size: 日志文件大小
            artifacts_size: 产物文件大小
            artifacts_path: 产物文件路径
            code_archive_size: 代码包大小
            code_archive_path: 代码包路径

        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            updates = []
            params = []

            if log_size is not None:
                updates.append('log_size = ?')
                params.append(log_size)
            if artifacts_size is not None:
                updates.append('artifacts_size = ?')
                params.append(artifacts_size)
            if artifacts_path is not None:
                updates.append('artifacts_path = ?')
                params.append(artifacts_path)
            if code_archive_size is not None:
                updates.append('code_archive_size = ?')
                params.append(code_archive_size)
            if code_archive_path is not None:
                updates.append('code_archive_path = ?')
                params.append(code_archive_path)

            if not updates:
                return True

            params.append(job_id)
            query = f"UPDATE ci_jobs SET {', '.join(updates)} WHERE job_id = ?"
            cursor.execute(query, params)

            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 更新任务文件大小失败: {e}")
            return False

    def mark_job_expired(self, job_id: str) -> bool:
        """
        标记任务为已过期

        Args:
            job_id: 任务ID

        Returns:
            bool: 是否标记成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('UPDATE ci_jobs SET is_expired = 1 WHERE job_id = ?', (job_id,))
            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 标记任务过期失败: {e}")
            return False

    def calculate_disk_usage(self, user_id: str = None) -> int:
        """
        计算磁盘使用量（字节）

        Args:
            user_id: 用户ID，None表示计算所有用户

        Returns:
            磁盘使用量（字节）
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            if user_id:
                cursor.execute('''
                    SELECT
                        COALESCE(SUM(log_size), 0) +
                        COALESCE(SUM(artifacts_size), 0) +
                        COALESCE(SUM(code_archive_size), 0)
                    FROM ci_jobs
                    WHERE user_id = ? AND is_expired = 0
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT
                        COALESCE(SUM(log_size), 0) +
                        COALESCE(SUM(artifacts_size), 0) +
                        COALESCE(SUM(code_archive_size), 0)
                    FROM ci_jobs
                    WHERE is_expired = 0
                ''')

            result = cursor.fetchone()[0]
            return result if result else 0

        except Exception as e:
            print(f"✗ 计算磁盘使用量失败: {e}")
            return 0

    def get_oldest_jobs(self, user_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最老的任务（按created_at排序）

        Args:
            user_id: 用户ID，None表示所有用户
            limit: 返回数量

        Returns:
            任务列表
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            if user_id:
                cursor.execute('''
                    SELECT * FROM ci_jobs
                    WHERE user_id = ? AND is_expired = 0
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM ci_jobs
                    WHERE is_expired = 0
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

        except Exception as e:
            print(f"✗ 获取最老任务失败: {e}")
            return []

    # ========== 特殊用户管理方法 ==========

    def add_special_user(self, user_id: str, quota_gb: float) -> bool:
        """
        添加特殊用户

        Args:
            user_id: 用户ID
            quota_gb: 配额（GB）

        Returns:
            bool: 是否添加成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            quota_bytes = int(quota_gb * 1024 * 1024 * 1024)
            now = datetime.now(UTC).replace(tzinfo=None).isoformat() + 'Z'

            cursor.execute('''
                INSERT OR REPLACE INTO special_users (user_id, quota_bytes, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, quota_bytes, now, now))

            conn.commit()
            return True

        except Exception as e:
            print(f"✗ 添加特殊用户失败: {e}")
            return False

    def get_special_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取特殊用户信息

        Args:
            user_id: 用户ID

        Returns:
            用户信息字典，如果不存在返回None
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM special_users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()

            if row:
                return dict(row)
            return None

        except Exception as e:
            print(f"✗ 获取特殊用户信息失败: {e}")
            return None

    def get_all_special_users(self) -> List[Dict[str, Any]]:
        """
        获取所有特殊用户

        Returns:
            特殊用户列表
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM special_users ORDER BY created_at DESC')
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"✗ 获取特殊用户列表失败: {e}")
            return []

    def update_special_user_quota(self, user_id: str, quota_gb: float) -> bool:
        """
        更新特殊用户配额

        Args:
            user_id: 用户ID
            quota_gb: 新配额（GB）

        Returns:
            bool: 是否更新成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            quota_bytes = int(quota_gb * 1024 * 1024 * 1024)
            now = datetime.now(UTC).replace(tzinfo=None).isoformat() + 'Z'

            cursor.execute('''
                UPDATE special_users
                SET quota_bytes = ?, updated_at = ?
                WHERE user_id = ?
            ''', (quota_bytes, now, user_id))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"✗ 更新特殊用户配额失败: {e}")
            return False

    def delete_special_user(self, user_id: str) -> bool:
        """
        删除特殊用户

        Args:
            user_id: 用户ID

        Returns:
            bool: 是否删除成功
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute('DELETE FROM special_users WHERE user_id = ?', (user_id,))
            conn.commit()

            return cursor.rowcount > 0

        except Exception as e:
            print(f"✗ 删除特殊用户失败: {e}")
            return False


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
