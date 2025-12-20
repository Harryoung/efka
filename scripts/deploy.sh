#!/bin/bash

# 知了 EFKA - 生产环境部署脚本
# 版本: 2.0.0
# 用法: ./scripts/deploy.sh [选项]
#
# 选项:
#   --skip-venv       跳过虚拟环境创建
#   --skip-frontend   跳过前端构建
#   --dev             开发模式部署（使用 start.sh）
#   --systemd         生成 systemd 服务文件
#   --help            显示帮助信息

set -e  # 遇到错误立即退出

# ==================== 配置部分 ====================

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Python 虚拟环境目录
VENV_DIR="$PROJECT_ROOT/venv"

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"

# 前端构建目录
FRONTEND_BUILD_DIR="$PROJECT_ROOT/frontend/dist"

# 默认选项
SKIP_VENV=false
SKIP_FRONTEND=false
DEV_MODE=false
SYSTEMD_MODE=false

# ==================== 帮助函数 ====================

show_help() {
    cat << EOF
知了 EFKA - 生产环境部署脚本

用法: $0 [选项]

选项:
  --skip-venv       跳过虚拟环境创建（如果已存在）
  --skip-frontend   跳过前端构建
  --dev             开发模式部署（使用 start.sh 启动）
  --systemd         生成 systemd 服务文件（用于生产环境）
  --help            显示此帮助信息

示例:
  $0                    # 完整部署
  $0 --skip-venv        # 跳过虚拟环境创建
  $0 --dev              # 开发模式部署
  $0 --systemd          # 生成 systemd 服务

EOF
    exit 0
}

# ==================== 工具函数 ====================

print_header() {
    echo ""
    echo "=========================================="
    echo -e "${CYAN}$1${NC}"
    echo "=========================================="
    echo ""
}

print_step() {
    echo -e "${BLUE}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 未安装"
        echo "请先安装 $1"
        exit 1
    else
        print_success "$1 已安装 ($(command -v "$1"))"
    fi
}

check_python_version() {
    local version=$(python3 --version | cut -d' ' -f2)
    local major=$(echo "$version" | cut -d'.' -f1)
    local minor=$(echo "$version" | cut -d'.' -f2)

    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 9 ]); then
        print_error "Python 版本过低: $version (需要 Python 3.9+)"
        exit 1
    fi

    print_success "Python 版本: $version"
}

check_node_version() {
    local version=$(node --version | sed 's/v//')
    local major=$(echo "$version" | cut -d'.' -f1)

    if [ "$major" -lt 16 ]; then
        print_error "Node.js 版本过低: $version (需要 Node.js 16+)"
        exit 1
    fi

    print_success "Node.js 版本: $version"
}

# ==================== 参数解析 ====================

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-venv)
            SKIP_VENV=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --systemd)
            SYSTEMD_MODE=true
            shift
            ;;
        --help)
            show_help
            ;;
        *)
            print_error "未知选项: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

# ==================== 主程序开始 ====================

print_header "🚀 知了 EFKA - 生产环境部署"

echo "部署配置："
echo "  项目目录: $PROJECT_ROOT"
echo "  虚拟环境: $VENV_DIR"
echo "  跳过虚拟环境: $SKIP_VENV"
echo "  跳过前端构建: $SKIP_FRONTEND"
echo "  开发模式: $DEV_MODE"
echo "  Systemd模式: $SYSTEMD_MODE"
echo ""

# ==================== 步骤 1: 环境检查 ====================

print_header "📋 步骤 1/6: 环境检查"

print_step "检查必需命令..."
check_command python3
check_command node
check_command npm
check_command pip3

print_step "检查版本要求..."
check_python_version
check_node_version

# 检查 .env 文件
print_step "检查环境配置文件..."
if [ ! -f ".env" ]; then
    print_warning ".env 文件不存在，从 .env.example 创建"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success ".env 文件已创建"
        print_warning "请编辑 .env 文件，填写必要的配置信息！"
        echo ""
        echo "关键配置项："
        echo "  - CLAUDE_API_KEY: Claude API 密钥"
        echo "  - WEWORK_CORP_ID: 企业微信企业ID"
        echo "  - WEWORK_CORP_SECRET: 企业微信应用Secret"
        echo "  - WEWORK_AGENT_ID: 企业微信应用AgentID"
        echo ""
        read -p "按回车键继续..." dummy
    else
        print_error ".env.example 文件不存在"
        exit 1
    fi
else
    print_success ".env 文件存在"
fi

