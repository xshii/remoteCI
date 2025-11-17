#!/usr/bin/env python3
"""
Remote CI 统一客户端（增强版）
支持三种模式：upload（上传）、rsync（同步）、git（克隆）
支持自动用户检测和workspace隔离，避免并发冲突

用法:
  python submit.py upload [options] <script>
  python submit.py rsync [options] <project> <script>
  python submit.py git [options] <repo> <branch> <script>

新增功能:
  - 自动检测CI系统用户（GitLab、GitHub、Jenkins等）
  - rsync模式自动添加用户后缀，避免workspace冲突
  - 支持UUID模式，确保完全隔离（调试用）
  - 保留编译缓存，加速后续构建
"""

import os
import sys
import time
import uuid
import tarfile
import tempfile
import argparse
import requests
import subprocess
import fnmatch
from pathlib import Path
import yaml


# ============ 辅助函数 ============

def load_config_file(config_path=None):
    """
    加载YAML配置文件

    Args:
        config_path: 配置文件路径，None则自动查找

    Returns:
        配置字典，未找到返回{}
    """
    # 默认配置文件名
    default_config_files = ['.remoteCI.yml', 'remoteCI.yml', '.remoteCI.yaml', 'remoteCI.yaml']

    # 如果指定了配置文件
    if config_path:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠ 警告: 无法加载配置文件 {config_path}: {e}")
                return {}
        else:
            print(f"⚠ 警告: 配置文件不存在: {config_path}")
            return {}

    # 自动查找配置文件
    for config_file in default_config_files:
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                    print(f"✓ 已加载配置文件: {config_file}")
                    return config
            except Exception as e:
                print(f"⚠ 警告: 无法加载配置文件 {config_file}: {e}")

    return {}


def detect_user_id():
    """
    智能检测用户ID
    支持多种CI系统：GitLab CI、GitHub Actions、Jenkins、CircleCI、Travis CI

    返回:
        用户ID字符串
    """
    # 1. 优先使用显式指定的环境变量
    if os.environ.get('REMOTE_CI_USER_ID'):
        return os.environ.get('REMOTE_CI_USER_ID')

    # 2. 按优先级检测各种CI系统的用户变量
    ci_detections = [
        ('GITLAB_USER_LOGIN', 'GitLab CI'),
        ('GITLAB_USER_ID', 'GitLab CI'),
        ('GITHUB_ACTOR', 'GitHub Actions'),
        ('BUILD_USER', 'Jenkins'),
        ('CIRCLE_USERNAME', 'CircleCI'),
        ('TRAVIS_BUILD_USER', 'Travis CI'),
    ]

    for var, ci_name in ci_detections:
        if os.environ.get(var):
            user_id = os.environ.get(var)
            return user_id

    # 3. 降级使用本地系统用户
    return os.environ.get('USER', 'unknown')


def generate_workspace_name(project_name, user_id=None, use_uuid=False):
    """
    生成workspace名称

    Args:
        project_name: 项目基础名称
        user_id: 用户ID（None表示自动检测）
        use_uuid: 是否使用UUID模式（完全隔离，不复用缓存）

    Returns:
        完整的workspace名称

    示例:
        generate_workspace_name('proj', 'alice', False)  → 'proj-alice'
        generate_workspace_name('proj', 'alice', True)   → 'proj-alice-a1b2c3d4'
        generate_workspace_name('proj', None, True)      → 'proj-{auto_user}-a1b2c3d4'
    """
    # 自动检测user_id（如果未指定）
    if user_id is None:
        user_id = detect_user_id()

    if use_uuid:
        # UUID模式：在user_id后追加UUID，既隔离又分组
        uid = uuid.uuid4().hex[:8]
        return f"{project_name}-{user_id}-{uid}"
    else:
        # 用户模式：按用户隔离，复用编译缓存
        return f"{project_name}-{user_id}"


# ============ 客户端类 ============

