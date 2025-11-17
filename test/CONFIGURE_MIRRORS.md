# Docker 镜像源配置指南（清华源）

本文档介绍如何配置 Docker 使用清华大学镜像源，加速镜像下载。

## 已完成的配置

✓ **Dockerfile 已配置清华源**
- Debian APT 源 → 清华源
- Python pip 源 → 清华源

## 需要手动配置：Docker Hub 镜像加速

### 方法一：通过 Docker Desktop 图形界面配置（推荐）

1. **打开 Docker Desktop**
   - 点击菜单栏的 Docker 图标
   - 选择 "Preferences..." 或 "Settings..."

2. **进入 Docker Engine 设置**
   - 左侧菜单选择 "Docker Engine"
   - 看到一个 JSON 配置编辑器

3. **添加镜像加速配置**

   在 JSON 配置中添加 `registry-mirrors` 配置：

   ```json
   {
     "builder": {
       "gc": {
         "defaultKeepStorage": "20GB",
         "enabled": true
       }
     },
     "experimental": false,
     "registry-mirrors": [
       "https://docker.mirrors.tuna.tsinghua.edu.cn"
     ]
   }
   ```

   **注意**：
   - 如果配置文件已有其他内容，只需添加 `"registry-mirrors"` 这一行
   - 确保 JSON 格式正确（注意逗号）

4. **应用并重启**
   - 点击 "Apply & Restart"
   - 等待 Docker 重启完成

### 方法二：通过配置文件（命令行）

```bash
# 创建或编辑 Docker 配置文件
mkdir -p ~/.docker
cat > ~/.docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://docker.mirrors.tuna.tsinghua.edu.cn"
  ]
}
EOF

# 重启 Docker Desktop
# 方式1: 通过菜单栏 Docker 图标 -> Quit Docker Desktop，然后重新打开
# 方式2: 使用命令行
osascript -e 'quit app "Docker"'
sleep 2
open -a Docker
```

### 验证配置

配置完成后，运行以下命令验证：

```bash
docker info | grep -A 5 "Registry Mirrors"
```

应该看到：
```
Registry Mirrors:
  https://docker.mirrors.tuna.tsinghua.edu.cn/
```

## 其他可用的国内镜像源

如果清华源速度不理想，可以尝试其他镜像源：

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.tuna.tsinghua.edu.cn",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.ccs.tencentyun.com"
  ]
}
```

**说明**：Docker 会按顺序尝试这些镜像源，如果第一个失败会自动使用下一个。

## 测试镜像加速效果

```bash
# 测试拉取镜像速度
time docker pull redis:7-alpine

# 第一次会比较慢（从镜像源下载）
# 之后会很快（使用本地缓存）
```

## 已配置的源总结

| 类型 | 用途 | 配置位置 | 状态 |
|------|------|---------|------|
| Debian APT | 系统包安装 | Dockerfile | ✓ 已配置 |
| Python pip | Python 包安装 | Dockerfile | ✓ 已配置 |
| Docker Hub | Docker 镜像拉取 | Docker Desktop | ⚠️ 需手动配置 |

## 故障排查

### 1. 配置后仍然很慢

```bash
# 检查当前配置
docker info | grep -A 5 "Registry Mirrors"

# 清理并重试
docker system prune -a
```

### 2. JSON 格式错误

确保 JSON 格式正确，可以使用在线工具验证：
- https://jsonlint.com/

### 3. 配置不生效

```bash
# 完全重启 Docker Desktop
osascript -e 'quit app "Docker"'
sleep 5
open -a Docker

# 等待 30 秒后验证
sleep 30
docker info | grep "Registry Mirrors"
```

## 快速配置脚本

创建一个快速配置脚本（仅适用于 macOS）：

```bash
#!/bin/bash
# 配置 Docker 镜像加速

cat > ~/.docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.tuna.tsinghua.edu.cn",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
EOF

echo "✓ 配置文件已创建"
echo "请重启 Docker Desktop 以应用配置"
echo ""
echo "验证命令: docker info | grep -A 5 'Registry Mirrors'"
```

## 参考资料

- 清华大学开源软件镜像站：https://mirrors.tuna.tsinghua.edu.cn/help/docker-ce/
- Docker 官方文档：https://docs.docker.com/engine/reference/commandline/dockerd/#daemon-configuration-file
