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

# 停止前端服务的函数（处理 npm -> node -> vite 的进程链）
stop_frontend() {
    local main_pid=$1
    local stopped=false

    if [ ! -z "$main_pid" ]; then
        echo "停止前端服务主进程 (PID: $main_pid)..."

        # 查找所有子进程（递归）
        local child_pids=$(pgrep -P $main_pid)

        # 先尝试优雅停止主进程
        if kill $main_pid 2>/dev/null; then
            sleep 0.5

            # 检查主进程是否退出
            if ! kill -0 $main_pid 2>/dev/null; then
                stopped=true
            else
                # 主进程未退出，强制杀死
                kill -9 $main_pid 2>/dev/null
                stopped=true
            fi
        fi

        # 清理所有子进程
        if [ ! -z "$child_pids" ]; then
            echo "清理前端子进程: $child_pids"
            for pid in $child_pids; do
                # 递归清理子进程的子进程
                local grandchild_pids=$(pgrep -P $pid)
                if [ ! -z "$grandchild_pids" ]; then
                    kill -9 $grandchild_pids 2>/dev/null
                fi
                kill -9 $pid 2>/dev/null
            done
        fi
    fi

    # 最终清理：通过端口查找并杀死所有占用 3000 端口的进程
    local port_pids=$(lsof -ti :3000 2>/dev/null)
    if [ ! -z "$port_pids" ]; then
        echo "清理占用端口 3000 的进程: $port_pids"
        kill -9 $port_pids 2>/dev/null
        stopped=true
    fi

    if [ "$stopped" = true ]; then
        echo -e "${GREEN}✅ 前端服务已停止${NC}"
    else
        echo -e "${YELLOW}⚠️  前端服务未运行${NC}"
    fi
}

# 停止前端服务
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    stop_frontend $FRONTEND_PID
    rm logs/frontend.pid
else
    echo -e "${YELLOW}⚠️  未找到 frontend.pid 文件${NC}"
    # 直接通过端口查找
    FRONTEND_PID=$(lsof -ti :3000 2>/dev/null | head -1)
    stop_frontend $FRONTEND_PID
fi

echo ""
echo "=========================================="
echo -e "${GREEN}✅ 所有服务已停止${NC}"
echo "=========================================="
echo ""
echo "📝 日志文件保留在 logs/ 目录"
echo "💡 重新启动: ./scripts/start.sh"
echo ""
