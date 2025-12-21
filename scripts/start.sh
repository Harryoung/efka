#!/bin/bash

# EFKA v3.0 - Multi-channel Startup Script
# Supports: standalone mode and IM integration (WeWork, Feishu, DingTalk, Slack)
# Usage: ./scripts/start.sh [--mode <mode>]
# Modes: standalone (default), wework, feishu, dingtalk, slack

set -e  # Exit on error

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 解析命令行参数
MODE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode|-m)
            MODE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./scripts/start.sh [--mode <mode>]"
            echo ""
            echo "Modes:"
            echo "  standalone  - Pure Web mode, no IM integration (default)"
            echo "  wework      - WeChat Work integration"
            echo "  feishu      - Feishu/Lark integration"
            echo "  dingtalk    - DingTalk integration"
            echo "  slack       - Slack integration"
            echo ""
            echo "Examples:"
            echo "  ./scripts/start.sh                    # Standalone mode"
            echo "  ./scripts/start.sh --mode standalone  # Standalone mode"
            echo "  ./scripts/start.sh --mode wework      # WeChat Work mode"
            echo "  ./scripts/start.sh -m wework          # Short form"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "🚀 EFKA v3.0 - Embed-Free Knowledge Agent"
echo "=========================================="
echo ""

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}⚠️  端口 $port 已被占用${NC}"
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
        return 1
    else
        echo -e "${GREEN}✅ $1 已安装${NC}"
        return 0
    fi
}

# 步骤 1: 环境检查
echo "📋 步骤 1/5: 环境检查"
echo "----------------------------------------"

check_command python3 || exit 1
check_command node || exit 1
check_command npm || exit 1

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env 文件不存在${NC}"
    echo "请复制 .env.example 并配置环境变量"
    exit 1
else
    echo -e "${GREEN}✅ .env 文件存在${NC}"
fi

# 检查并激活虚拟环境
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ 检测到虚拟环境，正在激活...${NC}"
    source venv/bin/activate
    PYTHON_CMD="python"
else
    echo -e "${YELLOW}⚠️  未检测到虚拟环境，使用全局 Python${NC}"
    PYTHON_CMD="python3"
fi

# 加载环境变量
echo ""
echo "加载环境变量..."
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ 环境变量已加载${NC}"
fi

echo ""

# 步骤 2: 确定运行模式
echo "🔍 步骤 2/5: 确定运行模式"
echo "----------------------------------------"

# 确定运行模式（CLI > ENV > default）
if [ -n "$MODE" ]; then
    RUN_MODE="$MODE"
elif [ -z "$RUN_MODE" ]; then
    RUN_MODE="standalone"
fi
export RUN_MODE

# 验证模式并设置 IM 标志
case $RUN_MODE in
    standalone)
        IM_ENABLED=false
        echo -e "${GREEN}✅ 运行模式: standalone (纯 Web)${NC}"
        ;;
    wework|feishu|dingtalk|slack)
        IM_ENABLED=true
        IM_CHANNEL=$RUN_MODE
        ENABLED_CHANNELS=$RUN_MODE
        echo -e "${GREEN}✅ 运行模式: $RUN_MODE (IM 集成)${NC}"
        ;;
    *)
        echo -e "${RED}❌ 无效模式: $RUN_MODE${NC}"
        echo "有效模式: standalone, wework, feishu, dingtalk, slack"
        exit 1
        ;;
esac

# 检测User Web UI配置
USER_UI_ENABLED=${USER_UI_ENABLED:-true}
USER_UI_PORT=${USER_UI_PORT:-3001}

if [ "$USER_UI_ENABLED" = "true" ]; then
    echo -e "${GREEN}✅ User Web UI 已启用 (端口: $USER_UI_PORT)${NC}"
else
    echo -e "${YELLOW}⏭️  User Web UI 未启用${NC}"
fi

echo ""

# 步骤 3: 检查端口
echo "🔌 步骤 3/5: 检查端口"
echo "----------------------------------------"

# 检查主服务端口
check_port 8000 || exit 1

# 检查Admin UI端口
check_port 3000 || exit 1

# 检查User UI端口(如果启用)
if [ "$USER_UI_ENABLED" = "true" ]; then
    check_port $USER_UI_PORT || exit 1
