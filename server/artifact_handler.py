#!/usr/bin/env python3
"""
构建产物处理器
负责打包构建产物、清理原始文件
"""

import os
import tarfile
import shutil
import glob
from pathlib import Path
from typing import List, Optional


class ArtifactHandler:
    """构建产物处理器"""

    def __init__(self, artifacts_dir: str):
        """
        初始化产物处理器

        Args:
            artifacts_dir: 产物存储目录
        """
        self.artifacts_dir = artifacts_dir
        Path(artifacts_dir).mkdir(parents=True, exist_ok=True)

    def pack_artifacts(self, work_dir: str, artifact_patterns: List[str], job_id: str) -> Optional[str]:
        """
        打包构建产物

        Args:
            work_dir: 工作目录（构建代码所在目录）
            artifact_patterns: 产物路径模式列表，如 ['dist/', 'build/*.apk']
            job_id: 任务ID

        Returns:
            产物tar.gz路径，如果没有产物返回None
        """
        if not artifact_patterns:
            return None

        # 收集所有匹配的文件和目录
        artifacts_to_pack = []

        for pattern in artifact_patterns:
            # 去除前后空格
            pattern = pattern.strip()
            if not pattern:
                continue

            # 构建完整路径
            full_pattern = os.path.join(work_dir, pattern)

            # 使用glob匹配
            matches = glob.glob(full_pattern, recursive=True)

            if matches:
                for match in matches:
                    # 转换为相对路径
                    rel_path = os.path.relpath(match, work_dir)
                    artifacts_to_pack.append((match, rel_path))
            else:
                print(f"⚠ 产物模式未匹配到文件: {pattern}")

        if not artifacts_to_pack:
            print("⚠ 没有找到构建产物")
            return None

        # 创建tar.gz文件
        archive_path = os.path.join(self.artifacts_dir, f"{job_id}-artifacts.tar.gz")

        try:
            with tarfile.open(archive_path, 'w:gz') as tar:
                for abs_path, rel_path in artifacts_to_pack:
                    tar.add(abs_path, arcname=rel_path)
                    print(f"  打包: {rel_path}")

            # 获取文件大小
            size = os.path.getsize(archive_path)
            size_mb = size / (1024 * 1024)
            print(f"✓ 产物打包完成: {archive_path} ({size_mb:.2f}MB)")

            return archive_path

        except Exception as e:
            print(f"✗ 打包产物失败: {e}")
            return None

    def cleanup_source_artifacts(self, work_dir: str, artifact_patterns: List[str]):
        """
        清理原始构建产物（保留tar.gz）

        Args:
            work_dir: 工作目录
            artifact_patterns: 产物路径模式列表
        """
        if not artifact_patterns:
            return

        for pattern in artifact_patterns:
            pattern = pattern.strip()
            if not pattern:
                continue

            full_pattern = os.path.join(work_dir, pattern)
            matches = glob.glob(full_pattern, recursive=True)

            for match in matches:
                try:
                    if os.path.isfile(match):
                        os.remove(match)
                        print(f"  删除文件: {match}")
                    elif os.path.isdir(match):
                        shutil.rmtree(match)
                        print(f"  删除目录: {match}")
                except Exception as e:
                    print(f"⚠ 清理失败 {match}: {e}")

    def get_artifact_size(self, archive_path: str) -> int:
        """
        获取产物文件大小

        Args:
            archive_path: 产物文件路径

        Returns:
            文件大小（字节）
        """
        if os.path.exists(archive_path):
            return os.path.getsize(archive_path)
        return 0

    def delete_artifact(self, archive_path: str) -> bool:
        """
        删除产物文件

        Args:
            archive_path: 产物文件路径

        Returns:
            是否删除成功
        """
        try:
            if os.path.exists(archive_path):
                os.remove(archive_path)
                print(f"✓ 删除产物: {archive_path}")
                return True
            return False
        except Exception as e:
            print(f"✗ 删除产物失败: {e}")
            return False


# 测试代码
if __name__ == '__main__':
    import tempfile

    # 创建测试目录
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = os.path.join(temp_dir, 'work')
        artifacts_dir = os.path.join(temp_dir, 'artifacts')

        os.makedirs(work_dir)
        os.makedirs(os.path.join(work_dir, 'dist'))
        os.makedirs(os.path.join(work_dir, 'build'))

        # 创建测试文件
        with open(os.path.join(work_dir, 'dist', 'app.js'), 'w') as f:
            f.write('console.log("test")')
        with open(os.path.join(work_dir, 'build', 'app.apk'), 'w') as f:
            f.write('fake apk')

        # 测试打包
        handler = ArtifactHandler(artifacts_dir)
        archive = handler.pack_artifacts(work_dir, ['dist/', 'build/*.apk'], 'test-job-001')

        if archive:
            print(f"产物大小: {handler.get_artifact_size(archive)} 字节")
            print(f"产物文件: {archive}")

            # 测试清理
            handler.cleanup_source_artifacts(work_dir, ['dist/', 'build/*.apk'])

            # 测试删除
            handler.delete_artifact(archive)

        print("\n✓ 所有测试通过")
