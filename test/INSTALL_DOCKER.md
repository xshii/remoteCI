# macOS 安装 Docker 指南

## 方法一：官方下载安装（推荐）

### 1. 下载 Docker Desktop

访问 Docker 官网下载页面：
- **Apple Silicon (M1/M2)**: https://desktop.docker.com/mac/main/arm64/Docker.dmg
- **Intel 芯片**: https://desktop.docker.com/mac/main/amd64/Docker.dmg

或访问官网选择版本：https://www.docker.com/products/docker-desktop/

### 2. 安装步骤

1. 打开下载的 `Docker.dmg` 文件
2. 将 Docker 图标拖动到 Applications 文件夹
3. 打开 Applications 文件夹，双击 Docker
4. 首次启动会要求授权，输入系统密码
5. 等待 Docker 启动完成（菜单栏会显示 Docker 图标）

### 3. 验证安装

打开终端，运行：

```bash
docker --version
docker-compose --version
```

应该看到类似输出：
```
Docker version 24.0.x, build xxxxx
Docker Compose version v2.x.x
```

### 4. 测试运行

```bash
docker run hello-world
```

如果看到 "Hello from Docker!" 消息，说明安装成功。

## 方法二：使用 Homebrew（备选）

如果 Homebrew 正常工作，可以尝试：

```bash
# 更新 Homebrew
brew update

# 清理可能的冲突
brew cleanup

# 安装 Docker Desktop
brew install --cask docker
```

## 方法三：命令行下载安装

```bash
# 检测芯片类型
ARCH=$(uname -m)

if [ "$ARCH" = "arm64" ]; then
    # Apple Silicon
    curl -O https://desktop.docker.com/mac/main/arm64/Docker.dmg
else
    # Intel
    curl -O https://desktop.docker.com/mac/main/amd64/Docker.dmg
fi

# 挂载 DMG
hdiutil attach Docker.dmg

# 复制到 Applications
cp -R /Volumes/Docker/Docker.app /Applications/

# 卸载 DMG
hdiutil detach /Volumes/Docker

# 启动 Docker
open /Applications/Docker.app
```

## 配置 Docker（可选）

### 1. 启用 Kubernetes（如需要）

Docker Desktop -> Settings -> Kubernetes -> Enable Kubernetes

### 2. 配置资源限制

Docker Desktop -> Settings -> Resources

建议配置：
- CPUs: 2-4 核
- Memory: 4-8 GB
- Disk: 60 GB

### 3. 配置镜像加速（国内用户推荐）

Docker Desktop -> Settings -> Docker Engine

添加以下配置：

```json
{
  "registry-mirrors": [
    "https://mirror.ccs.tencentyun.com",
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

点击 "Apply & Restart"

## 常见问题

### 1. Docker 启动失败

- 检查系统版本是否满足要求（macOS 11 或更高版本）
- 确保有足够的磁盘空间
- 重启电脑后重试

### 2. 权限问题

```bash
sudo chown -R $(whoami) ~/.docker
```

### 3. 端口冲突

检查并关闭占用 Docker 端口的程序：

```bash
lsof -i :2375
lsof -i :2376
```

## 卸载 Docker Desktop

如需卸载：

```bash
# 停止 Docker
osascript -e 'quit app "Docker"'

# 删除应用
rm -rf /Applications/Docker.app

# 删除数据（可选）
rm -rf ~/Library/Group\ Containers/group.com.docker
rm -rf ~/Library/Containers/com.docker.docker
rm -rf ~/.docker
```

## 下一步

安装完成后，进入项目的 test 目录启动测试环境：

```bash
cd /Users/gakki/dev/remoteCI/test
./start-docker.sh
```
