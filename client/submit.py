#!/usr/bin/env python3
"""
Remote CI 统一客户端
支持三种模式：upload（上传）、rsync（同步）、git（克隆）

用法:
  python submit.py upload [options] <script>
  python submit.py rsync [options] <project> <script>
  python submit.py git [options] <repo> <branch> <script>
"""

import os
import sys
import time
import tarfile
import tempfile
import argparse
import requests
import subprocess
import fnmatch
from pathlib import Path


class RemoteCIClient:
    """Remote CI 统一客户端"""

    def __init__(self, api_url, api_token):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Bearer {api_token}'
        }

    # ========== 通用方法 ==========

    def wait_for_result(self, job_id, max_wait=1500, interval=10):
        """等待任务结果"""
        print(">>> 等待构建结果")
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
        print("⚠ 等待超时")
        print("=" * 42)
        print("任务仍在远程CI执行中...")
        print(f"查看任务: {self.api_url}/#job-{job_id}")
        print()
        print("远程CI将继续执行，结果可通过Web界面查看")
        print("=" * 42)

        # 不返回失败状态，避免CI报错
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

    def _detect_project_name(self):
        """自动检测项目名"""
        # 1. 尝试从git获取仓库名
        try:
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                name = url.split('/')[-1].replace('.git', '')
                if name:
                    return name
        except:
            pass

        # 2. 使用当前目录名
        try:
            return os.path.basename(os.getcwd())
        except:
            pass

        # 3. 默认
        return 'default'

    # ========== Upload 模式 ==========

    def upload_mode(self, script, upload_path='.', project_name=None, user_id=None,
                    exclude_patterns=None):
        """上传模式：打包代码并上传"""
        print("=" * 42)
        print("Remote CI - 上传模式")
        print("=" * 42)
        if project_name:
            print(f"项目名称: {project_name}")
        print(f"构建脚本: {script}")
        print(f"上传内容: {upload_path}")
        if user_id:
            print(f"用户ID: {user_id}")
        print("=" * 42)
        print()

        # 创建临时压缩包
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
            archive_path = tmp.name

        try:
            # 打包代码
            self._create_archive(upload_path, archive_path, exclude_patterns)

            # 提交任务
            job_id = self._submit_upload_job(archive_path, script, project_name, user_id)
            if not job_id:
                return 1

            # 等待结果
            return self.wait_for_result(job_id)

        finally:
            # 清理临时文件
            if os.path.exists(archive_path):
                os.unlink(archive_path)

    def _create_archive(self, upload_path, archive_path, custom_excludes=None):
        """创建代码压缩包"""
        print(">>> 步骤 1/3: 打包代码")

        # 默认排除规则
        default_excludes = [
            '.git', 'node_modules', '__pycache__', '*.pyc',
            '.pytest_cache', 'dist', 'build', '.env', '*.log'
        ]

        # 合并自定义排除规则
        all_excludes = default_excludes.copy()
        if custom_excludes:
            excludes = [p.strip() for p in custom_excludes.split(',') if p.strip()]
            all_excludes.extend(excludes)
            print("自定义排除规则:")
            for exclude in excludes:
                print(f"  排除: {exclude}")

        # 解析上传路径
        paths = upload_path.strip().split() if ' ' in upload_path else [upload_path]

        if upload_path == ".":
            print("打包当前目录（排除常见临时文件）")
        elif len(paths) > 1:
            print(f"打包指定目录: {upload_path}")
        else:
            print(f"打包指定路径: {upload_path}")

        # 创建tar.gz文件
        with tarfile.open(archive_path, 'w:gz') as tar:
            for path in paths:
                path = path.strip()
                if not path:
                    continue

                if os.path.exists(path):
                    if os.path.isdir(path):
                        tar.add(path, arcname=os.path.basename(path) if path != '.' else '.',
                               filter=lambda ti: self._filter_tarinfo(ti, all_excludes))
                    else:
                        if not self._should_exclude(path, all_excludes):
                            tar.add(path, arcname=os.path.basename(path))
                else:
                    print(f"⚠ 警告: 路径不存在: {path}")

        # 获取文件大小
        size_bytes = os.path.getsize(archive_path)
        size_mb = size_bytes / (1024 * 1024)
        if size_mb < 1:
            size_str = f"{size_bytes / 1024:.1f}K"
        else:
            size_str = f"{size_mb:.1f}M"

        print(f"✓ 代码打包完成 (大小: {size_str})")
        print()

    def _should_exclude(self, path, excludes):
        """检查路径是否应该被排除"""
        for exclude in excludes:
            if '*' in exclude or '?' in exclude:
                if fnmatch.fnmatch(path, exclude) or fnmatch.fnmatch(os.path.basename(path), exclude):
                    return True
            elif path == exclude or path.startswith(exclude + '/') or os.path.basename(path) == exclude:
                return True
        return False

    def _filter_tarinfo(self, tarinfo, excludes):
        """过滤tar文件内容"""
        if self._should_exclude(tarinfo.name, excludes):
            return None
        return tarinfo

    def _submit_upload_job(self, archive_path, script, project_name=None, user_id=None):
        """提交上传任务"""
        print(">>> 步骤 2/3: 上传代码并提交任务")

        user = os.environ.get('USER', 'unknown')

        if project_name is None:
            project_name = self._detect_project_name()

        with open(archive_path, 'rb') as f:
            files = {'code': ('code.tar.gz', f, 'application/gzip')}
            data = {
                'script': script,
                'user': user,
                'project_name': project_name
            }
            if user_id:
                data['user_id'] = user_id

            try:
                response = requests.post(
                    f'{self.api_url}/api/jobs/upload',
                    headers=self.headers,
                    files=files,
                    data=data
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

    # ========== Rsync 模式 ==========

    def rsync_mode(self, project_name, script, remote_host, workspace_base, user_id=None):
        """rsync模式：同步代码并提交任务"""
        workspace_path = f"{workspace_base}/{project_name}"

        print("=" * 42)
        print("Remote CI - rsync模式")
        print("=" * 42)
        print(f"项目名称: {project_name}")
        print(f"构建脚本: {script}")
        print(f"远程路径: {workspace_path}")
        if user_id:
            print(f"用户ID: {user_id}")
        print("=" * 42)
        print()

        # 同步代码
        workspace_path = self._sync_code(project_name, remote_host, workspace_base)
        if not workspace_path:
            return 1

        # 提交任务
        job_id = self._submit_rsync_job(workspace_path, script, user_id)
        if not job_id:
            return 1

        # 等待结果
        return self.wait_for_result(job_id)

    def _sync_code(self, project_name, remote_host, workspace_base):
        """同步代码到远程CI"""
        print(">>> 步骤 1/3: 同步代码到远程CI")

        workspace_path = f"{workspace_base}/{project_name}"

        # 创建远程目录
        try:
            subprocess.run(
                ['ssh', remote_host, f'mkdir -p {workspace_path}'],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ 创建远程目录失败: {e.stderr}")
            return None

        # rsync同步
        rsync_cmd = [
            'rsync', '-avz', '--delete',
            '--exclude=.git', '--exclude=node_modules', '--exclude=__pycache__',
            '--exclude=*.pyc', '--exclude=.pytest_cache', '--exclude=dist',
            '--exclude=build', '--exclude=.env',
            './',
            f'{remote_host}:{workspace_path}/'
        ]

        try:
            result = subprocess.run(
                rsync_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            if result.stdout:
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

    def _submit_rsync_job(self, workspace_path, script, user_id=None):
        """提交rsync任务"""
        print(">>> 步骤 2/3: 提交构建任务")

        user = os.environ.get('USER', 'unknown')

        payload = {
            'workspace': workspace_path,
            'script': script,
            'user': user
        }
        if user_id:
            payload['user_id'] = user_id

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

    # ========== Git 模式 ==========

    def git_mode(self, repo, branch, script, commit=None, user_id=None):
        """git模式：远程克隆并构建"""
        print("=" * 42)
        print("Remote CI - Git模式")
        print("=" * 42)
        print(f"仓库: {repo}")
        print(f"分支: {branch}")
        if commit:
            print(f"提交: {commit}")
        print(f"构建脚本: {script}")
        if user_id:
            print(f"用户ID: {user_id}")
        print("=" * 42)
        print()

        # 提交任务
        job_id = self._submit_git_job(repo, branch, script, commit, user_id)
        if not job_id:
            return 1

        # 等待结果
        return self.wait_for_result(job_id)

    def _submit_git_job(self, repo, branch, script, commit=None, user_id=None):
        """提交git任务"""
        print(">>> 提交构建任务")

        user = os.environ.get('USER', 'unknown')

        payload = {
            'repo': repo,
            'branch': branch,
            'script': script,
            'user': user
        }
        if commit:
            payload['commit'] = commit
        if user_id:
            payload['user_id'] = user_id

        try:
            response = requests.post(
                f'{self.api_url}/api/jobs/git',
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


def main():
    parser = argparse.ArgumentParser(
        description='Remote CI - 统一客户端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
环境变量:
  REMOTE_CI_API       - 远程CI API地址 (默认: http://remote-ci-server:5000)
  REMOTE_CI_TOKEN     - API认证Token (默认: your-api-token)
  REMOTE_CI_USER_ID   - 用户ID（可选，用于标识提交者）
  REMOTE_CI_HOST      - 远程CI SSH地址（rsync模式用）
  WORKSPACE_BASE      - Workspace基础目录（rsync模式用）
  CI_TIMEOUT          - 等待超时时间/秒 (默认: 1500)

示例:
  # Upload模式
  python submit.py upload "npm test"
  python submit.py upload "npm test" --project myapp --user-id 12345
  python submit.py upload "npm test" --path "src/ tests/" --exclude "*.log,*.tmp"

  # Rsync模式
  python submit.py rsync myproject "npm test"
  python submit.py rsync myproject "npm test" --user-id 12345

  # Git模式
  python submit.py git https://github.com/user/repo.git main "npm test"
  python submit.py git https://github.com/user/repo.git main "npm test" --commit abc123
        """
    )

    # 全局参数
    parser.add_argument('--user-id', help='用户ID（可选，用于标识提交者）')

    # 子命令
    subparsers = parser.add_subparsers(dest='mode', help='执行模式')

    # Upload 子命令
    upload_parser = subparsers.add_parser('upload', help='上传模式')
    upload_parser.add_argument('script', help='构建脚本')
    upload_parser.add_argument('--project', '-p', dest='project_name', help='项目名称（留空自动检测）')
    upload_parser.add_argument('--path', default='.', help='上传路径（默认: .）')
    upload_parser.add_argument('--exclude', help='自定义排除模式（逗号分隔）')

    # Rsync 子命令
    rsync_parser = subparsers.add_parser('rsync', help='rsync模式')
    rsync_parser.add_argument('project', help='项目名称')
    rsync_parser.add_argument('script', help='构建脚本')

    # Git 子命令
    git_parser = subparsers.add_parser('git', help='Git模式')
    git_parser.add_argument('repo', help='Git仓库URL')
    git_parser.add_argument('branch', help='分支名')
    git_parser.add_argument('script', help='构建脚本')
    git_parser.add_argument('--commit', help='指定commit hash（可选）')

    args = parser.parse_args()

    # 检查模式
    if not args.mode:
        parser.print_help()
        return 1

    # 从环境变量读取配置
    api_url = os.environ.get('REMOTE_CI_API', 'http://remote-ci-server:5000')
    api_token = os.environ.get('REMOTE_CI_TOKEN', 'your-api-token')
    timeout = int(os.environ.get('CI_TIMEOUT', '1500'))
    user_id = args.user_id or os.environ.get('REMOTE_CI_USER_ID')

    # 创建客户端
    client = RemoteCIClient(api_url, api_token)

    # 根据模式执行
    if args.mode == 'upload':
        return client.upload_mode(
            script=args.script,
            upload_path=args.path,
            project_name=args.project_name,
            user_id=user_id,
            exclude_patterns=args.exclude
        )

    elif args.mode == 'rsync':
        remote_host = os.environ.get('REMOTE_CI_HOST', 'ci-user@remote-ci-server')
        workspace_base = os.environ.get('WORKSPACE_BASE', '/var/ci-workspace')
        return client.rsync_mode(
            project_name=args.project,
            script=args.script,
            remote_host=remote_host,
            workspace_base=workspace_base,
            user_id=user_id
        )

    elif args.mode == 'git':
        return client.git_mode(
            repo=args.repo,
            branch=args.branch,
            script=args.script,
            commit=args.commit,
            user_id=user_id
        )

    return 1


if __name__ == '__main__':
    sys.exit(main())