class RemoteCIClient:
    """Remote CI 统一客户端"""

    def __init__(self, api_url, api_token):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Bearer {api_token}'
        }

    # ========== 通用方法 ==========

    def _build_web_url(self, user_id=None):
        """构建Web查看链接（带筛选参数）"""
        if user_id:
            # URL编码user_id
            from urllib.parse import quote
            return f"{self.api_url}/?user_id={quote(user_id)}"
        return self.api_url

    def wait_for_result(self, job_id, max_wait=1500, interval=10, user_id=None):
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
        web_url = self._build_web_url(user_id)
        print(f"查看任务: {web_url}")
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
                    exclude_patterns=None, config=None):
        """上传模式：打包代码并上传"""
        # 从配置文件读取默认值（如果有）
        if config and 'upload' in config:
            upload_config = config['upload']

            # paths: 优先使用命令行参数，否则使用配置文件
            if upload_path == '.' and 'paths' in upload_config:
                paths = upload_config['paths']
                if isinstance(paths, list):
                    upload_path = ' '.join(paths)
                elif isinstance(paths, str):
                    upload_path = paths

            # exclude: 合并配置文件和命令行参数
            if 'exclude' in upload_config:
                config_excludes = upload_config['exclude']
                if isinstance(config_excludes, list):
                    config_exclude_str = ','.join(config_excludes)
                elif isinstance(config_excludes, str):
                    config_exclude_str = config_excludes
                else:
                    config_exclude_str = None

                # 合并排除规则
                if config_exclude_str:
                    if exclude_patterns:
                        exclude_patterns = f"{config_exclude_str},{exclude_patterns}"
                    else:
                        exclude_patterns = config_exclude_str

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
            return self.wait_for_result(job_id, user_id=user_id)

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
                    # 标准化路径：去掉尾部斜杠，但保持相对路径结构
                    normalized_path = path.rstrip('/')

                    if os.path.isdir(path):
                        # 对于目录：保持原始相对路径
                        # src/ -> arcname='src'
                        # config/templates/ -> arcname='config/templates'
                        arcname = normalized_path if normalized_path != '.' else '.'
                        tar.add(path, arcname=arcname,
                               filter=lambda ti: self._filter_tarinfo(ti, all_excludes))
                    else:
                        # 对于文件：保持原始相对路径
                        # package.json -> arcname='package.json'
                        # config/app.json -> arcname='config/app.json'
                        if not self._should_exclude(path, all_excludes):
                            tar.add(path, arcname=normalized_path)
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

        if project_name is None:
            project_name = self._detect_project_name()

        with open(archive_path, 'rb') as f:
            files = {'code': ('code.tar.gz', f, 'application/gzip')}
            data = {
                'script': script,
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
                web_url = self._build_web_url(user_id)
                print(f"Web查看: {web_url}")
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
        return self.wait_for_result(job_id, user_id=user_id)

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

        payload = {
            'workspace': workspace_path,
            'script': script
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
            web_url = self._build_web_url(user_id)
            print(f"Web查看: {web_url}")
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
        return self.wait_for_result(job_id, user_id=user_id)

    def _submit_git_job(self, repo, branch, script, commit=None, user_id=None):
        """提交git任务"""
        print(">>> 提交构建任务")

        payload = {
            'repo': repo,
            'branch': branch,
            'script': script
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
            web_url = self._build_web_url(user_id)
            print(f"Web查看: {web_url}")
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

配置文件 (.remoteCI.yml):
  upload:
    paths:              # 要上传的路径列表
      - src/
      - tests/
      - package.json
    exclude:            # 排除规则列表
      - "*.log"
      - "*.tmp"
      - cache/

示例:
  # Upload模式 - 使用默认配置文件
  python submit.py upload "npm test"

  # Upload模式 - 指定配置文件
  python submit.py upload "npm test" --config custom.yml

  # Upload模式 - 命令行参数（覆盖配置文件）
  python submit.py upload "npm test" --project myapp --user-id 12345
  python submit.py upload "npm test" --path "src/ tests/" --exclude "*.log,*.tmp"

  # Rsync模式（推荐：自动用户隔离）
  python submit.py rsync myproject "npm test"
  # → workspace: myproject-alice（自动检测用户，复用缓存）

  # Rsync模式（用户+UUID隔离，调试用）
  python submit.py rsync myproject "npm test" --uuid
  # → workspace: myproject-alice-a1b2c3d4（按用户分组，每次独立）

  # Rsync模式（手动指定用户）
  python submit.py rsync myproject "npm test" --user-id bob
  # → workspace: myproject-bob

  # Rsync模式（禁用隔离，不推荐）
  python submit.py rsync myproject "npm test" --no-user-suffix
  # → workspace: myproject（多人并发可能冲突！）

  # Git模式
  python submit.py git https://github.com/user/repo.git main "npm test"
  python submit.py git https://github.com/user/repo.git main "npm test" --commit abc123
        """
    )

    # 全局参数
    parser.add_argument('--user-id', help='用户ID（可选，用于标识提交者）')
    parser.add_argument('--config', '-c', help='配置文件路径（默认: .remoteCI.yml）')

    # 子命令
    subparsers = parser.add_subparsers(dest='mode', help='执行模式')

    # Upload 子命令
    upload_parser = subparsers.add_parser('upload', help='上传模式')
    upload_parser.add_argument('script', help='构建脚本')
    upload_parser.add_argument('--project', '-p', dest='project_name', help='项目名称（留空自动检测）')
    upload_parser.add_argument('--path', default='.', help='上传路径（默认: .，可在配置文件指定）')
    upload_parser.add_argument('--exclude', help='自定义排除模式（逗号分隔，追加到配置文件规则）')

    # Rsync 子命令
    rsync_parser = subparsers.add_parser('rsync', help='rsync模式')
    rsync_parser.add_argument('project', help='项目名称')
    rsync_parser.add_argument('script', help='构建脚本')
    rsync_parser.add_argument('--uuid', action='store_true',
                              help='添加UUID后缀（格式: project-user-uuid，按用户分组但每次独立）')
    rsync_parser.add_argument('--no-user-suffix', action='store_true',
                              help='不添加用户后缀（不推荐，可能导致并发冲突）')

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

    # 加载配置文件
    config = load_config_file(args.config if hasattr(args, 'config') else None)

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
            exclude_patterns=args.exclude,
            config=config
        )

    elif args.mode == 'rsync':
        remote_host = os.environ.get('REMOTE_CI_HOST', 'ci-user@remote-ci-server')
        workspace_base = os.environ.get('WORKSPACE_BASE', '/var/ci-workspace')

        # 生成workspace名称（支持用户隔离和UUID模式）
        if args.no_user_suffix:
            # 不添加后缀（原始行为，有并发风险）
            workspace_name = args.project
            print("⚠️  警告: 未启用用户隔离，多人并发可能冲突")
            print()
        else:
            # 自动检测user_id（如果未指定）
            if user_id is None:
                user_id = detect_user_id()

            # 生成workspace名称
            workspace_name = generate_workspace_name(
                args.project,
                user_id=user_id,
                use_uuid=args.uuid
            )

            # 显示workspace信息
            print("=" * 50)
            print("Workspace隔离配置")
            print("=" * 50)
            print(f"原始项目名: {args.project}")
            print(f"用户ID: {user_id}")
            print(f"Workspace: {workspace_name}")
            if args.uuid:
                print("模式: 用户+UUID隔离（按用户分组，每次独立）")
                print("特点: 不复用缓存，适合调试")
            else:
                print("模式: 用户隔离（复用编译缓存）✓")
            print("=" * 50)
            print()

        return client.rsync_mode(
            project_name=workspace_name,
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
