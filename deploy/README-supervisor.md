# Remote CI - Supervisor 部署指南

适用于 Docker 容器或禁用 systemd 的环境。

## 快速开始

### 1. 使用安装脚本（推荐）

```bash
# 下载并运行安装脚本
sudo bash deploy/install-server-supervisor.sh
```

脚本会自动完成：
- 安装系统依赖（包括 supervisor）
- 创建服务用户和目录
- 安装 Python 依赖
- 配置环境变量
- 创建 Supervisor 配置

### 2. 手动安装

如果你想手动配置，按照以下步骤：

#### 步骤 1: 安装依赖

```bash
apt-get update
apt-get install -y python3 python3-pip python3-venv redis-server supervisor git rsync curl
```

#### 步骤 2: 创建目录和用户

```bash
# 创建服务用户
useradd -r -m -s /bin/bash ci-user

# 创建目录
mkdir -p /opt/remote-ci
mkdir -p /var/lib/remote-ci/{logs,uploads}
mkdir -p /var/ci-workspace
mkdir -p /var/log/remote-ci

# 设置权限
chown -R ci-user:ci-user /var/lib/remote-ci
chown -R ci-user:ci-user /var/ci-workspace
chown -R ci-user:ci-user /var/log/remote-ci
```

#### 步骤 3: 安装 Remote CI

```bash
cd /opt/remote-ci

# 复制项目文件
cp -r /path/to/remoteCI/{server,client,requirements.txt,.env.example} .

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，修改配置
nano .env
```

#### 步骤 4: 配置 Supervisor

```bash
# 复制配置文件
cp /opt/remote-ci/deploy/supervisor.conf /etc/supervisor/conf.d/remote-ci.conf

# 重新加载配置
supervisorctl reread
supervisorctl update
```

## 服务管理

### 启动服务

```bash
# 启动所有服务
sudo supervisorctl start remote-ci:*

# 启动单个服务
sudo supervisorctl start remote-ci-api
sudo supervisorctl start remote-ci-worker
sudo supervisorctl start remote-ci-redis
```

### 停止服务

```bash
# 停止所有服务
sudo supervisorctl stop remote-ci:*

# 停止单个服务
sudo supervisorctl stop remote-ci-api
```

### 重启服务

```bash
# 重启所有服务
sudo supervisorctl restart remote-ci:*

# 重启单个服务
sudo supervisorctl restart remote-ci-api
```

### 查看状态

```bash
# 查看所有服务状态
sudo supervisorctl status remote-ci:*

# 查看单个服务状态
sudo supervisorctl status remote-ci-api
```

### 查看日志

```bash
# 使用 supervisorctl 查看日志
sudo supervisorctl tail -f remote-ci-api
sudo supervisorctl tail -f remote-ci-worker

# 或直接查看日志文件
sudo tail -f /var/log/remote-ci/api.log
sudo tail -f /var/log/remote-ci/worker.log
```

## Docker 容器中使用

在 Docker 容器中，建议使用以下方式：

### Dockerfile 示例

```dockerfile
FROM python:3.8-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    supervisor \
    redis-server \
    git \
    rsync \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建目录
RUN mkdir -p /opt/remote-ci /var/lib/remote-ci /var/log/remote-ci

# 复制项目文件
COPY . /opt/remote-ci/
WORKDIR /opt/remote-ci

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制 supervisor 配置
COPY deploy/supervisor.conf /etc/supervisor/conf.d/remote-ci.conf

# 暴露端口
EXPOSE 5000 5555

# 启动 supervisor
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
```

### docker-compose.yml 示例

```yaml
version: '3.8'

services:
  remote-ci:
    build: .
    container_name: remote-ci
    ports:
      - "5000:5000"
      - "5555:5555"
    volumes:
      - ./data:/var/lib/remote-ci
      - ci-workspace:/var/ci-workspace
    environment:
      - CI_API_HOST=0.0.0.0
      - CI_API_PORT=5000
      - CI_API_TOKEN=your-secret-token
      - CI_BROKER_URL=redis://localhost:6379/0
      - CI_RESULT_BACKEND=redis://localhost:6379/0
      - CI_DATA_DIR=/var/lib/remote-ci
      - CI_WORKSPACE_DIR=/var/ci-workspace
    restart: unless-stopped

volumes:
  ci-workspace:
```

## 配置文件说明

### supervisor.conf 主要配置项

- **command**: 服务启动命令
- **directory**: 工作目录
- **user**: 运行用户
- **autostart**: 是否自动启动
- **autorestart**: 是否自动重启
- **startretries**: 启动失败重试次数
- **stdout_logfile**: 标准输出日志文件
- **stderr_logfile**: 错误输出日志文件
- **priority**: 启动优先级（数字越小越先启动）

### 服务说明

1. **remote-ci-redis** (priority=10)
   - Redis 服务，提供消息队列和结果存储
   - 最先启动

2. **remote-ci-api** (priority=20)
   - Flask API 服务器
   - 依赖 Redis

3. **remote-ci-worker** (priority=30)
   - Celery Worker，执行构建任务
   - 依赖 Redis

4. **remote-ci-flower** (priority=40)
   - Celery 监控面板（可选）
   - 默认不自动启动

## 故障排查

### 服务无法启动

1. 检查日志：
   ```bash
   sudo supervisorctl tail remote-ci-api
   ```

2. 检查配置：
   ```bash
   sudo supervisorctl status
   ```

3. 重新加载配置：
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   ```

### Redis 连接失败

检查 Redis 是否正常运行：
```bash
redis-cli ping
# 应该返回: PONG
```

### 权限问题

确保日志目录权限正确：
```bash
sudo chown -R ci-user:ci-user /var/log/remote-ci
```

## 卸载

```bash
# 停止所有服务
sudo supervisorctl stop remote-ci:*

# 删除配置
sudo rm /etc/supervisor/conf.d/remote-ci*.conf
sudo supervisorctl reread
sudo supervisorctl update

# 删除文件
sudo rm -rf /opt/remote-ci
sudo rm -rf /var/lib/remote-ci
sudo rm -rf /var/log/remote-ci

# 删除用户
sudo userdel -r ci-user
```

## 参考资料

- [Supervisor 官方文档](http://supervisord.org/)
- [Remote CI 主文档](../README.md)
- [Docker 部署指南](../test/DOCKER.md)
