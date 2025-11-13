#!/bin/bash

# 智能资料库管理员 - 生产环境启动脚本（使用虚拟环境）
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
echo "🚀 智能资料库管理员 - 生产环境启动"
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
