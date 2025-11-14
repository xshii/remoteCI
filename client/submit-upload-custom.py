#!/usr/bin/env python3
"""
公共CI脚本 - 上传模式（自定义排除）
用法:
  python submit-upload-custom.py [build-script] [include-paths] [exclude-patterns]

示例:
  # 只上传src和tests目录
  python submit-upload-custom.py "npm test" "src/ tests/" ""

  # 上传当前目录，但排除指定文件
  python submit-upload-custom.py "npm test" "." "*.log,*.tmp,cache/"

  # 只上传特定文件
  python submit-upload-custom.py "npm test" "package.json src/ Dockerfile" ""
"""

import os
import sys
import time
import tarfile
import tempfile
import argparse
import requests
import fnmatch
from pathlib import Path


class RemoteCIClientCustom:
    """Remote CI 客户端（支持自定义排除）"""

    def __init__(self, api_url, api_token):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.headers = {
            'Authorization': f'Bearer {api_token}'
        }

    def create_archive(self, include_paths, exclude_patterns, archive_path):
        """创建代码压缩包"""
        print(">>> 步骤 1/3: 打包代码")

        # 默认排除规则
        default_excludes = [
            '.git',
            'node_modules',
            '__pycache__',
            '*.pyc',
            '.pytest_cache',
            'dist',
            'build',
            '.env',
            '*.log'
        ]

        # 合并自定义排除规则
        all_excludes = default_excludes.copy()
        if exclude_patterns:
            custom_excludes = [p.strip() for p in exclude_patterns.split(',') if p.strip()]
            all_excludes.extend(custom_excludes)
            print("自定义排除规则:")
            for exclude in custom_excludes:
                print(f"  排除: {exclude}")

        # 解析包含路径
        paths = include_paths.strip().split() if ' ' in include_paths else [include_paths]

        print(f"执行打包...")

        # 创建tar.gz文件
        with tarfile.open(archive_path, 'w:gz') as tar:
            for path in paths:
                path = path.strip()
                if not path:
                    continue

                if os.path.exists(path):
                    # 添加文件/目录，应用排除规则
                    if os.path.isdir(path):
                        tar.add(
                            path,
                            arcname=os.path.basename(path) if path != '.' else '.',
                            filter=lambda tarinfo: self._filter_tarinfo(tarinfo, all_excludes)
                        )
                    else:
                        # 单个文件
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

        print(f"✓ 代码已打包 (大小: {size_str})")
        print()

        return archive_path

    def _should_exclude(self, path, excludes):
        """检查路径是否应该被排除"""
        for exclude in excludes:
            # 处理通配符
            if '*' in exclude or '?' in exclude:
                if fnmatch.fnmatch(path, exclude) or fnmatch.fnmatch(os.path.basename(path), exclude):
                    return True
            # 精确匹配或路径匹配
            elif path == exclude or path.startswith(exclude + '/') or os.path.basename(path) == exclude:
                return True
        return False

    def _filter_tarinfo(self, tarinfo, excludes):
        """过滤tar文件内容"""
        if self._should_exclude(tarinfo.name, excludes):
            return None
        return tarinfo

    def submit_job(self, archive_path, script, user=None):
        """提交任务到远程CI"""
        print(">>> 步骤 2/3: 上传代码并提交任务")

        if user is None:
            user = os.environ.get('USER', 'unknown')

        with open(archive_path, 'rb') as f:
            files = {'code': ('code.tar.gz', f, 'application/gzip')}
            data = {
                'script': script,
                'user': user
            }

            try:
                response = requests.post(
                    f'{self.api_url}/api/jobs/upload',
                    headers=self.headers,
                    files=files,
                    data=data
                )

                # 检查HTTP状态码
                if response.status_code != 201:
                    print(f"✗ 任务提交失败 (HTTP {response.status_code})")
                    print(response.text)
                    return None

                result = response.json()
                job_id = result.get('job_id')

                if not job_id:
                    print("✗ 无法获取任务ID")
                    print(f"响应: {result}")
                    return None

                print("✓ 任务已提交")
                print(f"  任务ID: {job_id}")
                print(f"  Web查看: {self.api_url}/#job-{job_id}")
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
        description='Remote CI - 上传模式（自定义排除）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 只上传src和tests目录
  python submit-upload-custom.py "npm test" "src/ tests/" ""

  # 上传当前目录，但排除指定文件
  python submit-upload-custom.py "npm test" "." "*.log,*.tmp,cache/"

  # 只上传特定文件
  python submit-upload-custom.py "npm test" "package.json src/ Dockerfile" ""

环境变量:
  REMOTE_CI_API     - 远程CI API地址 (默认: http://remote-ci-server:5000)
  REMOTE_CI_TOKEN   - API认证Token (默认: your-api-token)
  CI_TIMEOUT        - 等待超时时间/秒 (默认: 1500)
        """
    )

    parser.add_argument(
        'script',
        nargs='?',
        default='npm install && npm test',
        help='构建脚本 (默认: npm install && npm test)'
    )

    parser.add_argument(
        'include_paths',
        nargs='?',
        default='.',
        help='包含路径，多个路径用空格分隔 (默认: .)'
    )

    parser.add_argument(
        'exclude_patterns',
        nargs='?',
        default='',
        help='排除模式，逗号分隔 (例如: *.log,*.tmp,cache/)'
    )

    args = parser.parse_args()

    # 从环境变量读取配置
    api_url = os.environ.get('REMOTE_CI_API', 'http://remote-ci-server:5000')
    api_token = os.environ.get('REMOTE_CI_TOKEN', 'your-api-token')
    timeout = int(os.environ.get('CI_TIMEOUT', '1500'))

    print("=" * 42)
    print("Remote CI - 上传模式（自定义）")
    print("=" * 42)
    print(f"构建脚本: {args.script}")
    print(f"包含路径: {args.include_paths}")
    print(f"排除模式: {args.exclude_patterns if args.exclude_patterns else '默认排除'}")
    print("=" * 42)
    print()

    # 创建客户端
    client = RemoteCIClientCustom(api_url, api_token)

    # 创建临时压缩包
    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp:
        archive_path = tmp.name

    try:
        # 打包代码
        client.create_archive(args.include_paths, args.exclude_patterns, archive_path)

        # 提交任务
        job_id = client.submit_job(archive_path, args.script)
        if not job_id:
            return 1

        # 等待结果
        return client.wait_for_result(job_id, max_wait=timeout)

    finally:
        # 清理临时文件
        if os.path.exists(archive_path):
            os.unlink(archive_path)


if __name__ == '__main__':
    sys.exit(main())
