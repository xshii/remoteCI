#!/usr/bin/env python3
"""
全面扫描并对比所有数据库文件
找出哪个数据库有数据
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("全面扫描所有数据库文件")
print("=" * 80)
print()

# 扩展搜索路径
search_locations = [
    "/home/user/remoteCI",
    "/tmp",
    "/var",
    "/root",
    os.path.expanduser("~"),
]

db_files = []

print("正在搜索数据库文件...")
for location in search_locations:
    try:
        for root, dirs, files in os.walk(location):
            # 跳过一些明显不相关的目录
            if any(skip in root for skip in ['/proc', '/sys', '/dev', '/snap', '.git']):
                continue

            for file in files:
                if file.endswith('.db') and 'jobs' in file.lower():
                    full_path = os.path.join(root, file)
                    db_files.append(full_path)
                    print(f"  找到: {full_path}")
    except (PermissionError, OSError):
        pass

print()

if not db_files:
    print("✗ 没有找到任何数据库文件")
    print()
    print("可能的原因:")
    print("  1. 系统还未初始化运行过")
    print("  2. 数据库在搜索范围之外")
    print("  3. 数据库名称不包含 'jobs'")
    print()
    exit(1)

print(f"✓ 共找到 {len(db_files)} 个相关数据库文件")
print()

print("=" * 80)
print("分析每个数据库文件")
print("=" * 80)
print()

results = []

for db_path in db_files:
    print(f"分析: {db_path}")
    print("-" * 80)

    try:
        # 文件信息
        stat = os.stat(db_path)
        size = stat.st_size
        mtime = datetime.fromtimestamp(stat.st_mtime)

        print(f"  文件大小: {size:,} bytes ({size / 1024:.2f} KB)")
        print(f"  修改时间: {mtime}")

        # 尝试连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"  表: {', '.join(tables) if tables else '(无)'}")

        # 统计数据
        job_count = 0
        special_user_count = 0

        if 'ci_jobs' in tables:
            cursor.execute("SELECT COUNT(*) FROM ci_jobs")
            job_count = cursor.fetchone()[0]
            print(f"  任务数量: {job_count}")

            if job_count > 0:
                # 显示统计
                cursor.execute("SELECT status, COUNT(*) FROM ci_jobs GROUP BY status")
                status_stats = cursor.fetchall()
                print(f"  按状态统计:")
                for status, count in status_stats:
                    print(f"    - {status}: {count}")

                # 最新任务
                cursor.execute("SELECT job_id, status, created_at FROM ci_jobs ORDER BY created_at DESC LIMIT 1")
                latest = cursor.fetchone()
                if latest:
                    print(f"  最新任务: {latest[0][:30]}... ({latest[1]}) @ {latest[2][:19]}")

        if 'special_users' in tables:
            cursor.execute("SELECT COUNT(*) FROM special_users")
            special_user_count = cursor.fetchone()[0]
            print(f"  特殊用户数: {special_user_count}")

        conn.close()

        results.append({
            'path': db_path,
            'size': size,
            'mtime': mtime,
            'job_count': job_count,
            'special_user_count': special_user_count,
            'has_data': job_count > 0 or special_user_count > 0
        })

        print()

    except Exception as e:
        print(f"  ✗ 错误: {e}")
        print()

# 总结
print("=" * 80)
print("总结")
print("=" * 80)
print()

has_data_dbs = [r for r in results if r['has_data']]
empty_dbs = [r for r in results if not r['has_data']]

if not has_data_dbs:
    print("✗ 所有数据库都是空的！")
    print()
    print("这说明:")
    print("  1. 可能还没有提交过任务")
    print("  2. 或者任务数据在未被发现的数据库文件中")
    print()
    print("建议:")
    print("  1. 提交一个测试任务")
    print("  2. 检查 Flask 和 Celery 的启动日志，看它们使用的数据库路径")
    print("  3. 使用 strace 或 lsof 追踪进程打开的文件")
    print()

elif len(has_data_dbs) == 1:
    db = has_data_dbs[0]
    print(f"✓ 找到包含数据的数据库: {db['path']}")
    print(f"  任务数: {db['job_count']}")
    print(f"  特殊用户数: {db['special_user_count']}")
    print(f"  最后修改: {db['mtime']}")
    print()

    if empty_dbs:
        print(f"⚠ 同时发现 {len(empty_dbs)} 个空数据库:")
        for db in empty_dbs:
            print(f"  - {db['path']}")
        print()
        print("建议:")
        print(f"  1. 设置环境变量 CI_DATA_DIR={os.path.dirname(has_data_dbs[0]['path'])}")
        print("  2. 确保 Flask 和 Celery Worker 都使用此环境变量")
        print("  3. 考虑删除空的数据库文件以避免混淆")
        print()

else:
    print(f"✗ 警告: 发现 {len(has_data_dbs)} 个包含数据的数据库！")
    print()
    print("这可能导致数据不一致问题。数据库列表:")
    print()
    for i, db in enumerate(has_data_dbs, 1):
        print(f"{i}. {db['path']}")
        print(f"   任务数: {db['job_count']}, 最后修改: {db['mtime']}")
        print()

    print("建议:")
    print("  1. 确定哪个是正确的数据库")
    print("  2. 设置 CI_DATA_DIR 环境变量指向正确的目录")
    print("  3. 考虑合并或清理其他数据库")
    print()

# 检查进程
print("=" * 80)
print("检查运行中的进程")
print("=" * 80)
print()

import subprocess

try:
    # 检查 Flask 进程
    result = subprocess.run(['pgrep', '-f', 'flask'], capture_output=True, text=True)
    if result.returncode == 0:
        pids = result.stdout.strip().split('\n')
        print(f"✓ Flask 进程运行中 (PID: {', '.join(pids)})")

        # 尝试查看打开的文件
        for pid in pids:
            try:
                lsof_result = subprocess.run(['lsof', '-p', pid], capture_output=True, text=True, timeout=5)
                if '.db' in lsof_result.stdout:
                    print(f"  进程 {pid} 打开的数据库文件:")
                    for line in lsof_result.stdout.split('\n'):
                        if '.db' in line and 'jobs' in line.lower():
                            print(f"    {line}")
            except Exception:
                pass
    else:
        print("⚠ Flask 进程未运行")
    print()

    # 检查 Celery 进程
    result = subprocess.run(['pgrep', '-f', 'celery.*worker'], capture_output=True, text=True)
    if result.returncode == 0:
        pids = result.stdout.strip().split('\n')
        print(f"✓ Celery Worker 进程运行中 (PID: {', '.join(pids)})")

        # 尝试查看打开的文件
        for pid in pids:
            try:
                lsof_result = subprocess.run(['lsof', '-p', pid], capture_output=True, text=True, timeout=5)
                if '.db' in lsof_result.stdout:
                    print(f"  进程 {pid} 打开的数据库文件:")
                    for line in lsof_result.stdout.split('\n'):
                        if '.db' in line and 'jobs' in line.lower():
                            print(f"    {line}")
            except Exception:
                pass
    else:
        print("⚠ Celery Worker 进程未运行")

except Exception as e:
    print(f"无法检查进程: {e}")

print()
print("=" * 80)
print("完成")
print("=" * 80)
