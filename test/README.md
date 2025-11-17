# Remote CI - Docker 测试环境

⚠️ **注意：此目录仅用于本地 Docker 测试，不适用于生产环境**

## 目录说明

本目录包含 Remote CI 的 Docker 测试环境配置，用于快速搭建本地测试环境。

## 快速开始

### 1. 启动测试环境

```bash
cd test
./start-docker.sh
```

### 2. 访问服务

启动成功后，可以访问：

- **Web 管理界面**: http://localhost:5000
- **API 健康检查**: http://localhost:5000/api/health
- **测试 Token**: `test-token-only`

### 3. 停止测试环境

```bash
cd test
./stop-docker.sh
```

## 文件说明

- `Dockerfile` - Docker 镜像构建文件
- `docker-compose.yml` - 多服务编排配置
- `.dockerignore` - Docker 构建排除规则
- `start-docker.sh` - 快速启动脚本
- `stop-docker.sh` - 停止服务脚本
- `DOCKER.md` - 详细使用文档

## 服务说明

测试环境包含以下服务：

1. **remoteCI-test-redis** - Redis 消息队列（端口 6379）
2. **remoteCI-test-api** - Flask API 服务（端口 5000）
3. **remoteCI-test-worker** - Celery 任务执行器
4. **remoteCI-test-flower** - Celery 监控（端口 5555，可选）

所有容器都带有 `-test-` 前缀，与生产环境区分。

## 常用命令

```bash
# 启动服务
./start-docker.sh

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api
docker-compose logs -f worker

# 重启服务
docker-compose restart

# 停止服务
docker-compose stop

# 完全停止并清理
./stop-docker.sh
```

## 启用 Flower 监控

```bash
docker-compose --profile monitoring up -d
```

访问 http://localhost:5555 查看 Celery 任务监控。

## 测试客户端

在测试环境中提交任务：

```bash
# 设置环境变量
export REMOTE_CI_API=http://localhost:5000
export REMOTE_CI_TOKEN=test-token-only

# Upload 模式测试
cd ..
python client/submit.py upload "echo 'Hello Test'"

# 查看任务状态
curl http://localhost:5000/api/stats
```

## 数据持久化

测试环境数据存储在：

- `../data/` - 日志、上传文件、数据库
- Docker volumes - Redis 数据、workspace

清理测试数据：

```bash
./stop-docker.sh  # 选择选项 3 删除所有数据
```

## 故障排查

### 端口冲突

如果 5000 或 6379 端口被占用，修改 `docker-compose.yml`：

```yaml
ports:
  - "5001:5000"  # 修改为其他端口
```

### 查看容器状态

```bash
docker-compose ps
docker-compose logs -f
```

### 重建镜像

```bash
docker-compose build --no-cache
docker-compose up -d
```

## 与生产环境的区别

| 项目 | 测试环境 | 生产环境 |
|------|---------|---------|
| 容器名称 | remoteCI-test-* | remoteCI-* |
| API Token | test-token-only | 需要配置强密码 |
| 数据卷 | 可随时删除 | 需要备份 |
| 资源限制 | 无限制 | 建议配置 |
| HTTPS | 不支持 | 必须配置 |

## 更多信息

详细的使用说明请查看 `DOCKER.md` 文档。
