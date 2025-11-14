# Remote CI Python 客户端

本目录包含 Remote CI 客户端的 Python 版本脚本，功能与 Bash 脚本完全相同。

## 🎯 为什么使用 Python 版本？

- ✅ **跨平台兼容性**：可在 Linux、macOS、Windows 上运行
- ✅ **更好的错误处理**：提供更详细的错误信息
- ✅ **易于扩展**：Python 代码更容易阅读和修改
- ✅ **统一依赖管理**：使用标准的 Python 包管理

## 🚀 推荐：使用统一客户端

**新增**：`submit.py` - 统一的客户端脚本，整合了所有模式（upload、rsync、git）。

```bash
# Upload模式
python3 submit.py upload "npm test" --project myapp

# Rsync模式
python3 submit.py rsync myproject "npm test"

# Git模式
python3 submit.py git https://github.com/user/repo.git main "npm test"

# 查看帮助
python3 submit.py --help
python3 submit.py upload --help
```

**优势**：
- ✅ 单一脚本，更易维护
- ✅ 统一的命令行接口
- ✅ 代码复用，减少重复
- ✅ 支持所有功能（包括自定义排除、user_id等）

## 📋 文件说明

| Python 脚本 | Bash 脚本对应 | 说明 | 状态 |
|------------|--------------|------|------|
| `submit.py` | - | **统一客户端（推荐）** | ✅ 推荐使用 |
| `submit-upload.py` | `submit-upload.sh` | 上传模式客户端 | 📦 保留兼容 |
| `submit-upload-custom.py` | `submit-upload-custom.sh` | 支持自定义排除规则的上传模式 | 📦 保留兼容 |
| `submit-rsync.py` | `submit-rsync.sh` | rsync 模式客户端 | 📦 保留兼容 |
| `config_example.py` | `config.sh.example` | 配置文件示例 | - |

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Python 3.8+
python3 --version

# 安装依赖包
pip3 install requests
```

### 2. 配置环境变量

```bash
# 方法1: 直接设置环境变量（推荐）
export REMOTE_CI_API="http://your-server:5000"
export REMOTE_CI_TOKEN="your-secret-token"
export REMOTE_CI_USER_ID="12345"  # 可选，用于标识用户

# 方法2: 创建配置文件
cp config_example.py config.py
# 编辑 config.py，修改配置
```

### 3. 使用统一客户端（推荐）

#### Upload模式

```bash
# 基础用法 - 上传当前目录
python3 submit.py upload "npm test"

# 指定项目名
python3 submit.py upload "npm test" --project myapp

# 只上传指定目录
python3 submit.py upload "npm test" --path "src/ tests/"

# 自定义排除规则
python3 submit.py upload "npm test" --exclude "*.log,*.tmp,cache/"

# 完整示例
python3 submit.py upload "npm test" --project myapp --user-id 12345 --path "src/" --exclude "*.log"
```

#### Rsync模式

```bash
# 基础用法
python3 submit.py rsync myproject "npm test"

# 带用户ID
python3 submit.py rsync myproject "npm test" --user-id 12345

# 需要先配置环境变量
export REMOTE_CI_HOST="ci-user@remote-ci-server"
export WORKSPACE_BASE="/var/ci-workspace"
```

#### Git模式

```bash
# 克隆并构建
python3 submit.py git https://github.com/user/repo.git main "npm test"

# 指定commit
python3 submit.py git https://github.com/user/repo.git main "npm test" --commit abc123

# 带用户ID
python3 submit.py git https://github.com/user/repo.git main "npm test" --user-id 12345
```

### 4. 使用独立脚本（兼容旧版）

#### 上传模式

```bash
# 基础用法 - 上传当前目录
python3 submit-upload.py "npm test"

# 只上传指定目录
python3 submit-upload.py "npm test" "src/ tests/"
```

#### 自定义上传模式

```bash
# 只上传特定目录
python3 submit-upload-custom.py "npm test" "src/ tests/" ""

# 上传时排除指定文件
python3 submit-upload-custom.py "npm test" "." "*.log,*.tmp,cache/"
```

#### rsync 模式

```bash
# 需要先配置 SSH 密钥
python3 submit-rsync.py myproject "npm test"
```

## 📝 使用示例

### GitLab CI 集成

```yaml
# .gitlab-ci.yml
remote_build:
  stage: build
  timeout: 30m
  variables:
    REMOTE_CI_API: "http://your-server:5000"
  before_script:
    - pip3 install requests
  script:
    - python3 client/submit-upload.py "npm install && npm test"
```

### GitHub Actions 集成

```yaml
# .github/workflows/ci.yml
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: pip3 install requests
      - name: Submit to Remote CI
        env:
          REMOTE_CI_API: ${{ secrets.REMOTE_CI_API }}
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: python3 client/submit-upload.py "npm install && npm test"
```

## 🔧 环境变量说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `REMOTE_CI_API` | 远程CI API地址 | `http://remote-ci-server:5000` |
| `REMOTE_CI_TOKEN` | API认证Token | `your-api-token` |
| `REMOTE_CI_HOST` | SSH地址（rsync模式） | `ci-user@remote-ci-server` |
| `WORKSPACE_BASE` | Workspace目录（rsync模式） | `/var/ci-workspace` |
| `CI_TIMEOUT` | 等待超时时间（秒） | `1500` (25分钟) |

## 📦 依赖说明

### 必需依赖

- **Python 3.8+**：所有脚本的运行环境
- **requests**：HTTP 请求库（`pip3 install requests`）

### 可选依赖

- **rsync**：仅 `submit-rsync.py` 需要
- **ssh**：仅 `submit-rsync.py` 需要

## 💡 高级用法

### 自定义超时时间

```bash
# 设置40分钟超时
export CI_TIMEOUT=2400
python3 submit-upload.py "npm test"
```

### 使用配置文件

```python
# config.py
REMOTE_CI_API = "http://192.168.1.100:5000"
REMOTE_CI_TOKEN = "your-secret-token"

# 在脚本中会自动读取环境变量
```

### 查看配置

```bash
# 检查当前配置
python3 config_example.py
```

## 🐛 故障排查

### 问题1: ModuleNotFoundError: No module named 'requests'

```bash
# 解决方案：安装 requests 库
pip3 install requests
```

### 问题2: 权限被拒绝

```bash
# 解决方案：添加可执行权限
chmod +x submit-upload.py
```

### 问题3: rsync 命令未找到

```bash
# Ubuntu/Debian
sudo apt-get install rsync

# CentOS/RHEL
sudo yum install rsync

# macOS
brew install rsync
```

## 🔄 与 Bash 脚本的兼容性

Python 脚本和 Bash 脚本功能完全相同，可以互换使用：

```bash
# 这两个命令效果相同
bash submit-upload.sh "npm test"
python3 submit-upload.py "npm test"
```

## 📚 更多信息

- 详细文档：[../README.md](../README.md)
- 使用示例：[../examples/](../examples/)
- 问题反馈：GitHub Issues

## ⚡ 性能提示

1. **使用上传模式**：对于小项目（<10MB）推荐使用上传模式
2. **选择性上传**：只上传必要的文件，减少传输时间
3. **rsync 增量同步**：大项目频繁构建时使用 rsync 模式

## 🔐 安全提示

1. **不要硬编码 Token**：使用环境变量或 CI Secret
2. **Token 权限最小化**：只授予必要的权限
3. **定期轮换 Token**：每季度更换一次
4. **启用 HTTPS**：生产环境必须使用 HTTPS

---

**提示**：如果您在 Windows 环境下使用，建议使用 Python 版本而不是 Bash 脚本。
