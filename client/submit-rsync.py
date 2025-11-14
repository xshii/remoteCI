#!/usr/bin/env python3
"""
公共CI脚本 - rsync模式
用法:
  python submit-rsync.py [project-name] [build-script]
  python submit-rsync.py myproject "npm test"
"""

import os
import sys
import time
import argparse
import requests
import subprocess
import json


class RemoteCIRsyncClient:
    """Remote CI 客户端 - rsync模式"""

    def __init__(self, api_url, api_token, remote_host, workspace_base):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.remote_host = remote_host
        self.workspace_base = workspace_base
        self.headers = {
            'Authorization': f'Bearer {api_token}'
        }

    def sync_code(self, project_name):
        """同步代码到远程CI"""
        print(">>> 步骤 1/3: 同步代码到远程CI")

        workspace_path = f"{self.workspace_base}/{project_name}"

        # 创建远程目录
        try:
            subprocess.run(
                ['ssh', self.remote_host, f'mkdir -p {workspace_path}'],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ 创建远程目录失败: {e.stderr}")
            return None

        # rsync同步（排除不需要的文件）
        rsync_cmd = [
            'rsync',
            '-avz',
            '--delete',
            '--exclude=.git',
            '--exclude=node_modules',
            '--exclude=__pycache__',
            '--exclude=*.pyc',
            '--exclude=.pytest_cache',
            '--exclude=dist',
            '--exclude=build',
            '--exclude=.env',
            './',
            f'{self.remote_host}:{workspace_path}/'
        ]

        try:
            result = subprocess.run(
                rsync_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            # 显示rsync输出（如果需要的话）
            if result.stdout:
                # 只显示总结行
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    if line.strip():
                        print(line)

            print("✓ 代码同步完成")
            print()
            return workspace_path

        except subprocess.CalledProcessError as e:
            print(f"✗ rsync同步失败: {e.stderr}")
            return None
        except FileNotFoundError:
            print("✗ rsync命令未找到，请确保已安装rsync")
            return None

    def submit_job(self, workspace_path, script, user=None):
        """提交任务到远程CI"""
        print(">>> 步骤 2/3: 提交构建任务")

        if user is None:
            user = os.environ.get('USER', 'unknown')

        payload = {
            'workspace': workspace_path,
            'script': script,
            'user': user
        }

        try:
            response = requests.post(
                f'{self.api_url}/api/jobs/rsync',
                headers={**self.headers, 'Content-Type': 'application/json'},
                json=payload
            )
            response.raise_for_status()
            result = response.json()

            job_id = result.get('job_id')
            if not job_id:
                print("✗ 任务提交失败")
                print(f"响应: {result}")
                return None

            print("✓ 任务已提交")
            print(f"任务ID: {job_id}")
            print(f"Web查看: {self.api_url}/#job-{job_id}")
            print()

            return job_id

        except requests.exceptions.RequestException as e:
            print(f"✗ 请求失败: {e}")
            return None

    def wait_for_result(self, job_id, max_wait=1500, interval=10):
        """等待任务结果"""
        print(">>> 步骤 3/3: 等待构建结果")
        print()

        elapsed = 0

        while elapsed < max_wait:
            try:
                response = requests.get(
                    f'{self.api_url}/api/jobs/{job_id}',
                    headers=self.headers
                )
                response.raise_for_status()
                result = response.json()

                status = result.get('status', 'unknown')

                # 显示进度
                print(f"\r[{elapsed:03d}s] 状态: {status:<10}", end='', flush=True)

                if status == 'success':
                    print("\n")
                    print("=" * 42)
                    print("✓ 构建成功")
                    print("=" * 42)
                    self._show_logs(job_id)
                    return 0

                elif status in ['failed', 'error', 'timeout']:
                    print("\n")
                    print("=" * 42)
                    print("✗ 构建失败")
                    print("=" * 42)
                    self._show_logs(job_id)
                    return 1

                elif status in ['queued', 'running']:
                    time.sleep(interval)
                    elapsed += interval

                else:
                    print(f"\n✗ 未知状态: {status}")
                    return 1

            except requests.exceptions.RequestException as e:
                print(f"\n✗ 请求失败: {e}")
                return 1

        # 超时处理
        print("\n")
        print("=" * 42)
        print("⚠ 公共CI等待超时")
        print("=" * 42)
        print("任务仍在远程CI执行中...")
        print(f"查看任务: {self.api_url}/#job-{job_id}")
        print()
        print("远程CI将继续执行，结果可通过Web界面查看")
        print("=" * 42)

        # 不返回失败状态，避免公共CI报错
        return 0

    def _show_logs(self, job_id):
        """显示任务日志"""
        print()
        print("构建日志:")
        print("-" * 42)

        try:
            response = requests.get(
                f'{self.api_url}/api/jobs/{job_id}/logs',
                headers=self.headers
            )
            response.raise_for_status()
            print(response.text)
        except requests.exceptions.RequestException as e:
            print(f"无法获取日志: {e}")

        print("-" * 42)


def main():
    parser = argparse.ArgumentParser(
        description='Remote CI - rsync模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python submit-rsync.py myproject "npm test"
  python submit-rsync.py backend "python -m pytest"

环境变量:
  REMOTE_CI_HOST       - 远程CI SSH地址 (默认: ci-user@remote-ci-server)
  REMOTE_CI_API        - 远程CI API地址 (默认: http://remote-ci-server:5000)
  REMOTE_CI_TOKEN      - API认证Token (默认: your-api-token)
  WORKSPACE_BASE       - Workspace基础目录 (默认: /var/ci-workspace)
  CI_TIMEOUT           - 等待超时时间/秒 (默认: 1500)
  CI_PROJECT_NAME      - CI项目名称 (自动检测)
        """
    )

    parser.add_argument(
        'project_name',
        nargs='?',
        help='项目名称 (可通过CI_PROJECT_NAME环境变量自动获取)'
    )

    parser.add_argument(
        'script',
        nargs='?',
        default='npm install && npm test',
        help='构建脚本 (默认: npm install && npm test)'
    )

    args = parser.parse_args()

    # 从环境变量读取配置
    remote_host = os.environ.get('REMOTE_CI_HOST', 'ci-user@remote-ci-server')
    api_url = os.environ.get('REMOTE_CI_API', 'http://remote-ci-server:5000')
    api_token = os.environ.get('REMOTE_CI_TOKEN', 'your-api-token')
    workspace_base = os.environ.get('WORKSPACE_BASE', '/var/ci-workspace')
    timeout = int(os.environ.get('CI_TIMEOUT', '1500'))

    # 项目名称：命令行参数 > 环境变量 > 默认值
    project_name = args.project_name
    if not project_name:
        project_name = os.environ.get('CI_PROJECT_NAME', 'default-project')

    workspace_path = f"{workspace_base}/{project_name}"

    print("=" * 42)
    print("Remote CI - rsync模式")
    print("=" * 42)
    print(f"项目名称: {project_name}")
    print(f"构建脚本: {args.script}")
    print(f"远程路径: {workspace_path}")
    print("=" * 42)
    print()

    # 创建客户端
    client = RemoteCIRsyncClient(api_url, api_token, remote_host, workspace_base)

    # 同步代码
    workspace_path = client.sync_code(project_name)
    if not workspace_path:
        return 1

    # 提交任务
    job_id = client.submit_job(workspace_path, args.script)
    if not job_id:
        return 1

    # 等待结果
    return client.wait_for_result(job_id, max_wait=timeout)


if __name__ == '__main__':
    sys.exit(main())