fi

# 检查各渠道端口
for channel in $ENABLED_CHANNELS; do
    channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
    port_var="${channel_upper}_PORT"
    port=${!port_var}

    if [ -z "$port" ]; then
        # 使用默认端口
        case $channel in
            wework) port=8081 ;;
            feishu) port=8082 ;;
            dingtalk) port=8083 ;;
            slack) port=8084 ;;
            *) port=8080 ;;
        esac
    fi

    check_port $port || exit 1
done

echo ""

# 步骤 4: 启动后端服务
echo "🔧 步骤 4/5: 启动后端服务"
echo "----------------------------------------"

# 检查后端依赖
# 使用 .venv_installed 文件标记依赖安装状态
# 注意：如果 requirements.txt 更新了，需要手动删除此文件重新安装
if [ ! -f "backend/.venv_installed" ]; then
    echo "⚠️  后端依赖未安装，正在安装..."
    pip3 install -r backend/requirements.txt
    touch backend/.venv_installed
    echo "✅  后端依赖安装完成"
else
    echo "✅  后端依赖已安装（如需更新依赖，请删除 backend/.venv_installed 文件）"
fi

mkdir -p logs

# 创建 knowledge_base 目录并复制 skills 文件（Agent 安全边界要求）
echo "📁 创建知识库目录结构..."
mkdir -p "$PROJECT_ROOT/knowledge_base"
if [ -d "$PROJECT_ROOT/skills" ]; then
    mkdir -p "$PROJECT_ROOT/knowledge_base/skills"
    echo "📋 复制 skills 文件到知识库..."
    cp -r "$PROJECT_ROOT/skills/"* "$PROJECT_ROOT/knowledge_base/skills/" 2>/dev/null || true
    echo -e "${GREEN}✅ skills 目录已复制到 knowledge_base/skills/${NC}"
fi

echo ""
echo "=========================================="
echo "启动后端服务"
echo "=========================================="

# 启动 FastAPI 主服务（Admin API，端口8000）
echo "🚀 启动 FastAPI 主服务（Admin API + User API）..."
echo "   运行模式: $RUN_MODE"
$PYTHON_CMD -m backend.main --mode $RUN_MODE > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > logs/backend.pid
echo -e "${GREEN}   PID: $BACKEND_PID${NC}"
echo "   运行在: http://localhost:8000"
echo "   健康检查: http://localhost:8000/health"

# 等待主服务启动
echo "   等待服务初始化..."
sleep 8

# 健康检查
MAX_RETRIES=5
RETRY_COUNT=0
SERVICE_STARTED=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        SERVICE_STARTED=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   健康检查失败，重试 $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ "$SERVICE_STARTED" = true ]; then
    echo -e "${GREEN}✅ FastAPI 主服务启动成功${NC}"
else
    echo -e "${RED}❌ FastAPI 主服务启动失败${NC}"
    echo "请查看日志: cat logs/backend.log"
    exit 1
fi

echo ""

# 启动IM渠道服务(如果已启用)
if [ "$IM_ENABLED" = true ]; then
    echo "=========================================="
    echo "启动IM渠道服务"
    echo "=========================================="

    for channel in $ENABLED_CHANNELS; do
        channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
        port_var="${channel_upper}_PORT"
        port=${!port_var}

        # 使用默认端口
        if [ -z "$port" ]; then
            case $channel in
                wework) port=8081 ;;
                feishu) port=8082 ;;
                dingtalk) port=8083 ;;
                slack) port=8084 ;;
                *) port=8080 ;;
            esac
        fi

        echo ""
        echo "🚀 启动 $channel 渠道服务..."
        echo "   端口: $port"

        # 根据渠道类型启动相应服务
        case $channel in
            wework)
                $PYTHON_CMD -m backend.channels.wework.server > logs/wework.log 2>&1 &
                CHANNEL_PID=$!
                echo $CHANNEL_PID > logs/wework.pid
                ;;
            feishu)
                $PYTHON_CMD -m backend.channels.feishu.server > logs/feishu.log 2>&1 &
                CHANNEL_PID=$!
                echo $CHANNEL_PID > logs/feishu.pid
                ;;
            dingtalk)
                $PYTHON_CMD -m backend.channels.dingtalk.server > logs/dingtalk.log 2>&1 &
                CHANNEL_PID=$!
                echo $CHANNEL_PID > logs/dingtalk.pid
                ;;
            slack)
                $PYTHON_CMD -m backend.channels.slack.server > logs/slack.log 2>&1 &
                CHANNEL_PID=$!
                echo $CHANNEL_PID > logs/slack.pid
                ;;
            *)
                echo -e "${RED}   ❌ 未知渠道: $channel${NC}"
                continue
                ;;
        esac

        echo -e "${GREEN}   PID: $CHANNEL_PID${NC}"
        echo "   运行在: http://localhost:$port"

        # 等待服务启动
        sleep 6

        # 检查端口是否监听
        if lsof -i:$port > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $channel 渠道服务启动成功${NC}"
        else
            echo -e "${YELLOW}⚠️  $channel 渠道服务可能未启动${NC}"
            echo "请查看日志: cat logs/${channel}.log"
        fi
    done
