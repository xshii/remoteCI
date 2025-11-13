# 项目结构说明

```
remoteCI/
├── client/                      # 公共CI端脚本
│   ├── config.sh.example       # 配置文件示例
│   ├── submit-rsync.sh         # rsync模式提交脚本
│   └── submit-upload.sh        # 上传模式提交脚本
│
├── server/                      # 远程CI服务端
│   ├── __init__.py             # Python包标识
│   ├── app.py                  # Flask API服务（主入口）
│   ├── celery_app.py           # Celery应用初始化
│   ├── config.py               # 配置管理
│   └── tasks.py                # Celery任务定义
│
├── deploy/                      # 部署脚本
│   └── install-server.sh       # 服务器一键安装脚本
│
├── docs/                        # 文档
│   ├── QUICKSTART.md           # 快速启动指南
│   ├── ARCHITECTURE.md         # 架构设计文档
│   └── PROJECT_STRUCTURE.md    # 本文件
│
├── .env.example                 # 环境变量配置示例
├── .gitignore                   # Git忽略文件配置
├── requirements.txt             # Python依赖
└── README.md                    # 项目主文档
```

## 文件说明

### 服务端文件

#### `server/config.py`
- 配置管理模块
- 从环境变量读取配置
- 定义目录结构
- Celery配置

#### `server/celery_app.py`
- Celery应用初始化
- 连接Redis
- 自动发现任务

#### `server/tasks.py`
- 定义构建任务
- 支持三种模式：rsync/upload/git
- 任务执行逻辑
- 日志记录
- 异常处理

#### `server/app.py`
- Flask API服务
- RESTful API端点
- Token认证
- Web管理界面
- 任务提交和查询

### 客户端脚本

#### `client/submit-rsync.sh`
- rsync模式任务提交脚本
- 代码同步
- 任务提交
- 状态轮询
- 结果获取

#### `client/submit-upload.sh`
- 上传模式任务提交脚本
- 代码打包
- 文件上传
- 任务提交
- 结果获取

#### `client/config.sh.example`
- 客户端配置示例
- 需要复制为`config.sh`并修改

### 部署文件

#### `deploy/install-server.sh`
- 服务器一键安装脚本
- 安装系统依赖
- 创建用户和目录
- 安装Python依赖
- 配置systemd服务
- 生成API Token

### 配置文件

#### `.env.example`
- 服务器环境变量配置示例
- 包含所有配置项说明
- 需要复制为`.env`并修改

#### `requirements.txt`
- Python依赖列表
- Flask、Celery、Redis等

## 运行时目录结构

安装后会创建以下目录：

```
/opt/remote-ci/                  # 安装目录
├── server/                      # 服务端代码
├── venv/                        # Python虚拟环境
├── .env                         # 配置文件
└── requirements.txt

/var/lib/remote-ci/              # 数据目录
├── logs/                        # 任务日志
│   └── <job_id>.log
└── uploads/                     # 上传文件（临时）
    └── <timestamp>-code.tar.gz

/var/ci-workspace/               # rsync工作空间
├── project-a/                   # 项目A代码
├── project-b/                   # 项目B代码
└── ...

/tmp/remote-ci/                  # 临时工作目录
└── <job_id>/                    # 任务执行目录（自动清理）
    └── repo/

/var/log/remote-ci/              # 服务日志
├── api.log                      # API服务日志
├── worker.log                   # Worker日志
└── flower.log                   # Flower监控日志（可选）
```

## systemd服务文件

```
/etc/systemd/system/
├── remote-ci-api.service        # API服务
├── remote-ci-worker.service     # Worker服务
└── remote-ci-flower.service     # Flower监控（可选）
```

## 文件权限

```
用户：ci-user
组：ci-user

权限：
/opt/remote-ci/          → ci-user:ci-user (755)
/var/lib/remote-ci/      → ci-user:ci-user (755)
/var/ci-workspace/       → ci-user:ci-user (755)
/var/log/remote-ci/      → ci-user:ci-user (755)
```

## 开发时目录结构

开发环境可以使用相对路径：

```
remoteCI/
├── data/                        # 数据目录（开发）
│   ├── logs/
│   └── uploads/
├── venv/                        # 虚拟环境（开发）
└── .env                         # 配置文件（开发）
```

启动开发服务器：

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env

# 启动Redis（需要单独安装）
redis-server

# 启动API服务
python -m server.app

# 启动Worker（另一个终端）
celery -A server.celery_app worker --loglevel=info
```

## Git忽略规则

`.gitignore`会忽略：

- `__pycache__/` - Python缓存
- `*.pyc` - Python字节码
- `venv/` - 虚拟环境
- `data/` - 数据目录
- `.env` - 配置文件（包含敏感信息）
- `*.log` - 日志文件
- `*.tar.gz` - 临时打包文件

## 依赖关系

### Python依赖

```
Flask (3.0.0)
  └── Werkzeug, Jinja2, click

Celery (5.3.4)
  ├── kombu (消息传递)
  ├── billiard (进程池)
  └── vine (异步工具)

redis (5.0.1)
  └── Redis Python客户端

flower (2.0.1)
  └── Celery监控工具
```

### 系统依赖

```
Python 3.8+
Redis Server
Git
rsync
```

## 扩展建议

如果需要扩展功能，建议的目录结构：

```
remoteCI/
├── server/
│   ├── models/              # 数据模型（如果使用数据库）
│   ├── utils/               # 工具函数
│   ├── middlewares/         # 中间件
│   └── blueprints/          # Flask蓝图（模块化API）
│
├── tests/                   # 测试代码
│   ├── test_api.py
│   └── test_tasks.py
│
└── scripts/                 # 维护脚本
    ├── cleanup_logs.sh
    └── backup.sh
```
