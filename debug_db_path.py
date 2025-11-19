#!/usr/bin/env python3
"""
数据库路径诊断脚本
用于检查 Flask 和 Celery Worker 是否使用相同的数据库路径
"""

import os
import sys
from pathlib import Path

# 尝试加载环境变量（如果有.env文件）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("注意: dotenv 模块未安装，跳过 .env 文件加载\n")

print("=" * 80)
print("数据库路径诊断工具")
print("=" * 80)
print()

# 1. 检查当前工作目录
print("1. 当前工作目录:")
print(f"   {os.getcwd()}")
print()

# 2. 模拟 server/config.py 的逻辑
print("2. 模拟 server/config.py 中的路径计算:")
print()

# 假设从不同位置导入 config
test_paths = [
    "/home/user/remoteCI/server/config.py",  # 实际文件位置
    os.path.join(os.getcwd(), "server/config.py"),  # 从当前目录
]

for config_path in test_paths:
    print(f"   假设 config.py 在: {config_path}")
    config_file = Path(config_path)
    base_dir = config_file.parent.parent
    print(f"   BASE_DIR = {base_dir}")

    # 检查环境变量
    env_data_dir = os.getenv('CI_DATA_DIR')
    if env_data_dir:
        data_dir = env_data_dir
        print(f"   DATA_DIR (from env) = {data_dir}")
    else:
        data_dir = str(base_dir / 'data')
        print(f"   DATA_DIR (from BASE_DIR) = {data_dir}")

    db_path = f"{data_dir}/jobs.db"
    print(f"   数据库路径: {db_path}")

    # 检查文件是否存在
    exists = os.path.exists(db_path)
    print(f"   文件存在: {exists}")

    if exists:
        # 显示文件大小和修改时间
        size = os.path.getsize(db_path)
        mtime = os.path.getmtime(db_path)
        from datetime import datetime
        print(f"   文件大小: {size} 字节")
        print(f"   修改时间: {datetime.fromtimestamp(mtime)}")

        # 查询数据库中的任务数量
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ci_jobs")
            count = cursor.fetchone()[0]
            print(f"   任务数量: {count}")

            # 显示最近的几条记录
            cursor.execute("SELECT job_id, status, mode, created_at FROM ci_jobs ORDER BY created_at DESC LIMIT 5")
            rows = cursor.fetchall()
            if rows:
                print(f"   最近的任务:")
                for row in rows:
                    print(f"      - {row[0]}: {row[1]} ({row[2]}) @ {row[3]}")

            conn.close()
        except Exception as e:
            print(f"   查询数据库失败: {e}")

    print()

# 3. 检查环境变量
print("3. 环境变量检查:")
env_vars = ['CI_DATA_DIR', 'CI_WORK_DIR', 'CI_WORKSPACE_DIR', 'CI_API_HOST', 'CI_API_PORT']
for var in env_vars:
    value = os.getenv(var)
    if value:
        print(f"   {var} = {value}")
    else:
        print(f"   {var} = (未设置)")
print()

# 4. 实际使用的路径
print("4. 实际使用的数据库路径:")
print()

# 导入实际的配置
sys.path.insert(0, '/home/user/remoteCI')
try:
    from server.config import DATA_DIR, BASE_DIR
    print(f"   BASE_DIR = {BASE_DIR}")
    print(f"   DATA_DIR = {DATA_DIR}")
    db_path = f"{DATA_DIR}/jobs.db"
    print(f"   数据库路径: {db_path}")

    exists = os.path.exists(db_path)
    print(f"   文件存在: {exists}")

    if exists:
        size = os.path.getsize(db_path)
        mtime = os.path.getmtime(db_path)
        from datetime import datetime
        print(f"   文件大小: {size} 字节")
        print(f"   修改时间: {datetime.fromtimestamp(mtime)}")

        # 查询数据库
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ci_jobs")
            count = cursor.fetchone()[0]
            print(f"   ✓ 任务总数: {count}")

            # 显示最近的记录
            cursor.execute("SELECT job_id, status, mode, user_id, created_at FROM ci_jobs ORDER BY created_at DESC LIMIT 5")
            rows = cursor.fetchall()
            if rows:
                print(f"   ✓ 最近的 {len(rows)} 条任务:")
                for row in rows:
                    print(f"      - {row[0][:20]}... | {row[1]:8} | {row[2]:6} | {row[3] or 'N/A':15} | {row[4]}")
            else:
                print(f"   ⚠ 数据库为空")

            conn.close()
        except Exception as e:
            print(f"   ✗ 查询数据库失败: {e}")
            import traceback
            traceback.print_exc()

except Exception as e:
    print(f"   ✗ 导入配置失败: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("诊断建议:")
print("=" * 80)
print()
print("1. 检查 Flask 和 Celery Worker 是否使用相同的启动目录")
print("2. 确保环境变量 CI_DATA_DIR 已设置为绝对路径")
print("3. 查看是否有多个数据库文件存在于不同路径")
print("4. 运行以下命令查找所有数据库文件:")
print("   find /home/user/remoteCI -name 'jobs.db'")
print("   find /tmp -name 'jobs.db'")
print()
