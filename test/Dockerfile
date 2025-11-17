FROM python:3.8-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    rsync \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 清华源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用清华源）
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY server/ ./server/
COPY client/ ./client/

# 创建必要的目录
RUN mkdir -p /app/data/logs /app/data/uploads /var/ci-workspace /tmp/remote-ci

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    CI_DATA_DIR=/app/data \
    CI_WORK_DIR=/tmp/remote-ci \
    CI_WORKSPACE_DIR=/var/ci-workspace

# 暴露端口
EXPOSE 5000

# 默认命令（会被 docker-compose 覆盖）
CMD ["python", "-m", "server.app"]