# 创建必要的目录
print_step "创建必要目录..."
mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_ROOT/knowledge_base"

# 复制 skills 目录到知识库（Agent 安全边界要求）
if [ -d "$PROJECT_ROOT/skills" ]; then
    print_step "复制 skills 目录到知识库..."
    mkdir -p "$PROJECT_ROOT/knowledge_base/skills"
    cp -r "$PROJECT_ROOT/skills/"* "$PROJECT_ROOT/knowledge_base/skills/" 2>/dev/null || true
    print_success "skills 目录已复制到 knowledge_base/skills/"
fi

print_success "目录创建完成"

# ==================== 步骤 2: Python 虚拟环境 ====================

print_header "🐍 步骤 2/6: Python 虚拟环境配置"

if [ "$SKIP_VENV" = true ] && [ -d "$VENV_DIR" ]; then
    print_warning "跳过虚拟环境创建（--skip-venv）"
else
    if [ -d "$VENV_DIR" ]; then
        print_warning "虚拟环境已存在，将重新创建"
        rm -rf "$VENV_DIR"
    fi

    print_step "创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
    print_success "虚拟环境创建成功: $VENV_DIR"
fi

# 激活虚拟环境
print_step "激活虚拟环境..."
source "$VENV_DIR/bin/activate"
print_success "虚拟环境已激活"

# 升级 pip
print_step "升级 pip..."
pip install --upgrade pip setuptools wheel -q
print_success "pip 升级完成"

# ==================== 步骤 3: 后端依赖安装 ====================

print_header "📦 步骤 3/6: 安装后端依赖"

if [ -f "backend/requirements.txt" ]; then
    print_step "安装 Python 依赖包..."
    pip install -r backend/requirements.txt
    print_success "后端依赖安装完成"

    # 验证关键依赖
    print_step "验证关键依赖..."

    if ! pip show fastapi > /dev/null 2>&1; then
        print_error "FastAPI 安装失败"
        exit 1
    fi
    print_success "FastAPI 已安装"

    if ! pip show claude-agent-sdk > /dev/null 2>&1; then
        print_error "Claude Agent SDK 安装失败"
        exit 1
    fi
    print_success "Claude Agent SDK 已安装"

    if ! command -v markitdown-mcp &> /dev/null; then
        print_error "markitdown-mcp 安装失败或不在PATH中"
        exit 1
    fi
    print_success "markitdown-mcp 已安装"

    # 安装 wework-mcp（本地MCP服务器）
    print_step "安装 wework-mcp MCP 服务器..."
    if [ -d "$PROJECT_ROOT/wework-mcp" ]; then
        pip install "$PROJECT_ROOT/wework-mcp"
        if ! command -v wework-mcp &> /dev/null; then
            print_error "wework-mcp 安装失败或不在PATH中"
            exit 1
        fi
        print_success "wework-mcp 已安装"
    else
        print_warning "wework-mcp 目录不存在，跳过安装"
        print_warning "注意：企微消息推送功能将不可用"
    fi

else
    print_error "backend/requirements.txt 不存在"
    exit 1
fi

# ==================== 步骤 4: 前端构建 ====================

print_header "🎨 步骤 4/6: 前端构建"

if [ "$SKIP_FRONTEND" = true ]; then
    print_warning "跳过前端构建（--skip-frontend）"
else
    cd "$PROJECT_ROOT/frontend"

    # 安装前端依赖
    print_step "安装前端依赖..."
    if [ ! -d "node_modules" ]; then
        npm install
    else
        print_warning "node_modules 已存在，跳过安装（使用 'rm -rf node_modules' 强制重装）"
    fi
    print_success "前端依赖安装完成"

    # 构建生产版本
    print_step "构建生产版本..."
    npm run build
    print_success "前端构建完成: $FRONTEND_BUILD_DIR"

    cd "$PROJECT_ROOT"
fi

# ==================== 步骤 5: Redis 配置 ====================

print_header "🗄️ 步骤 5/7: Redis 配置检查"

print_step "检查 Redis 配置..."

