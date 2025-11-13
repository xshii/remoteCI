# 选择性上传示例

## 使用场景

当你的项目很大，但只需要上传部分代码时，可以使用选择性上传功能。

## 基础示例

### 1. 只上传源码目录

```bash
# 只上传src目录
bash client/submit-upload.sh "npm run build" "src/"

# 结果：只有src目录被打包上传，其他文件被忽略
```

### 2. 上传多个目录

```bash
# 上传src和tests目录
bash client/submit-upload.sh "npm test" "src/ tests/"

# 上传源码、测试和配置文件
bash client/submit-upload.sh "npm test" "src/ tests/ package.json"
```

### 3. 自定义排除规则

```bash
# 上传当前目录，但额外排除日志和缓存
bash client/submit-upload-custom.sh \
  "npm test" \
  "." \
  "*.log,*.tmp,cache/,.DS_Store"
```

---

## 实际项目示例

### Node.js前端项目

```bash
# 只上传必要的文件，跳过示例和文档
bash client/submit-upload-custom.sh \
  "npm install && npm run build" \
  "src/ public/ package.json package-lock.json tsconfig.json webpack.config.js" \
  ""

# 打包大小对比：
# 完整项目：50MB
# 选择性上传：8MB（减少84%）
```

### Python后端项目

```bash
# 只上传源码和依赖声明
bash client/submit-upload-custom.sh \
  "pip install -r requirements.txt && pytest" \
  "app/ tests/ requirements.txt setup.py" \
  "*.pyc,__pycache__"

# 打包大小对比：
# 完整项目：30MB（含虚拟环境、文档）
# 选择性上传：2MB（减少93%）
```

### Monorepo项目

```bash
# 只上传单个包
bash client/submit-upload.sh \
  "cd packages/api && npm install && npm test" \
  "packages/api/"

# 只上传受影响的包
bash client/submit-upload.sh \
  "npm test" \
  "packages/api/ packages/shared/ package.json"
```

### Go项目

```bash
# 只上传源码
bash client/submit-upload-custom.sh \
  "go build && go test ./..." \
  "cmd/ pkg/ internal/ go.mod go.sum" \
  ""
```

### Java Maven项目

```bash
# 只上传源码和POM
bash client/submit-upload-custom.sh \
  "mvn clean install" \
  "src/ pom.xml" \
  "target/"
```

---

## GitLab CI集成

```yaml
# .gitlab-ci.yml
variables:
  REMOTE_CI_API: "http://remote-ci:5000"

# 方式1: 使用基础脚本
build_frontend:
  script:
    # 只上传src和配置文件
    - bash client/submit-upload.sh "npm run build" "src/ package.json"

# 方式2: 使用自定义脚本
build_backend:
  script:
    # 上传应用代码，排除测试数据
    - bash client/submit-upload-custom.sh
        "pytest"
        "app/ tests/ requirements.txt"
        "test_data/"

# 方式3: Monorepo - 只构建变更的包
build_package:
  script:
    # 检测变更的包
    - CHANGED_PACKAGE=$(git diff --name-only HEAD^ HEAD | grep "packages/" | cut -d'/' -f2 | sort -u | head -n1)
    - if [ -n "$CHANGED_PACKAGE" ]; then
        bash client/submit-upload.sh
          "cd packages/$CHANGED_PACKAGE && npm test"
          "packages/$CHANGED_PACKAGE/";
      fi
```

---

## GitHub Actions集成

```yaml
# .github/workflows/selective-build.yml
name: Selective Build

on:
  push:
    paths:
      - 'src/**'
      - 'tests/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Upload only source code
        env:
          REMOTE_CI_API: ${{ secrets.REMOTE_CI_API }}
          REMOTE_CI_TOKEN: ${{ secrets.REMOTE_CI_TOKEN }}
        run: |
          curl -O https://raw.githubusercontent.com/your-org/remoteCI/main/client/submit-upload-custom.sh
          bash submit-upload-custom.sh \
            "npm run build" \
            "src/ tests/ package.json" \
            ""
```

---

## 性能对比

### 大型前端项目

