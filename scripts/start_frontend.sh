#!/bin/bash

# 智能资料库管理员 - 前端服务启动脚本
# 用法: ./scripts/start_frontend.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🎨 智能资料库管理员 - 前端服务启动"
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
        local pid=$(lsof -Pi :$port -sTCP:LISTEN -t)
        echo "占用进程 PID: $pid"
        echo "请使用以下命令停止占用进程:"
        echo "  kill -9 $pid"
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
echo "📋 步骤 1/3: 环境检查"
echo "----------------------------------------"

check_command node
check_command npm

# 检查 Node 版本
NODE_VERSION=$(node --version)
echo "Node.js 版本: $NODE_VERSION"

# 检查 npm 版本
NPM_VERSION=$(npm --version)
echo "npm 版本: $NPM_VERSION"

echo ""

# 步骤 2: 检查端口
echo "🔍 步骤 2/3: 检查端口"
echo "----------------------------------------"

if ! check_port 3000; then
    echo "提示: 如果是前端服务占用，可以先运行 './scripts/stop.sh' 停止所有服务"
    exit 1
fi

echo ""

# 步骤 3: 检查前端目录
echo "📁 检查前端目录"
echo "----------------------------------------"

if [ ! -d "frontend" ]; then
    echo -e "${RED}❌ frontend 目录不存在${NC}"
    exit 1
else
    echo -e "${GREEN}✅ frontend 目录存在${NC}"
fi

cd frontend

echo ""

# 步骤 4: 安装依赖
echo "📦 步骤 3/3: 检查并安装依赖"
echo "----------------------------------------"

if [ ! -d "node_modules" ]; then
    echo "⚠️  前端依赖未安装，正在安装..."
    npm install
    echo -e "${GREEN}✅ 依赖安装完成${NC}"
else
    echo -e "${GREEN}✅ 依赖已安装${NC}"
    echo "如需重新安装，请先删除 node_modules 目录"
fi

echo ""

# 步骤 5: 启动前端服务
echo "🚀 启动前端服务"
echo "=========================================="

# 创建日志目录
mkdir -p ../logs

# 检查是否已有前端进程在运行
if [ -f "../logs/frontend.pid" ]; then
    OLD_PID=$(cat ../logs/frontend.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  检测到前端服务已在运行 (PID: $OLD_PID)${NC}"
        echo "正在停止旧进程..."
        kill $OLD_PID 2>/dev/null || true
        sleep 2
    fi
fi

echo "启动开发服务器..."
echo "前端将运行在: http://localhost:3000"
echo ""

# 在后台启动前端
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!

# 保存 PID
echo $FRONTEND_PID > ../logs/frontend.pid

echo "前端进程 PID: $FRONTEND_PID"
echo "日志文件: logs/frontend.log"
echo ""

# 等待前端启动
echo "等待服务启动（最多 10 秒）..."
RETRY_COUNT=0
MAX_RETRIES=10

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ 前端服务启动成功！${NC}"
        break
    fi
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
done

echo ""

# 检查启动结果
if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ 前端服务启动失败或超时${NC}"
    echo ""
    echo "请检查以下内容:"
    echo "  1. 查看日志: tail -f logs/frontend.log"
    echo "  2. 检查端口: lsof -i :3000"
    echo "  3. 检查进程: ps -p $FRONTEND_PID"
    echo ""
    echo "尝试手动启动:"
    echo "  cd frontend && npm run dev"
    exit 1
fi

cd ..

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN}🎉 前端服务启动完成！${NC}"
echo "=========================================="
echo ""
echo "📱 访问地址:"
echo "   前端界面: http://localhost:3000"
echo ""
echo "📊 进程信息:"
echo "   进程 PID: $FRONTEND_PID"
echo "   PID 文件: logs/frontend.pid"
echo ""
echo "📝 日志文件:"
echo "   实时日志: tail -f logs/frontend.log"
echo "   完整日志: cat logs/frontend.log"
echo ""
echo "🛑 停止服务:"
echo "   方法 1: kill $FRONTEND_PID"
echo "   方法 2: ./scripts/stop.sh  (停止所有服务)"
echo ""
echo "💡 提示:"
echo "   - 前端使用 Vite 开发服务器，支持热更新"
echo "   - 修改代码后会自动刷新浏览器"
echo "   - 如需生产构建，使用: cd frontend && npm run build"
echo ""
echo "=========================================="

# 自动打开浏览器（可选）
if command -v xdg-open &> /dev/null; then
    echo "3 秒后自动打开浏览器..."
    sleep 3
    xdg-open http://localhost:3000 &
elif command -v open &> /dev/null; then
    echo "3 秒后自动打开浏览器..."
    sleep 3
    open http://localhost:3000 &
fi