# 从 .env 读取 Redis 密码
REDIS_PASSWORD=$(grep "^REDIS_PASSWORD=" .env 2>/dev/null | cut -d'=' -f2- | tr -d '"' | tr -d "'")
REDIS_PORT=$(grep "^REDIS_PORT=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
REDIS_PORT=${REDIS_PORT:-6379}

# 检查 Redis 是否运行
print_step "检查 Redis 服务状态..."

if command -v docker &> /dev/null; then
    # 检查 Docker Redis 容器
    if docker ps | grep -q "redis"; then
        REDIS_CONTAINER=$(docker ps --filter "name=redis" --format "{{.Names}}" | head -1)
        print_success "发现 Redis Docker 容器: $REDIS_CONTAINER"

        # 验证 Redis 连接
        if [ -n "$REDIS_PASSWORD" ]; then
            if docker exec "$REDIS_CONTAINER" redis-cli --pass "$REDIS_PASSWORD" ping > /dev/null 2>&1; then
                print_success "Redis 连接测试成功（有密码）"
            else
                print_warning "Redis 密码可能不正确"
            fi
        else
            if docker exec "$REDIS_CONTAINER" redis-cli ping > /dev/null 2>&1; then
                print_success "Redis 连接测试成功（无密码）"
            fi
        fi

        # 检查 Redis 版本
        REDIS_VERSION=$(docker exec "$REDIS_CONTAINER" redis-cli --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$REDIS_VERSION" ]; then
            print_success "Redis 版本: $REDIS_VERSION"

            # 检查是否是推荐版本（Redis 7.x）
            REDIS_MAJOR=$(echo "$REDIS_VERSION" | cut -d'.' -f1)
            if [ "$REDIS_MAJOR" != "7" ]; then
                print_warning "检测到 Redis $REDIS_VERSION，推荐使用 Redis 7.x"
                echo ""
                echo "如需更换为推荐版本，运行以下命令："
                echo "  docker stop $REDIS_CONTAINER && docker rm $REDIS_CONTAINER"
                echo "  docker run --name redis -d -p 127.0.0.1:6379:6379 redis:7-alpine redis-server --requirepass \"$REDIS_PASSWORD\""
                echo ""
            fi
        fi
    else
        print_warning "未检测到运行中的 Redis 容器"
        echo ""
        echo "推荐使用 Docker 部署 Redis："
        echo ""
        if [ -n "$REDIS_PASSWORD" ]; then
            echo "  docker run --name redis -d -p 127.0.0.1:6379:6379 \\"
            echo "    redis:7-alpine redis-server --requirepass \"$REDIS_PASSWORD\""
        else
            print_warning ".env 中未配置 REDIS_PASSWORD，建议配置密码"
            echo "  docker run --name redis -d -p 127.0.0.1:6379:6379 redis:7-alpine"
        fi
        echo ""
        echo "或者使用系统包管理器安装 Redis："
        echo "  macOS: brew install redis && brew services start redis"
        echo "  Ubuntu: sudo apt install redis-server && sudo systemctl start redis"
        echo ""
        read -p "是否继续部署（不安装 Redis）？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "部署已取消"
            exit 1
        fi
    fi
elif command -v redis-cli &> /dev/null; then
    # 检查本地 Redis 服务
    if redis-cli ping > /dev/null 2>&1; then
        print_success "发现本地 Redis 服务"
        REDIS_VERSION=$(redis-cli --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if [ -n "$REDIS_VERSION" ]; then
            print_success "Redis 版本: $REDIS_VERSION"
        fi
    else
        print_warning "本地 Redis 服务未响应"
    fi
else
    print_warning "未检测到 Redis（Docker 或本地安装）"
    echo ""
    echo "Redis 用于会话持久化，建议安装。"
    echo "如果不安装 Redis，系统将使用内存存储（重启后会话丢失）。"
    echo ""
    read -p "是否继续部署（不安装 Redis）？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "部署已取消"
        exit 1
    fi
fi

# ==================== 步骤 6: 环境验证 ====================

print_header "✅ 步骤 6/7: 环境验证"

print_step "验证 Python 模块导入..."

# 加载环境变量用于测试
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 测试关键模块导入
python3 << 'PYTHON_TEST'
import sys
import os

try:
    # 测试 FastAPI
    import fastapi
    print("✅ FastAPI 导入成功")

    # 测试 Claude SDK
    from claude_agent_sdk import AgentDefinition
    print("✅ Claude Agent SDK 导入成功")

    # 测试后端服务（需要环境变量）
    if os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        # 只做基本导入测试，不初始化 SDK 客户端
        from backend.services.kb_service_factory import get_admin_service, get_user_service
        print("✅ KB Service Factory 导入成功")

        from backend.api.query import router as query_router
        print("✅ Query API 导入成功")
    else:
        print("⚠️  未配置 API KEY，跳过服务导入测试")

    print("\n所有关键模块导入测试通过！")

except Exception as e:
    print(f"❌ 模块导入失败: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_TEST

if [ $? -eq 0 ]; then
    print_success "Python 模块导入验证通过"
else
    print_error "环境验证失败"
    exit 1
fi

# 测试 Redis 连接（如果配置了）
if [ -n "$REDIS_PASSWORD" ] || command -v docker &> /dev/null; then
    print_step "测试 Redis 连接..."

    python3 << 'REDIS_TEST'
import sys
import os

# 尝试连接 Redis
try:
    import redis

    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_password = os.getenv("REDIS_PASSWORD")

    if redis_password:
        r = redis.Redis(
            host='127.0.0.1',
            port=6379,
            db=0,
            password=redis_password,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
    else:
        r = redis.Redis(
            host='127.0.0.1',
            port=6379,
            db=0,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )

    # 测试连接
    result = r.ping()
    if result:
        print("✅ Redis 连接测试成功")

        # 测试基本操作
        r.set('deploy_test_key', 'deploy_test_value')
        value = r.get('deploy_test_key')
        if value == 'deploy_test_value':
            print("✅ Redis 读写测试成功")
        r.delete('deploy_test_key')

        r.close()
    else:
        print("⚠️  Redis PING 失败", file=sys.stderr)

except redis.exceptions.ConnectionError as e:
    print(f"⚠️  Redis 连接失败: {e}", file=sys.stderr)
    print("提示：应用将自动降级到内存存储（会话不持久化）", file=sys.stderr)
except Exception as e:
    print(f"⚠️  Redis 测试异常: {e}", file=sys.stderr)
REDIS_TEST

    # Redis 连接失败不阻止部署
    if [ $? -ne 0 ]; then
        print_warning "Redis 连接测试未通过，但不影响部署"
        print_warning "应用将使用内存存储（重启后会话丢失）"
    fi
else
    print_warning "跳过 Redis 连接测试（未配置密码或 Docker 不可用）"
fi

# ==================== 步骤 7: 生成启动脚本/服务 ====================

print_header "🔧 步骤 7/7: 生成启动配置"

if [ "$SYSTEMD_MODE" = true ]; then
    # 生成 systemd 服务文件
    print_step "生成 systemd 服务文件..."

    # 读取 WeWork 端口配置
    source .env
    WEWORK_PORT=${WEWORK_PORT:-8081}

    # FastAPI 主服务
    cat > "$PROJECT_ROOT/efka-admin.service" << EOF
[Unit]
Description=EFKA - Admin Service (FastAPI)
After=network.target
# 如果使用 systemd 管理的 Redis，取消下面的注释
# After=network.target redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
EnvironmentFile=$PROJECT_ROOT/.env
ExecStart=$VENV_DIR/bin/python -m backend.main
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/backend.log
StandardError=append:$LOG_DIR/backend.log

[Install]
WantedBy=multi-user.target
EOF
    print_success "Admin 服务文件: efka-admin.service"

    # Flask 企微回调服务
    cat > "$PROJECT_ROOT/efka-wework.service" << EOF
[Unit]
Description=EFKA - WeWork Callback Service (Flask)
After=network.target efka-admin.service
# 如果使用 systemd 管理的 Redis，取消下面的注释
# After=network.target redis.service efka-admin.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_ROOT
EnvironmentFile=$PROJECT_ROOT/.env
ExecStart=$VENV_DIR/bin/python -m backend.wework_server
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/wework.log
StandardError=append:$LOG_DIR/wework.log

[Install]
WantedBy=multi-user.target
EOF
    print_success "WeWork 服务文件: efka-wework.service"

    echo ""
    echo "Systemd 服务文件已生成！"
    echo ""
    echo "部署步骤："
    echo "  1. 复制服务文件到 systemd 目录:"
    echo "     sudo cp efka-*.service /etc/systemd/system/"
    echo ""
    echo "  2. 重载 systemd:"
    echo "     sudo systemctl daemon-reload"
    echo ""
    echo "  3. 启用并启动服务:"
    echo "     sudo systemctl enable efka-admin.service"
    echo "     sudo systemctl enable efka-wework.service"
    echo "     sudo systemctl start efka-admin.service"
    echo "     sudo systemctl start efka-wework.service"
    echo ""
    echo "  4. 查看服务状态:"
    echo "     sudo systemctl status efka-admin.service"
    echo "     sudo systemctl status efka-wework.service"
    echo ""
    echo "  5. 查看日志:"
    echo "     sudo journalctl -u efka-admin.service -f"
    echo "     sudo journalctl -u efka-wework.service -f"
    echo ""

else
    # 生成生产环境启动脚本（使用 venv）
    print_step "生成生产环境启动脚本..."

    cat > "$PROJECT_ROOT/scripts/start_production.sh" << 'EOF'
#!/bin/bash

# 知了 EFKA - 生产环境启动脚本（使用虚拟环境）
# 用法: ./scripts/start_production.sh

set -e

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo "🚀 知了 EFKA - 生产环境启动"
echo "=========================================="
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ 虚拟环境不存在${NC}"
    echo "请先运行部署脚本: ./scripts/deploy.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate
echo -e "${GREEN}✅ 虚拟环境已激活${NC}"

# 加载环境变量
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ 环境变量已加载${NC}"
fi

# 读取 WeWork 端口配置
WEWORK_PORT=${WEWORK_PORT:-8081}

# 创建日志目录
mkdir -p logs

echo ""
echo "启动服务..."
echo ""

# 启动 FastAPI 主服务（管理端API，端口8000）
echo "🚀 启动 FastAPI 主服务（管理端API）..."
python -m backend.main > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > logs/backend.pid
echo "   PID: $BACKEND_PID"
echo "   运行在: http://localhost:8000"
echo "   健康检查: http://localhost:8000/health"

# 等待主服务启动
sleep 3

# 健康检查
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ FastAPI 主服务启动成功${NC}"
else
    echo -e "${RED}❌ FastAPI 主服务启动失败${NC}"
    echo "请查看日志: cat logs/backend.log"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""

# 启动 Flask 企微回调服务（员工端API）
echo "🚀 启动 Flask 企微回调服务（员工端API）..."
python -m backend.wework_server > logs/wework.log 2>&1 &
WEWORK_PID=$!
echo $WEWORK_PID > logs/wework.pid
echo "   PID: $WEWORK_PID"
echo "   运行在: http://localhost:$WEWORK_PORT"
echo "   回调地址: http://localhost:$WEWORK_PORT/api/wework/callback"

# 等待Flask服务启动
sleep 3

# 检查端口是否监听
if lsof -i:$WEWORK_PORT > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Flask 企微回调服务启动成功${NC}"
else
    echo -e "${YELLOW}⚠️  Flask 企微回调服务可能未启动${NC}"
    echo "请查看日志: cat logs/wework.log"
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 生产环境启动完成${NC}"
echo "=========================================="
echo ""
echo "📱 访问地址:"
echo "   Admin API: http://localhost:8000"
echo "   WeWork API: http://localhost:$WEWORK_PORT"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "📊 进程信息:"
echo "   FastAPI PID: $BACKEND_PID"
echo "   Flask PID: $WEWORK_PID"
echo ""
echo "📝 日志文件:"
echo "   Admin: logs/backend.log"
echo "   WeWork: logs/wework.log"
echo ""
echo "🛑 停止服务: ./scripts/stop.sh"
echo ""
EOF

    chmod +x "$PROJECT_ROOT/scripts/start_production.sh"
    print_success "生产启动脚本: scripts/start_production.sh"
fi

# ==================== 部署完成 ====================

print_header "🎉 部署完成！"

echo "部署摘要："
echo "  ✅ Python 虚拟环境: $VENV_DIR"
echo "  ✅ 后端依赖已安装"
if [ "$SKIP_FRONTEND" = false ]; then
    echo "  ✅ 前端已构建: $FRONTEND_BUILD_DIR"
fi
echo "  ✅ 环境验证通过"
echo ""

if [ "$DEV_MODE" = true ]; then
    echo "开发模式部署完成！"
    echo ""
    echo "启动开发服务器："
    echo "  ./scripts/start.sh"
    echo ""
elif [ "$SYSTEMD_MODE" = true ]; then
    echo "Systemd 服务文件已生成，请参考上面的部署步骤"
    echo ""
else
    echo "生产环境部署完成！"
    echo ""
    echo "快速启动："
    echo "  ./scripts/start_production.sh"
    echo ""
    echo "或使用 systemd 部署："
    echo "  ./scripts/deploy.sh --systemd"
    echo ""
fi

echo "重要提示："
echo "  1. 确保 .env 文件配置正确（特别是 API KEY 和 Redis 密码）"
echo "  2. Redis 用于会话持久化，推荐使用 Redis 7.x Alpine 版本"
echo "  3. 生产环境建议使用 Nginx 反向代理"
echo "  4. 定期备份 knowledge_base 目录"
echo ""

# 退出虚拟环境（可选，因为脚本结束后会自动退出）
# deactivate

print_success "部署脚本执行完毕！"
