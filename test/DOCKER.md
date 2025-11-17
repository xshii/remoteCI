# Remote CI - Docker 测试环境指南

⚠️ **重要提示：本配置仅用于本地测试环境，不适用于生产部署！**

## 概述

本目录包含 Remote CI 的 Docker 测试环境配置。所有容器都带有 `-test-` 前缀，使用测试专用的配置。

## 快速开始

### 1. 使用快速启动脚本（推荐）

```bash
cd test
./start-docker.sh
```

### 2. 手动启动

```bash
cd test

# 构建镜像并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 访问服务

服务启动后，可以访问：

- **Web 管理界面**: http://localhost:5000
- **API 健康检查**: http://localhost:5000/api/health
- **测试 Token**: `test-token-only`
- **Celery 监控** (可选): http://localhost:5555

## 服务说明

### 测试环境服务

1. **remoteCI-test-redis**: Redis 消息队列和结果后端
   - 端口: 6379
   - 数据持久化: redis_data volume

2. **remoteCI-test-api**: Flask API 服务
   - 端口: 5000
   - 提供 REST API 和 Web 界面
   - 健康检查: `/api/health`

3. **remoteCI-test-worker**: Celery Worker
   - 执行构建任务
   - 并发数由 `CI_MAX_CONCURRENT` 控制

### 可选服务

4. **remoteCI-test-flower**: Celery 监控面板
   - 端口: 5555
   - 默认不启动，需要手动启用

启动 Flower:
```bash
cd test
docker-compose --profile monitoring up -d
```

## 常用命令

**注意：所有命令都需要在 `test` 目录下执行**

### 服务管理

```bash
cd test

# 启动服务（推荐使用脚本）
./start-docker.sh

# 停止服务（推荐使用脚本）
./stop-docker.sh

# 或手动管理
docker-compose up -d
docker-compose stop
docker-compose restart
docker-compose down
docker-compose down -v  # 删除所有数据
```

### 日志查看

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f redis

# 查看最近 100 行日志
docker-compose logs --tail=100 -f
```

### 服务重启

```bash
# 重启 API 服务
docker-compose restart api

# 重启 Worker（当修改代码后）
docker-compose restart worker

# 重建并重启服务
docker-compose up -d --build
```

### 进入容器

```bash
# 进入 API 容器
docker-compose exec api bash

# 进入 Worker 容器
docker-compose exec worker bash

# 执行 Python 命令
docker-compose exec api python -c "print('Hello')"
```

## 数据持久化

项目使用以下 volumes 持久化数据：

- `./data`: 日志、上传文件、数据库文件
- `redis_data`: Redis 数据
- `ci_workspace`: rsync 模式的工作空间
- `ci_work`: 临时构建目录

### 备份数据

```bash
# 备份 data 目录
tar -czf backup-data-$(date +%Y%m%d).tar.gz ./data

# 备份数据库
docker-compose exec api tar -czf /tmp/backup.tar.gz /app/data
docker cp remoteCI-api:/tmp/backup.tar.gz ./backup.tar.gz
```

## 健康检查

### 检查所有服务状态

```bash
# 查看容器健康状态
docker-compose ps

# 测试 API 健康
curl http://localhost:5000/api/health

# 测试 Worker 健康
docker-compose exec worker celery -A server.celery_app inspect ping
```

### 查看统计信息

```bash
# 查看任务统计
curl http://localhost:5000/api/stats

# 查看任务历史
curl http://localhost:5000/api/jobs/history
```

## 性能优化

### 调整并发数

编辑 `.env` 文件：

```bash
# 设置并发任务数为 4
CI_MAX_CONCURRENT=4
```

重启服务：

```bash
docker-compose restart worker
```

### 资源限制

编辑 `docker-compose.yml`，添加资源限制：

```yaml
worker:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
      reservations:
        cpus: '1.0'
        memory: 1G
```

## 故障排查

### Worker 无法连接 Redis

检查 Redis 服务状态：

```bash
docker-compose logs redis
docker-compose exec redis redis-cli ping
```

### API 无法启动

检查端口占用：

```bash
# 检查 5000 端口
lsof -i :5000

# 修改端口（在 .env 中）
CI_API_PORT=5001
```

### 任务执行失败

查看 Worker 日志：

```bash
docker-compose logs -f worker
```

查看任务日志：

```bash
# 日志存储在 data/logs/ 目录
ls -lh data/logs/
tail -f data/logs/<job-id>.log
```

### 清理旧数据

```bash
# 清理 7 天前的日志
docker-compose exec api find /app/data/logs -name "*.log" -mtime +7 -delete

# 清理上传的文件
docker-compose exec api find /app/data/uploads -name "*.tar.gz" -mtime +1 -delete
```

## 测试环境 vs 生产环境

| 项目 | 测试环境 (test/) | 生产环境 |
|------|-----------------|---------|
| 用途 | 本地开发测试 | 正式部署 |
| 容器名称 | remoteCI-test-* | remoteCI-* |
| API Token | test-token-only | 强密码 |
| 数据持久化 | 可随时删除 | 必须备份 |
| HTTPS | 不需要 | 必须配置 |
| 反向代理 | 不需要 | Nginx/Traefik |
| 资源限制 | 无 | 需要配置 |
| 监控告警 | 可选 | 推荐配置 |

**生产环境部署建议：**

本测试配置不适用于生产环境。生产环境部署时请：

1. 创建独立的生产环境配置
2. 使用强 API Token
3. 配置 HTTPS 和反向代理
4. 设置资源限制和监控
5. 配置定期备份
6. 使用日志轮转

## 客户端测试

配置测试环境变量：

```bash
export REMOTE_CI_API=http://localhost:5000
export REMOTE_CI_TOKEN=test-token-only
```

使用客户端提交测试任务：

```bash
cd ..  # 回到项目根目录

# Upload 模式测试
python client/submit.py upload "echo 'Hello Test'"

# 查看任务状态
curl http://localhost:5000/api/stats
curl http://localhost:5000/api/jobs/history
```

## 更新升级

```bash
# 拉取最新代码
git pull

# 重建镜像
docker-compose build

# 重启服务
docker-compose up -d

# 查看新版本运行状态
docker-compose ps
docker-compose logs -f
```
