# Remote CI Python 客户端

本目录包含 Remote CI 客户端的 Python 版本脚本，功能与 Bash 脚本完全相同。

## 🎯 为什么使用 Python 版本？

- ✅ **跨平台兼容性**：可在 Linux、macOS、Windows 上运行
- ✅ **更好的错误处理**：提供更详细的错误信息
- ✅ **易于扩展**：Python 代码更容易阅读和修改
- ✅ **统一依赖管理**：使用标准的 Python 包管理

## 📋 文件说明

| Python 脚本 | Bash 脚本对应 | 说明 |
|------------|--------------|------|
| `submit.py` | - | **统一客户端（整合upload/rsync/git三种模式）** |
| `config_example.py` | `config.sh.example` | 配置文件示例 |

**优势**：
- ✅ 单一脚本，更易维护
- ✅ 统一的命令行接口
- ✅ 代码复用，减少重复
- ✅ 支持所有功能（upload、rsync、git、自定义排除、user_id等）

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

### 3. 使用客户端

#### Upload模式（上传代码）

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

#### Rsync模式（同步代码）

**⭐ 自动用户隔离（推荐）**

Rsync模式自动为每个用户创建独立workspace，避免多人并发冲突：

```bash
# 基础用法 - 自动检测用户并隔离（推荐）
python3 submit.py rsync myproject "npm test"
# → workspace: myproject-alice（自动检测GitLab/GitHub/Jenkins用户）

# UUID模式 - 完全隔离（调试用）
python3 submit.py rsync myproject "npm test" --uuid
# → workspace: myproject-alice-a1b2c3d4（按用户分组，每次独立）

# 手动指定用户
python3 submit.py rsync myproject "npm test" --user-id bob
# → workspace: myproject-bob

# 禁用隔离（不推荐）
python3 submit.py rsync myproject "npm test" --no-user-suffix
# → workspace: myproject（多人并发可能冲突！）

# 需要先配置环境变量
export REMOTE_CI_HOST="ci-user@remote-ci-server"
export WORKSPACE_BASE="/var/ci-workspace"
```

**Workspace隔离效果：**
```
/var/ci-workspace/
  ├── myproject-alice/          ← Alice的独立空间（复用缓存）
  ├── myproject-alice-a1b2c3d4  ← Alice的UUID调试workspace
  ├── myproject-bob/            ← Bob的独立空间
  └── myproject-charlie/        ← Charlie的独立空间
```

**支持的CI系统用户检测：**
- GitLab CI: `$GITLAB_USER_LOGIN`
- GitHub Actions: `$GITHUB_ACTOR`
- Jenkins: `$BUILD_USER`
- CircleCI: `$CIRCLE_USERNAME`
- Travis CI: `$TRAVIS_BUILD_USER`
- 本地环境: `$USER`

#### Git模式（克隆代码）

```bash
# 克隆并构建
python3 submit.py git https://github.com/user/repo.git main "npm test"

# 指定commit
python3 submit.py git https://github.com/user/repo.git main "npm test" --commit abc123

# 带用户ID
python3 submit.py git https://github.com/user/repo.git main "npm test" --user-id 12345
```

#### 查看帮助

```bash
python3 submit.py --help              # 总体帮助
python3 submit.py upload --help       # Upload模式帮助
python3 submit.py rsync --help        # Rsync模式帮助
python3 submit.py git --help          # Git模式帮助
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
    - python3 client/submit.py upload "npm install && npm test" --project $CI_PROJECT_NAME
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
        run: python3 client/submit.py upload "npm install && npm test" --project ${{ github.event.repository.name }}
```

## 🔧 环境变量说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `REMOTE_CI_API` | 远程CI API地址 | `http://remote-ci-server:5000` |
| `REMOTE_CI_TOKEN` | API认证Token | `your-api-token` |
| `REMOTE_CI_USER_ID` | 用户ID（可选） | - |
| `REMOTE_CI_HOST` | SSH地址（rsync模式） | `ci-user@remote-ci-server` |
| `WORKSPACE_BASE` | Workspace目录（rsync模式） | `/var/ci-workspace` |
| `CI_TIMEOUT` | 等待超时时间（秒） | `1500` (25分钟) |

## 📦 依赖说明

### 必需依赖

- **Python 3.8+**：脚本运行环境
- **requests**：HTTP 请求库（`pip3 install requests`）

### 可选依赖（按模式）

- **rsync**：rsync模式需要
- **ssh**：rsync模式需要
- **git**：git模式需要（通常已预装）

## 💡 高级用法

### Workspace隔离（Rsync模式）

**问题：多人并发冲突**

在多人团队中，如果都使用同一个workspace，后提交的会覆盖先提交的代码：
```
10:00:00 - Alice rsync → /var/ci-workspace/myproject (Alice的代码)
10:00:05 - Bob rsync → /var/ci-workspace/myproject (覆盖成Bob的代码！)
结果：Alice的任务执行了Bob的代码 ❌
```

**解决：自动用户隔离**

客户端自动为每个用户创建独立workspace：
```bash
# 默认启用用户隔离（推荐）
python3 submit.py rsync myproject "make -j8"
# → workspace: myproject-alice
# → 复用编译缓存，增量编译快速

# UUID模式（调试/一次性任务）
python3 submit.py rsync myproject "make -j8" --uuid
# → workspace: myproject-alice-a1b2c3d4
# → 按用户分组，完全隔离，不复用缓存
```

**三种模式对比：**

| 模式 | Workspace | 缓存 | 冲突 | 适用场景 |
|------|-----------|------|------|---------|
| **用户模式** | `project-alice` | ✅ 复用 | ❌ 无 | 日常开发（推荐） |
| **UUID模式** | `project-alice-uuid` | ❌ 不复用 | ❌ 无 | 调试/压力测试 |
| **禁用隔离** | `project` | ✅ 复用 | ⚠️ 有 | 单人使用 |

**实际效果：**
```
远程CI目录结构：
/var/ci-workspace/
  ├── myproject-alice/      ← Alice（复用build/缓存，5秒增量编译）
  ├── myproject-bob/        ← Bob（复用build/缓存）
  └── myproject-charlie/    ← Charlie（复用build/缓存）

/opt/heavy-libs/            ← 预装库（所有人共享，只读）
  ├── include/
  └── lib/
```

**清理UUID临时workspace：**
```bash
# 在远程CI服务器上，清理1天前的UUID workspace
find /var/ci-workspace -name "*-*-????????" -mtime +1 -exec rm -rf {} \;

# 添加到crontab（每天凌晨2点自动清理）
0 2 * * * find /var/ci-workspace -name "*-*-????????" -mtime +1 -exec rm -rf {} \;
```

### 自定义超时时间

```bash
# 设置40分钟超时
export CI_TIMEOUT=2400
python3 submit.py upload "npm test"
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
chmod +x submit.py
```

### 问题3: rsync 命令未找到（rsync模式）

```bash
# Ubuntu/Debian
sudo apt-get install rsync

# CentOS/RHEL
sudo yum install rsync

# macOS
brew install rsync
```

### 问题4: git 命令未找到（git模式）

```bash
# Ubuntu/Debian
sudo apt-get install git

# CentOS/RHEL
sudo yum install git

# macOS (通常已预装)
brew install git
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
