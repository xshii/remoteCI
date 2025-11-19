#!/usr/bin/env python3
"""
数据库内容查看工具 (Python版本)
用于读取和分析 Remote CI 数据库内容
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import json


def find_database():
    """自动查找数据库文件"""
    search_paths = [
        "/home/user/remoteCI/data/jobs.db",
        "/tmp/remote-ci/jobs.db",
        "/var/lib/remote-ci/jobs.db",
        os.path.expanduser("~/.remote-ci/jobs.db"),
    ]

    # 先检查常见位置
    for path in search_paths:
        if os.path.exists(path):
            return path

    # 搜索项目目录
    try:
        for root, dirs, files in os.walk("/home/user/remoteCI"):
            for file in files:
                if file == "jobs.db":
                    return os.path.join(root, file)
    except Exception:
        pass

    return None


def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def read_database(db_path):
    """读取并显示数据库内容"""

    if not os.path.exists(db_path):
        print(f"✗ 错误: 数据库文件不存在: {db_path}")
        return

    print("=" * 80)
    print("Remote CI 数据库内容查看工具 (Python)")
    print("=" * 80)
    print()

    # 显示文件信息
    stat = os.stat(db_path)
    print("数据库信息:")
    print(f"  文件路径: {db_path}")
    print(f"  文件大小: {format_size(stat.st_size)}")
    print(f"  修改时间: {datetime.fromtimestamp(stat.st_mtime)}")
    print()

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"数据库表: {', '.join(tables)}")
        print()

        if 'ci_jobs' not in tables:
            print("✗ 错误: ci_jobs 表不存在")
            return

        # 2. 任务统计
        print("=" * 80)
        print("任务统计")
        print("=" * 80)

        cursor.execute("SELECT COUNT(*) FROM ci_jobs")
        total = cursor.fetchone()[0]
        print(f"总任务数: {total}")
        print()

        if total == 0:
            print("数据库为空，没有任务记录")
            return

        # 按状态统计
        print("按状态统计:")
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM ci_jobs
            GROUP BY status
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            status_icons = {
                'success': '✓',
                'failed': '✗',
                'running': '▶',
                'queued': '⏳',
                'timeout': '⏱',
                'error': '⚠'
            }
            icon = status_icons.get(row['status'], '•')
            print(f"  {icon} {row['status']:10} : {row['count']:5}")
        print()

        # 按模式统计
        print("按模式统计:")
        cursor.execute("""
            SELECT mode, COUNT(*) as count
            FROM ci_jobs
            GROUP BY mode
            ORDER BY count DESC
        """)
        for row in cursor.fetchall():
            print(f"  • {row['mode']:10} : {row['count']:5}")
        print()

        # 按用户统计
        print("按用户统计 (Top 10):")
        cursor.execute("""
            SELECT COALESCE(user_id, '(未设置)') as user_id, COUNT(*) as count
            FROM ci_jobs
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"  • {row['user_id']:20} : {row['count']:5}")
        print()

        # 3. 最近的任务
        print("=" * 80)
        print("最近的任务 (最新10条)")
        print("=" * 80)

        cursor.execute("""
            SELECT job_id, status, mode, user_id, project_name, created_at
            FROM ci_jobs
            ORDER BY created_at DESC
            LIMIT 10
        """)

        print(f"{'Job ID':<25} {'状态':<10} {'模式':<8} {'用户':<15} {'项目':<15} {'创建时间':<20}")
        print("-" * 110)

        for row in cursor.fetchall():
            job_id = row['job_id'][:22] + '...' if row['job_id'] else 'N/A'
            status = row['status'] or 'N/A'
            mode = row['mode'] or 'N/A'
            user_id = row['user_id'][:12] + '...' if row['user_id'] and len(row['user_id']) > 15 else (row['user_id'] or 'N/A')
            project = row['project_name'][:12] + '...' if row['project_name'] and len(row['project_name']) > 15 else (row['project_name'] or 'N/A')
            created = row['created_at'][:19] if row['created_at'] else 'N/A'

            print(f"{job_id:<25} {status:<10} {mode:<8} {user_id:<15} {project:<15} {created:<20}")
        print()

        # 4. 最新任务详情
        print("=" * 80)
        print("最新任务详情")
        print("=" * 80)

        cursor.execute("SELECT * FROM ci_jobs ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()

        if row:
            print(f"任务ID:        {row['job_id']}")
            print(f"状态:          {row['status']}")
            print(f"模式:          {row['mode']}")
            print(f"用户ID:        {row['user_id'] or 'N/A'}")
            print(f"项目名:        {row['project_name'] or 'N/A'}")
            print(f"脚本:          {row['script'][:60]}..." if row['script'] and len(row['script']) > 60 else f"脚本:          {row['script']}")
            print(f"创建时间:      {row['created_at']}")
            print(f"开始时间:      {row['started_at'] or 'N/A'}")
            print(f"结束时间:      {row['finished_at'] or 'N/A'}")
            print(f"耗时:          {row['duration']:.2f}秒" if row['duration'] else "耗时:          N/A")
            print(f"退出码:        {row['exit_code'] if row['exit_code'] is not None else 'N/A'}")
            print(f"日志文件:      {row['log_file'] or 'N/A'}")
            print(f"日志大小:      {format_size(row['log_size']) if row['log_size'] else 'N/A'}")

            if row['artifacts_path']:
                print(f"产物路径:      {row['artifacts_path']}")
                print(f"产物大小:      {format_size(row['artifacts_size'])}")

            if row['error_message']:
                print(f"错误信息:      {row['error_message']}")
        print()

        # 5. 运行中的任务
        print("=" * 80)
        print("运行中的任务")
        print("=" * 80)

        cursor.execute("""
            SELECT job_id, status, mode, user_id, created_at
            FROM ci_jobs
            WHERE status IN ('queued', 'running')
            ORDER BY created_at DESC
        """)

        running = cursor.fetchall()
        if running:
            print(f"{'Job ID':<25} {'状态':<10} {'模式':<8} {'用户':<15} {'创建时间':<20}")
            print("-" * 80)
            for row in running:
                job_id = row['job_id'][:22] + '...' if row['job_id'] else 'N/A'
                status = row['status'] or 'N/A'
                mode = row['mode'] or 'N/A'
                user_id = row['user_id'][:12] + '...' if row['user_id'] and len(row['user_id']) > 15 else (row['user_id'] or 'N/A')
                created = row['created_at'][:19] if row['created_at'] else 'N/A'

                print(f"{job_id:<25} {status:<10} {mode:<8} {user_id:<15} {created:<20}")
        else:
            print("（无运行中的任务）")
        print()

        # 6. 特殊用户配额
        if 'special_users' in tables:
            print("=" * 80)
            print("特殊用户配额")
            print("=" * 80)

            cursor.execute("SELECT * FROM special_users ORDER BY created_at DESC")
            special_users = cursor.fetchall()

            if special_users:
                print(f"{'用户ID':<20} {'配额':<15} {'创建时间':<20}")
                print("-" * 60)
                for row in special_users:
                    quota_gb = row['quota_bytes'] / (1024 * 1024 * 1024)
                    print(f"{row['user_id']:<20} {quota_gb:.2f} GB{'':<8} {row['created_at'][:19]}")
            else:
                print("（无特殊用户）")
            print()

        conn.close()

        # 7. 使用提示
        print("=" * 80)
        print("交互式查询")
        print("=" * 80)
        print(f"如需进行自定义查询，可以运行:")
        print(f"  sqlite3 {db_path}")
        print()
        print("或者使用 Python:")
        print("  import sqlite3")
        print(f"  conn = sqlite3.connect('{db_path}')")
        print("  cursor = conn.cursor()")
        print("  cursor.execute('SELECT * FROM ci_jobs WHERE status = \"failed\"')")
        print()

    except sqlite3.Error as e:
        print(f"✗ 数据库错误: {e}")
    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        print("正在搜索数据库文件...")
        db_path = find_database()

        if not db_path:
            print("✗ 未找到数据库文件")
            print()
            print("使用方法:")
            print(f"  {sys.argv[0]} /path/to/jobs.db")
            print()
            print("或者将数据库放在以下位置之一:")
            print("  - /home/user/remoteCI/data/jobs.db")
            print("  - /tmp/remote-ci/jobs.db")
            sys.exit(1)

        print(f"✓ 找到数据库: {db_path}")
        print()

    read_database(db_path)


if __name__ == '__main__':
    main()
