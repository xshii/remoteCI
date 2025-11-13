# 实际用例场景

## 用例1: 前端E2E测试（30-60分钟）

**场景描述：**
- React/Vue前端项目
- E2E测试需要启动多个服务（前端、后端、数据库）
- Cypress/Playwright测试套件执行时间长
- 公共CI只有30分钟超时

**解决方案：rsync模式**

```bash
# .gitlab-ci.yml
remote_e2e:
  script:
    - bash client/submit-rsync.sh frontend-app "
        npm install &&
        docker-compose up -d &&
        npm run test:e2e &&
        docker-compose down
      "
```

**优势：**
- rsync增量同步，node_modules不用每次传输
- 远程CI可以运行超过30分钟
- 公共CI在25分钟后退出，任务继续执行

---

## 用例2: 机器学习模型训练（2-4小时）

**场景描述：**
- Python深度学习项目
- 需要GPU资源
- 训练时间2-4小时
- 公共CI没有GPU

**解决方案：上传模式 + 长时间任务**

```yaml
# .github/workflows/train.yml
- name: Submit Training
  run: |
    bash client/submit-upload.sh "
      pip install -r requirements.txt &&
      CUDA_VISIBLE_DEVICES=0,1 python train.py --epochs 200
    "
```

**配置：**
```bash
# 远程CI配置更长的超时
CI_JOB_TIMEOUT=14400  # 4小时
```

---

## 用例3: Android APK构建（15-30分钟）

**场景描述：**
- Android项目
- Gradle构建需要大量内存和CPU
- 首次构建下载依赖慢
- 公共CI资源受限

**解决方案：rsync模式 + Gradle缓存**

```bash
# Jenkins Pipeline
bash client/submit-rsync.sh android-app "
  ./gradlew clean assembleRelease --no-daemon --max-workers=4 &&
  ./gradlew test
"
```

**远程CI配置：**
```bash
# /var/ci-workspace/android-app/.gradle/ 持久化
# 后续构建利用缓存，速度快
```

---

## 用例4: 多环境集成测试

**场景描述：**
- 微服务项目
- 需要启动10+个服务
- 集成测试覆盖多个场景
- 公共CI资源不足

**解决方案：rsync模式 + Docker Compose**

```bash
bash client/submit-rsync.sh microservices "
  docker-compose -f docker-compose.test.yml up -d &&
  sleep 30 &&
  npm run test:integration &&
  docker-compose down
"
```

---

## 用例5: 数据库迁移测试

**场景描述：**
- 需要测试多个数据库版本的兼容性
- MySQL 5.7, 8.0, PostgreSQL 12, 13, 14
- 每个版本测试10分钟
- 总共50+分钟

**解决方案：并行任务**

```bash
# 提交多个任务并行执行
for DB in mysql57 mysql80 postgres12 postgres13 postgres14; do
  bash client/submit-rsync.sh myapp-$DB "
    docker run -d --name db $DB &&
    npm run migrate &&
    npm run test &&
    docker stop db
  " &
done

wait
```

**远程CI配置：**
```bash
CI_MAX_CONCURRENT=5  # 5个任务并行
```

---

## 用例6: 定时备份和清理（Cron任务）

**场景描述：**
- 定期清理旧的测试数据
- 备份重要文件
- 不依赖公共CI

**解决方案：直接调用API**

```bash
# crontab
0 2 * * * curl -X POST http://remote-ci:5000/api/jobs/rsync \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"workspace":"/var/ci-workspace/cleanup","script":"bash cleanup.sh"}'
```

---

## 用例7: 大型Monorepo构建

**场景描述：**
- 包含20+个子项目的Monorepo
- 需要构建所有项目
- 单个项目5分钟，总共100+分钟

**解决方案：rsync模式 + 增量构建**

```bash
bash client/submit-rsync.sh monorepo "
  # 使用Turborepo/Nx的缓存
  npx turbo run build test --cache-dir=.turbo
"
```

**优势：**
- rsync只同步修改的文件
- Turborepo/Nx缓存未修改项目的构建结果
- 实际构建时间大幅减少

---

## 用例8: 多平台交叉编译

**场景描述：**
- Go/Rust项目需要编译多个平台
- Linux, Windows, macOS
- ARM, x86_64
- 每个平台5分钟，总共30+分钟

**解决方案：上传模式**

```bash
bash client/submit-upload.sh "
  # Go交叉编译
  GOOS=linux GOARCH=amd64 go build -o bin/app-linux-amd64 &&
  GOOS=windows GOARCH=amd64 go build -o bin/app-windows-amd64.exe &&
  GOOS=darwin GOARCH=amd64 go build -o bin/app-darwin-amd64 &&
  GOOS=linux GOARCH=arm64 go build -o bin/app-linux-arm64
"
```

---

## 用例9: 性能测试和基准测试

**场景描述：**
- 需要运行性能测试
- JMeter/k6负载测试
- 需要稳定的测试环境
- 测试时间30-60分钟

**解决方案：rsync模式 + 专用环境**

```bash
bash client/submit-rsync.sh perf-test "
  # 启动应用
  docker-compose up -d app &&
  sleep 10 &&

  # 运行性能测试
  k6 run --vus 100 --duration 30m load-test.js &&

  # 生成报告
  python generate_report.py
"
```

---

## 用例10: 安全扫描

**场景描述：**
- 代码安全扫描（SonarQube）
- 依赖漏洞扫描（Snyk）
- 容器镜像扫描（Trivy）
- 总耗时20-40分钟

**解决方案：上传模式**

```bash
bash client/submit-upload.sh "
  # 代码扫描
  sonar-scanner &&

  # 依赖扫描
  snyk test &&

  # 容器扫描
  docker build -t myapp . &&
  trivy image myapp
"
```

---

## 性能对比

### rsync模式 vs 上传模式

**Node.js项目（100MB源码 + 200MB node_modules）**

| 场景 | rsync首次 | rsync后续 | 上传模式 |
|------|----------|----------|----------|
| 传输时间 | 15秒 | **2秒** | 12秒 |
| 总构建时间 | 5分20秒 | **4分7秒** | 5分17秒 |

**优势：rsync后续构建快70%**

---

## 最佳实践

### 1. 选择合适的模式

```
频繁构建（每天10+次）→ rsync模式
偶尔构建（每天1-2次）→ 上传模式
无SSH权限           → 上传模式
```

### 2. 合理设置超时

```bash
# 快速测试
CI_TIMEOUT=600  # 10分钟

# 正常构建
CI_TIMEOUT=1500  # 25分钟（公共CI限制）

# 长时间任务（远程CI配置）
CI_JOB_TIMEOUT=7200  # 2小时
```

### 3. 优化传输大小

```bash
# 排除不必要的文件
rsync --exclude='node_modules' \
      --exclude='*.log' \
      --exclude='.git' \
      --exclude='dist'

# 或打包时排除
tar --exclude='node_modules' -czf code.tar.gz .
```

### 4. 利用缓存

```bash
# rsync模式：利用workspace持久化
/var/ci-workspace/myapp/
  ├── node_modules/  # 保留，npm install增量更新
  ├── .gradle/       # 保留，Gradle缓存
  └── .turbo/        # 保留，Turborepo缓存
```

### 5. 并发控制

```bash
# 远程CI配置
CI_MAX_CONCURRENT=3  # 根据服务器资源调整

# 避免提交过多任务导致排队
```
