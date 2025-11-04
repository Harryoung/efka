#!/bin/bash

# 智能资料库管理员 - 停止脚本
# 用法: ./scripts/stop.sh

echo "=========================================="
echo "🛑 智能资料库管理员 - 停止脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 读取进程 ID
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    echo "停止后端服务 (PID: $BACKEND_PID)..."

    if kill $BACKEND_PID 2>/dev/null; then
        echo -e "${GREEN}✅ 后端服务已停止${NC}"
    else
        echo -e "${YELLOW}⚠️  后端进程不存在或已停止${NC}"
    fi

    rm logs/backend.pid
else
    echo -e "${YELLOW}⚠️  未找到后端 PID 文件${NC}"

    # 尝试通过端口查找并停止
    BACKEND_PID=$(lsof -ti :8000)
    if [ ! -z "$BACKEND_PID" ]; then
        echo "发现后端进程 (PID: $BACKEND_PID)，正在停止..."
        kill $BACKEND_PID
        echo -e "${GREEN}✅ 后端服务已停止${NC}"
    fi
fi

if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    echo "停止前端服务 (PID: $FRONTEND_PID)..."

    if kill $FRONTEND_PID 2>/dev/null; then
        echo -e "${GREEN}✅ 前端服务已停止${NC}"
    else
        echo -e "${YELLOW}⚠️  前端进程不存在或已停止${NC}"
    fi

    rm logs/frontend.pid
else
    echo -e "${YELLOW}⚠️  未找到前端 PID 文件${NC}"

    # 尝试通过端口查找并停止
    FRONTEND_PID=$(lsof -ti :3000)
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "发现前端进程 (PID: $FRONTEND_PID)，正在停止..."
        kill $FRONTEND_PID
        echo -e "${GREEN}✅ 前端服务已停止${NC}"
    fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 所有服务已停止${NC}"
echo "=========================================="
echo ""
echo "📝 日志文件保留在 logs/ 目录"
echo "💡 重新启动: ./scripts/start.sh"
echo ""
