#!/usr/bin/env python3
"""
Celery任务定义
支持两种模式：
1. rsync模式：使用workspace目录中的代码
2. upload模式：使用上传的代码包
"""

import os
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from celery import Task
from server.celery_app import celery_app
from server.config import WORK_DIR, DATA_DIR, JOB_TIMEOUT
from server.database import JobDatabase

# 初始化数据库连接
job_db = JobDatabase(f"{DATA_DIR}/jobs.db")


class BuildTask(Task):
    """自定义任务基类，支持进度更新"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败回调"""
        log_file = f"{DATA_DIR}/logs/{task_id}.log"
        with open(log_file, 'a') as f:
            f.write(f"\n\n===== 任务异常终止 =====\n")
            f.write(f"时间: {datetime.now().isoformat()}\n")
            f.write(f"错误: {str(exc)}\n")
            f.write(f"详情:\n{einfo}\n")


@celery_app.task(base=BuildTask, bind=True, name='remote_ci.build')
def execute_build(self, job_data):
    """
    执行构建任务

    Args:
        job_data: {
            'mode': 'rsync' | 'upload' | 'git',
            'script': '构建脚本',
            'user_id': '提交者ID',

            # rsync模式
            'workspace': '/var/ci-workspace/project',

            # upload模式
            'code_archive': '/path/to/code.tar.gz',

            # git模式
            'repo': 'git仓库URL',
            'branch': '分支名',
            'commit': '可选的commit hash'
        }

    Returns:
        {
            'status': 'success|failed|timeout',
            'exit_code': int,
            'duration': float (秒)
        }
    """
    task_id = self.request.id
    log_file = f"{DATA_DIR}/logs/{task_id}.log"
    work_dir = f"{WORK_DIR}/{task_id}"

    start_time = datetime.now()

    def log(message):
        """写日志"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")
            f.flush()

    def update_progress(state, meta):
        """更新任务进度"""
        self.update_state(state=state, meta=meta)

    try:
        # 更新数据库状态为运行中
        job_db.update_job_started(task_id)

        # 初始化日志
        log("=" * 70)
        log(f"任务ID: {task_id}")
        log(f"开始时间: {start_time.isoformat()}")
        log(f"模式: {job_data.get('mode', 'unknown')}")
        user_id = job_data.get('user_id')
        if user_id:
            log(f"提交者ID: {user_id}")
        log("=" * 70)
        log("")

        # 创建工作目录
        Path(work_dir).mkdir(parents=True, exist_ok=True)

        # 步骤1: 准备代码
        update_progress('PROGRESS', {'step': 'preparing', 'percent': 10})

        mode = job_data.get('mode', 'git')

        if mode == 'rsync':
            # rsync模式：复制workspace中的代码
            workspace = job_data['workspace']
            log(f">>> 步骤 1/3: 复制代码（rsync模式）")
            log(f"源目录: {workspace}")

            if not os.path.exists(workspace):
                raise Exception(f"Workspace不存在: {workspace}")

            # 复制到工作目录
            repo_dir = f"{work_dir}/repo"
            shutil.copytree(workspace, repo_dir, symlinks=True)
            log(f"✓ 代码复制完成\n")

        elif mode == 'upload':
            # upload模式：解压上传的代码包
            code_archive = job_data['code_archive']
            log(f">>> 步骤 1/3: 解压代码（上传模式）")
            log(f"代码包: {code_archive}")

            if not os.path.exists(code_archive):
                raise Exception(f"代码包不存在: {code_archive}")

            repo_dir = f"{work_dir}/repo"
            Path(repo_dir).mkdir(parents=True, exist_ok=True)

            # 解压
            subprocess.run(
                ['tar', '-xzf', code_archive, '-C', repo_dir],
                check=True,
                timeout=300
            )
            log(f"✓ 代码解压完成\n")

        elif mode == 'git':
            # git模式：克隆代码
            log(f">>> 步骤 1/3: 克隆代码（Git模式）")
            log(f"仓库: {job_data['repo']}")
            log(f"分支: {job_data['branch']}")

            clone_cmd = ['git', 'clone', '-b', job_data['branch'], '--depth', '1',
                        job_data['repo'], 'repo']

            clone_result = subprocess.run(
                clone_cmd,
                cwd=work_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=300,
                text=True
            )

            log(clone_result.stdout)

            if clone_result.returncode != 0:
                log(f"\n错误: Git克隆失败 (退出码: {clone_result.returncode})")
                return {
                    'status': 'failed',
                    'exit_code': clone_result.returncode,
                    'duration': (datetime.now() - start_time).total_seconds(),
                    'error': 'Git clone failed'
                }

            repo_dir = f"{work_dir}/repo"

            # 如果指定了commit，切换到该commit
            if 'commit' in job_data and job_data['commit']:
                log(f"切换到commit: {job_data['commit']}")
                subprocess.run(
                    ['git', 'checkout', job_data['commit']],
                    cwd=repo_dir,
                    check=True
                )

            log(f"✓ 代码准备完成\n")

        else:
            raise Exception(f"不支持的模式: {mode}")

        # 步骤2: 执行构建
        update_progress('PROGRESS', {'step': 'building', 'percent': 30})

        log(">>> 步骤 2/3: 执行构建脚本")
        log(f"工作目录: {repo_dir}")
        log(f"命令: {job_data['script']}")
        log("-" * 70)
        log("")

        build_result = subprocess.run(
            job_data['script'],
            shell=True,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=JOB_TIMEOUT - 400,  # 留点时间给清理工作
            text=True
        )

        log(build_result.stdout)
        log("")
        log("-" * 70)

        # 步骤3: 保存结果
        update_progress('PROGRESS', {'step': 'finishing', 'percent': 90})

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        log(f"\n>>> 步骤 3/3: 完成")
        log(f"结束时间: {end_time.isoformat()}")
        log(f"总耗时: {duration:.2f} 秒")
        log(f"退出码: {build_result.returncode}")

        if build_result.returncode == 0:
            log("\n" + "=" * 70)
            log("✓ 构建成功")
            log("=" * 70)
            status = 'success'
        else:
            log("\n" + "=" * 70)
            log("✗ 构建失败")
            log("=" * 70)
            status = 'failed'

        result = {
            'status': status,
            'exit_code': build_result.returncode,
            'duration': duration
        }

        # 更新数据库状态为完成
        job_db.update_job_finished(task_id, status, result)

        return result

    except subprocess.TimeoutExpired:
        log(f"\n\n{'=' * 70}")
        log("✗ 任务超时")
        log(f"超时限制: {JOB_TIMEOUT} 秒")
        log("=" * 70)

        result = {
            'status': 'timeout',
            'exit_code': -1,
            'duration': (datetime.now() - start_time).total_seconds(),
            'error': 'Task timeout'
        }

        # 更新数据库状态
        job_db.update_job_finished(task_id, 'timeout', result)

        return result

    except Exception as e:
        log(f"\n\n{'=' * 70}")
        log(f"✗ 任务执行错误: {str(e)}")
        log("=" * 70)

        result = {
            'status': 'error',
            'exit_code': -2,
            'duration': (datetime.now() - start_time).total_seconds(),
            'error': str(e)
        }

        # 更新数据库状态
        job_db.update_job_finished(task_id, 'error', result)

        return result

    finally:
        # 清理工作目录
        try:
            shutil.rmtree(work_dir)
            log(f"\n清理工作目录: {work_dir}")
        except Exception as e:
            log(f"\n警告: 清理工作目录失败: {e}")

        # 清理上传的文件（upload模式）
        if mode == 'upload' and 'code_archive' in job_data:
            try:
                os.remove(job_data['code_archive'])
                log(f"清理上传文件: {job_data['code_archive']}")
            except Exception as e:
                log(f"警告: 清理上传文件失败: {e}")