else
    echo -e "${BLUE}ℹ️  跳过IM渠道服务（未配置）${NC}"
fi

echo ""

# 步骤 5: 启动前端服务
echo "🎨 步骤 5/5: 启动前端服务"
echo "----------------------------------------"

# 启动 Admin UI (端口3000)
echo "🚀 启动 Admin UI (端口3000)..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "⚠️  前端依赖未安装，正在安装..."
    npm install
fi

npm run dev > ../logs/frontend.log 2>&1 &
ADMIN_UI_PID=$!
echo $ADMIN_UI_PID > ../logs/frontend.pid
echo -e "${GREEN}   PID: $ADMIN_UI_PID${NC}"
echo "   运行在: http://localhost:3000"

cd ..

# 等待Admin UI启动
sleep 5

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Admin UI 启动成功${NC}"
else
    echo -e "${RED}❌ Admin UI 启动失败${NC}"
    echo "请查看日志: cat logs/frontend.log"
fi

echo ""

# 启动 User UI (如果启用) - 使用同一前端项目的 user 模式
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "🚀 启动 User UI (端口$USER_UI_PORT)..."
    cd frontend

    # 使用 VITE_APP_MODE=user 启动第二个实例
    VITE_APP_MODE=user npm run dev -- --port $USER_UI_PORT > ../logs/frontend-user.log 2>&1 &
    USER_UI_PID=$!
    echo $USER_UI_PID > ../logs/frontend-user.pid
    echo -e "${GREEN}   PID: $USER_UI_PID${NC}"
    echo "   运行在: http://localhost:$USER_UI_PORT"

    cd ..

    # 等待User UI启动
    sleep 5

    if curl -s http://localhost:$USER_UI_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✅ User UI 启动成功${NC}"
    else
        echo -e "${RED}❌ User UI 启动失败${NC}"
        echo "请查看日志: cat logs/frontend-user.log"
    fi
fi

echo ""

# 完成
echo "=========================================="
echo -e "${GREEN}🎉 所有服务启动完成！${NC}"
echo "=========================================="
echo ""
echo "📱 访问地址:"
echo "   Admin UI: http://localhost:3000"
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "   User UI: http://localhost:$USER_UI_PORT"
fi
echo "   FastAPI 主服务: http://localhost:8000"
if [ "$IM_ENABLED" = true ]; then
    for channel in $ENABLED_CHANNELS; do
        channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
        port_var="${channel_upper}_PORT"
        port=${!port_var:-8081}
        echo "   $channel 渠道服务: http://localhost:$port"
    done
fi
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "🛑 停止服务:"
echo "   ./scripts/stop.sh"
echo ""
echo "📝 日志文件:"
echo "   FastAPI 主服务: logs/backend.log"
if [ "$IM_ENABLED" = true ]; then
    for channel in $ENABLED_CHANNELS; do
        echo "   $channel 渠道服务: logs/${channel}.log"
    done
fi
echo "   Admin UI: logs/frontend.log"
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "   User UI: logs/frontend-user.log"
fi
echo ""
echo "=========================================="

# 自动打开浏览器
if command -v open &> /dev/null; then
    echo "3 秒后自动打开浏览器..."
    sleep 3
    open http://localhost:3000
fi
