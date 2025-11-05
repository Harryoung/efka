#!/bin/bash

# 智能资料库管理员 - 快速启动脚本
# 用法: ./scripts/start.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🚀 智能资料库管理员 - 启动脚本"
echo "=========================================="
echo ""

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}⚠️  端口 $port 已被占用${NC}"
        echo "请关闭占用端口的进程，或修改配置使用其他端口"
        return 1
    else
        echo -e "${GREEN}✅ 端口 $port 可用${NC}"
        return 0
    fi
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 未安装${NC}"
        echo "请先安装 $1"
        exit 1
    else
        echo -e "${GREEN}✅ $1 已安装${NC}"
    fi
}

# 步骤 1: 环境检查
echo "📋 步骤 1/4: 环境检查"
echo "----------------------------------------"

check_command python3
check_command node
check_command npm

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "Python 版本: $PYTHON_VERSION"

# 检查 Node 版本
NODE_VERSION=$(node --version)
echo "Node.js 版本: $NODE_VERSION"

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env 文件不存在${NC}"
    echo "请复制 .env.example 并配置环境变量"
    exit 1
else
    echo -e "${GREEN}✅ .env 文件存在${NC}"
fi

echo ""

# 步骤 2: 检查端口
echo "🔍 步骤 2/4: 检查端口"
echo "----------------------------------------"

if ! check_port 8000; then
    echo "提示: 可以使用 'lsof -i :8000' 查看占用进程"
    exit 1
fi

if ! check_port 3000; then
    echo "提示: 可以使用 'lsof -i :3000' 查看占用进程"
    exit 1
fi

echo ""

# 步骤 3: 启动后端
echo "🔧 步骤 3/4: 启动后端服务"
echo "----------------------------------------"

# 检查后端依赖
if [ ! -f "backend/.venv_installed" ]; then
    echo "⚠️  后端依赖未安装，正在安装..."
    pip3 install -r backend/requirements.txt
    touch backend/.venv_installed
fi

# ⚠️ 关键：从 .env 文件加载并导出环境变量
# 这样可以确保 Python 子进程（包括子 Agent）都能访问认证信息
echo "加载环境变量..."
if [ -f ".env" ]; then
    # shellcheck disable=SC1091
    set -a
    source .env
    set +a

    # 显示加载的环境变量（隐藏敏感信息）
    if [ ! -z "$ANTHROPIC_AUTH_TOKEN" ]; then
        TOKEN_SUFFIX="${ANTHROPIC_AUTH_TOKEN: -4}"
        echo -e "${GREEN}✅ ANTHROPIC_AUTH_TOKEN 已加载 (...$TOKEN_SUFFIX)${NC}"
    fi

    if [ ! -z "$ANTHROPIC_BASE_URL" ]; then
        echo -e "${GREEN}✅ ANTHROPIC_BASE_URL 已加载 ($ANTHROPIC_BASE_URL)${NC}"
    fi

    if [ ! -z "$CLAUDE_API_KEY" ]; then
        KEY_SUFFIX="${CLAUDE_API_KEY: -4}"
        echo -e "${GREEN}✅ CLAUDE_API_KEY 已加载 (...$KEY_SUFFIX)${NC}"
    fi

    if [ ! -z "$REDIS_URL" ]; then
        echo -e "${GREEN}✅ REDIS_URL 已加载 ($REDIS_URL)${NC}"
    fi

    if [ ! -z "$REDIS_USERNAME" ]; then
        echo -e "${GREEN}✅ REDIS_USERNAME 已加载${NC}"
    fi

    if [ ! -z "$REDIS_PASSWORD" ]; then
        echo -e "${GREEN}✅ REDIS_PASSWORD 已加载（已隐藏）${NC}"
    fi
fi

echo "启动后端服务..."
echo "后端运行在: http://localhost:8000"
echo "健康检查: http://localhost:8000/health"
echo ""

mkdir -p logs

# 在后台启动后端（从项目根目录运行）
# 环境变量已通过 export 传递给子进程
python3 -m backend.main > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "后端进程 PID: $BACKEND_PID"

# 等待后端启动
echo "等待后端启动..."
sleep 3

# 检查后端是否成功启动
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 后端启动成功${NC}"
else
    echo -e "${RED}❌ 后端启动失败${NC}"
    echo "请查看日志: cat logs/backend.log"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""

# 步骤 4: 启动前端
echo "🎨 步骤 4/4: 启动前端服务"
echo "----------------------------------------"

cd frontend

# 检查前端依赖
if [ ! -d "node_modules" ]; then
    echo "⚠️  前端依赖未安装，正在安装..."
    npm install
fi

echo "启动前端服务..."
echo "前端运行在: http://localhost:3000"
echo ""

# 在后台启动前端
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "前端进程 PID: $FRONTEND_PID"

# 等待前端启动
echo "等待前端启动..."
sleep 5

# 检查前端是否成功启动
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 前端启动成功${NC}"
else
    echo -e "${RED}❌ 前端启动失败${NC}"
    echo "请查看日志: cat logs/frontend.log"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 1
fi

cd ..
echo ""

# 保存进程 ID
mkdir -p logs
echo $BACKEND_PID > logs/backend.pid
echo $FRONTEND_PID > logs/frontend.pid

# 完成
echo "=========================================="
echo -e "${GREEN}🎉 启动完成！${NC}"
echo "=========================================="
echo ""
echo "📱 访问地址:"
echo "   前端界面: http://localhost:3000"
echo "   后端 API: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "📊 进程信息:"
echo "   后端 PID: $BACKEND_PID"
echo "   前端 PID: $FRONTEND_PID"
echo ""
echo "📝 日志文件:"
echo "   后端日志: logs/backend.log"
echo "   前端日志: logs/frontend.log"
echo ""
echo "🛑 停止服务:"
echo "   ./scripts/stop.sh"
echo ""
echo "💡 提示:"
echo "   - 打开浏览器访问 http://localhost:3000"
echo "   - 查看启动指南: cat 启动指南.md"
echo "   - 查看实时日志: tail -f logs/backend.log"
echo ""
echo "=========================================="

# 自动打开浏览器（可选）
if command -v open &> /dev/null; then
    echo "3 秒后自动打开浏览器..."
    sleep 3
    open http://localhost:3000
fi