```
项目结构：
├── src/              (5MB)
├── tests/            (2MB)
├── docs/             (15MB)
├── examples/         (10MB)
├── node_modules/     (200MB - 已默认排除)
└── 其他              (5MB)

上传方式对比：

1. 完整上传：
   - 大小：37MB（排除node_modules后）
   - 时间：35秒 @ 10Mbps

2. 选择性上传（src/ tests/ package.json）：
   - 大小：7MB
   - 时间：7秒 @ 10Mbps
   - 节省：80%时间

3. 结论：
   选择性上传在大项目中效果显著
```

### Monorepo项目

```
项目结构：
packages/
├── api/      (10MB)
├── web/      (20MB)
├── mobile/   (30MB)
├── shared/   (5MB)
└── docs/     (10MB)

场景：只修改了api包

1. 完整上传：75MB → 70秒
2. 只上传api包：10MB → 10秒
3. 节省：86%时间
```

---

## 最佳实践

### 1. 按需上传

```bash
# ✅ 好的做法
bash client/submit-upload.sh "npm test" "src/ tests/"

# ❌ 不推荐
bash client/submit-upload.sh "npm test"  # 上传所有不必要的文件
```

### 2. 配合.gitignore

```bash
# 创建.ciignore文件
cat > .ciignore <<EOF
docs/
examples/
*.md
*.txt
.vscode/
.idea/
EOF

# 使用自定义脚本读取.ciignore
# （需要修改脚本支持）
```

### 3. Monorepo优化

```bash
# 检测变更的包
CHANGED_PACKAGES=$(git diff --name-only HEAD^ HEAD | grep "packages/" | cut -d'/' -f2 | sort -u)

# 只上传变更的包
for pkg in $CHANGED_PACKAGES; do
  bash client/submit-upload.sh \
    "cd packages/$pkg && npm test" \
    "packages/$pkg/ packages/shared/"
done
```

### 4. 缓存依赖（远程CI）

```bash
# 首次：上传依赖声明，远程CI安装
bash client/submit-upload.sh \
  "npm install" \
  "package.json package-lock.json"

# 后续：只上传源码（依赖已缓存）
bash client/submit-upload.sh \
  "npm test" \
  "src/ tests/"
```

---

## 故障排查

### 问题1: 上传后文件不存在

```bash
# 检查打包内容
tar -tzf /tmp/ci-code-*.tar.gz

# 确保路径正确
bash client/submit-upload.sh "npm test" "src/"  # 正确
bash client/submit-upload.sh "npm test" "./src" # 可能有问题
```

### 问题2: 排除规则不生效

```bash
# 检查排除语法
bash client/submit-upload-custom.sh \
  "npm test" \
  "." \
  "*.log,cache/"  # 逗号分隔，无空格
```

### 问题3: Monorepo路径问题

```bash
# 确保构建脚本中的路径正确
bash client/submit-upload.sh \
  "cd packages/api && npm test" \  # cd到正确的目录
  "packages/api/"
```

---

## 高级技巧

### 1. 动态排除

```bash
# 根据文件大小排除
find . -size +10M -name "*.dat" > large_files.txt
EXCLUDES=$(cat large_files.txt | tr '\n' ',' | sed 's/,$//')
bash client/submit-upload-custom.sh "npm test" "." "$EXCLUDES"
```

### 2. 增量上传模拟

```bash
# 第一次：上传完整项目
bash client/submit-upload.sh "npm install"

# 后续：只上传变更的文件
git diff --name-only HEAD^ HEAD > changed_files.txt
CHANGED=$(cat changed_files.txt | tr '\n' ' ')
bash client/submit-upload.sh "npm test" "$CHANGED"
```

### 3. 多阶段构建

```bash
# 阶段1: 安装依赖（只上传package.json）
bash client/submit-upload.sh \
  "npm install" \
  "package.json package-lock.json"

# 阶段2: 运行测试（只上传源码）
bash client/submit-upload.sh \
  "npm test" \
  "src/ tests/"

# 阶段3: 构建（只上传必要文件）
bash client/submit-upload.sh \
  "npm run build" \
  "src/ public/ webpack.config.js"
```

---

## 总结

选择性上传的优势：
- ✅ 减少传输时间（最多节省90%）
- ✅ 降低网络带宽消耗
- ✅ 更快的构建周期
- ✅ 适合大型项目和Monorepo

推荐使用场景：
- 项目>10MB
- Monorepo架构
- 包含大量文档/示例/测试数据
- 网络速度较慢
