#!/usr/bin/env python3
"""
配额管理器
负责管理磁盘配额、自动清理超配额文件
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from server.database import JobDatabase
from server.config import DATA_DIR


class QuotaManager:
    """配额管理器"""

    # 总配额（字节）
    TOTAL_QUOTA_BYTES = 200 * 1024 * 1024 * 1024  # 200GB

    def __init__(self, db: JobDatabase, special_users_config: str = None):
        """
        初始化配额管理器

        Args:
            db: 数据库实例
            special_users_config: 特殊用户配置文件路径
        """
        self.db = db
        self.special_users_config = special_users_config or f"{DATA_DIR}/special_users.yml"

        # 启动时从配置文件加载特殊用户
        self.load_special_users_from_config()

    def load_special_users_from_config(self):
        """从配置文件加载特殊用户到数据库"""
        if not os.path.exists(self.special_users_config):
            print(f"⚠ 特殊用户配置文件不存在: {self.special_users_config}")
            self._create_default_config()
            return

        try:
            with open(self.special_users_config, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            special_users = config.get('special_users', [])

            if not special_users:
                print("⚠ 配置文件中没有特殊用户")
                return

            # 将配置文件中的用户同步到数据库
            for user_config in special_users:
                user_id = user_config.get('user_id')
                quota_gb = user_config.get('quota_gb', 50)

                if user_id:
                    self.db.add_special_user(user_id, quota_gb)
                    print(f"✓ 加载特殊用户: {user_id} (配额: {quota_gb}GB)")

        except Exception as e:
            print(f"✗ 加载特殊用户配置失败: {e}")

    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            'special_users': [
                {'user_id': 'admin', 'quota_gb': 50},
            ]
        }

        try:
            Path(self.special_users_config).parent.mkdir(parents=True, exist_ok=True)
            with open(self.special_users_config, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
            print(f"✓ 创建默认配置文件: {self.special_users_config}")
        except Exception as e:
            print(f"✗ 创建默认配置文件失败: {e}")

    def get_quota_info(self) -> Dict:
        """
        获取配额信息

        Returns:
            {
                'total_bytes': 总配额,
                'used_bytes': 已使用,
                'available_bytes': 可用,
                'special_users': [{user_id, quota_bytes, used_bytes}, ...],
                'normal_users_quota': 普通用户共享配额,
                'normal_users_used': 普通用户已使用
            }
        """
        # 获取所有特殊用户
        special_users = self.db.get_all_special_users()
        special_user_ids = {u['user_id'] for u in special_users}

        # 计算特殊用户配额总和
        special_quota_total = sum(u['quota_bytes'] for u in special_users)

        # 普通用户共享配额
        normal_quota = self.TOTAL_QUOTA_BYTES - special_quota_total

        # 计算特殊用户使用量
        special_users_info = []
        special_used_total = 0

        for user in special_users:
            user_id = user['user_id']
            used = self.db.calculate_disk_usage(user_id)
            special_users_info.append({
                'user_id': user_id,
                'quota_bytes': user['quota_bytes'],
                'used_bytes': used,
                'usage_percent': round(used / user['quota_bytes'] * 100, 2) if user['quota_bytes'] > 0 else 0
            })
            special_used_total += used

        # 计算普通用户使用量
        total_used = self.db.calculate_disk_usage()
        normal_used = total_used - special_used_total

        # 获取所有普通用户的使用情况
        normal_users_info = []
        try:
            conn = self.db._get_conn()
            cursor = conn.cursor()

            # 查询所有有任务的用户（排除特殊用户和 NULL）
            cursor.execute('''
                SELECT DISTINCT user_id
                FROM ci_jobs
                WHERE user_id IS NOT NULL AND is_expired = 0
            ''')
            all_users = {row[0] for row in cursor.fetchall()}

            # 过滤出普通用户
            normal_user_ids = all_users - special_user_ids

            # 计算每个普通用户的使用量
            for user_id in sorted(normal_user_ids):
                used = self.db.calculate_disk_usage(user_id)
                if used > 0:  # 只显示有使用量的用户
                    normal_users_info.append({
                        'user_id': user_id,
                        'used_bytes': used,
                        'usage_percent': round(used / normal_quota * 100, 2) if normal_quota > 0 else 0
                    })

            # 按使用量降序排序
            normal_users_info.sort(key=lambda x: x['used_bytes'], reverse=True)

        except Exception as e:
            print(f"✗ 获取普通用户信息失败: {e}")

        return {
            'total_bytes': self.TOTAL_QUOTA_BYTES,
            'used_bytes': total_used,
            'available_bytes': self.TOTAL_QUOTA_BYTES - total_used,
            'usage_percent': round(total_used / self.TOTAL_QUOTA_BYTES * 100, 2),
            'special_users': special_users_info,
            'normal_users_quota': normal_quota,
            'normal_users_used': normal_used,
            'normal_users_usage_percent': round(normal_used / normal_quota * 100, 2) if normal_quota > 0 else 0,
            'normal_users': normal_users_info
        }

    def check_and_cleanup(self, user_id: str = None) -> Tuple[bool, int]:
        """
        检查配额并清理超配额文件

        Args:
            user_id: 用户ID，None表示检查普通用户共享配额

        Returns:
            (是否需要清理, 清理的任务数)
        """
        # 判断是否为特殊用户
        special_user = self.db.get_special_user(user_id) if user_id else None

        if special_user:
            # 特殊用户：检查个人配额
            user_quota = special_user['quota_bytes']
            user_used = self.db.calculate_disk_usage(user_id)

            if user_used <= user_quota:
                return False, 0

            # 超配额，清理该用户的最老任务
            print(f"⚠ 特殊用户 {user_id} 超配额: {user_used}/{user_quota} 字节")
            return True, self._cleanup_user_jobs(user_id, user_used - user_quota)

        else:
            # 普通用户：检查共享配额
            quota_info = self.get_quota_info()
            normal_quota = quota_info['normal_users_quota']
            normal_used = quota_info['normal_users_used']

            if normal_used <= normal_quota:
                return False, 0

            # 超配额，清理所有普通用户的最老任务
            print(f"⚠ 普通用户共享配额超限: {normal_used}/{normal_quota} 字节")

            # 获取所有特殊用户ID
            special_users = self.db.get_all_special_users()
            special_user_ids = {u['user_id'] for u in special_users}

            return True, self._cleanup_normal_users_jobs(special_user_ids, normal_used - normal_quota)

    def _cleanup_user_jobs(self, user_id: str, bytes_to_free: int) -> int:
        """
        清理指定用户的任务

        Args:
            user_id: 用户ID
            bytes_to_free: 需要释放的字节数

        Returns:
            清理的任务数
        """
        freed_bytes = 0
        cleaned_count = 0

        while freed_bytes < bytes_to_free:
            # 获取最老的任务
            oldest_jobs = self.db.get_oldest_jobs(user_id=user_id, limit=1)

            if not oldest_jobs:
                print(f"⚠ 没有更多任务可清理（用户: {user_id}）")
                break

            job = oldest_jobs[0]
            job_id = job['job_id']

            # 删除任务的所有文件
            freed = self._delete_job_files(job)

            if freed > 0:
                # 标记为过期
                self.db.mark_job_expired(job_id)
                freed_bytes += freed
                cleaned_count += 1
                print(f"✓ 清理任务 {job_id} (释放 {freed} 字节)")

        print(f"✓ 共清理 {cleaned_count} 个任务，释放 {freed_bytes} 字节")
        return cleaned_count

    def _cleanup_normal_users_jobs(self, special_user_ids: set, bytes_to_free: int) -> int:
        """
        清理普通用户的任务

        Args:
            special_user_ids: 特殊用户ID集合
            bytes_to_free: 需要释放的字节数

        Returns:
            清理的任务数
        """
        freed_bytes = 0
        cleaned_count = 0

        while freed_bytes < bytes_to_free:
            # 获取所有用户的最老任务
            oldest_jobs = self.db.get_oldest_jobs(user_id=None, limit=10)

            if not oldest_jobs:
                print("⚠ 没有更多任务可清理")
                break

            # 过滤出普通用户的任务
            normal_user_jobs = [
                job for job in oldest_jobs
                if job.get('user_id') not in special_user_ids
            ]

            if not normal_user_jobs:
                print("⚠ 没有更多普通用户任务可清理")
                break

            # 删除最老的普通用户任务
            job = normal_user_jobs[0]
            job_id = job['job_id']

            freed = self._delete_job_files(job)

            if freed > 0:
                self.db.mark_job_expired(job_id)
                freed_bytes += freed
                cleaned_count += 1
                print(f"✓ 清理任务 {job_id} (释放 {freed} 字节)")

        print(f"✓ 共清理 {cleaned_count} 个任务，释放 {freed_bytes} 字节")
        return cleaned_count

    def _delete_job_files(self, job: Dict) -> int:
        """
        删除任务的所有文件

        Args:
            job: 任务信息

        Returns:
            释放的字节数
        """
        freed_bytes = 0

        # 删除日志文件
        log_file = job.get('log_file')
        if log_file and os.path.exists(log_file):
            try:
                size = os.path.getsize(log_file)
                os.remove(log_file)
                freed_bytes += size
            except Exception as e:
                print(f"✗ 删除日志文件失败 {log_file}: {e}")

        # 删除产物文件
        artifacts_path = job.get('artifacts_path')
        if artifacts_path and os.path.exists(artifacts_path):
            try:
                size = os.path.getsize(artifacts_path)
                os.remove(artifacts_path)
                freed_bytes += size
            except Exception as e:
                print(f"✗ 删除产物文件失败 {artifacts_path}: {e}")

        # 删除代码包文件
        code_archive_path = job.get('code_archive_path')
        if code_archive_path and os.path.exists(code_archive_path):
            try:
                size = os.path.getsize(code_archive_path)
                os.remove(code_archive_path)
                freed_bytes += size
            except Exception as e:
                print(f"✗ 删除代码包失败 {code_archive_path}: {e}")

        return freed_bytes

    def delete_job(self, job_id: str) -> bool:
        """
        删除指定任务的所有文件并标记为过期

        Args:
            job_id: 任务ID

        Returns:
            是否删除成功
        """
        job = self.db.get_job(job_id)
        if not job:
            return False

        freed = self._delete_job_files(job)
        self.db.mark_job_expired(job_id)

        print(f"✓ 删除任务 {job_id}，释放 {freed} 字节")
        return True


# 测试代码
if __name__ == '__main__':
    from server.config import DATA_DIR

    db = JobDatabase(f"{DATA_DIR}/jobs.db")
    manager = QuotaManager(db)

    # 测试获取配额信息
    info = manager.get_quota_info()
    print("配额信息:", info)

    # 测试检查配额
    need_cleanup, count = manager.check_and_cleanup()
    print(f"是否需要清理: {need_cleanup}, 清理任务数: {count}")
