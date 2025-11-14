# Remote CI Makefile - 测试和开发辅助工具

.PHONY: help test-e2e test-start test-stop test-logs test-clean test-all

# 默认目标
help:
	@echo "Remote CI 测试工具"
	@echo ""
	@echo "可用命令:"
	@echo "  make test-all     - 运行完整的端到端测试（推荐）"
	@echo "  make test-start   - 启动测试环境"
	@echo "  make test-e2e     - 运行端到端测试"
	@echo "  make test-logs    - 查看容器日志"
	@echo "  make test-stop    - 停止测试环境"
	@echo "  make test-clean   - 清理测试环境和数据"
	@echo "  make test-shell   - 进入远程CI容器shell"
	@echo ""

# 运行完整测试
test-all: test-clean
	@echo "=========================================="
	@echo "运行完整的端到端测试套件"
	@echo "=========================================="
	@chmod +x test-e2e.sh
	@./test-e2e.sh

# 启动测试环境
test-start:
	@echo "启动测试环境..."
	@docker-compose -f docker-compose.test.yml up -d --build
	@echo "等待服务就绪..."
	@sleep 5
	@curl -s http://localhost:15000/api/health | jq . || echo "服务未就绪"

# 运行端到端测试（不重启环境）
test-e2e:
	@echo "运行端到端测试..."
	@chmod +x test-e2e.sh
	@./test-e2e.sh

# 查看日志
test-logs:
	@docker-compose -f docker-compose.test.yml logs -f

# 停止测试环境
test-stop:
	@echo "停止测试环境..."
	@docker-compose -f docker-compose.test.yml down

# 清理测试环境和数据
test-clean:
	@echo "清理测试环境..."
	@docker-compose -f docker-compose.test.yml down -v 2>/dev/null || true
	@rm -rf ../test-workspace ../test-logs
	@echo "清理完成"

# 进入容器shell
test-shell:
	@docker exec -it remoteCI-test-server bash

# 检查环境
test-check:
	@echo "检查Docker环境..."
	@docker --version
	@docker-compose --version
	@echo ""
	@echo "检查Python依赖..."
	@python3 --version
	@pip3 list | grep requests || echo "⚠️  需要安装: pip3 install requests"
	@which jq > /dev/null || echo "⚠️  需要安装jq: brew install jq (macOS) 或 apt install jq (Linux)"

# 快速验证
test-quick: test-start
	@sleep 3
	@echo "快速验证远程CI服务..."
	@curl -s http://localhost:15000/api/health | jq .
	@echo ""
	@echo "服务已启动，访问: http://localhost:15000"
	@echo "停止服务: make test-stop"
