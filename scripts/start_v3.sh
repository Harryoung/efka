#!/bin/bash

# 智能资料库管理员 v3.0 - 统一多渠道启动脚本
# 支持: WeWork, Feishu, DingTalk, Slack
# 使用混合配置模式自动检测并启动已配置的渠道

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🚀 智能资料库管理员 v3.0 - 启动脚本"
echo "=========================================="
echo ""

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 步骤 2: 检测已启用的渠道
echo "🔍 步骤 2/5: 检测已启用的渠道"
echo "----------------------------------------"

# 使用Python脚本检测已启用的渠道
echo "正在检测渠道配置..."
ENABLED_CHANNELS=$($PYTHON_CMD -c "
import os
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from backend.config.channel_config import get_channel_config

config = get_channel_config()
channels = config.get_enabled_channels()
print(' '.join(channels))
" 2>/dev/null)

if [ -z "$ENABLED_CHANNELS" ]; then
    echo -e "${YELLOW}⚠️  未检测到已启用的IM渠道${NC}"
    echo "   系统将以Web-only模式运行"
    IM_ENABLED=false
else
    echo -e "${GREEN}✅ 已启用的渠道: $ENABLED_CHANNELS${NC}"
    IM_ENABLED=true
fi

# 检测Employee Web UI配置
EMPLOYEE_UI_ENABLED=${EMPLOYEE_UI_ENABLED:-true}
EMPLOYEE_UI_PORT=${EMPLOYEE_UI_PORT:-3001}

if [ "$EMPLOYEE_UI_ENABLED" = "true" ]; then
    echo -e "${GREEN}✅ Employee Web UI 已启用 (端口: $EMPLOYEE_UI_PORT)${NC}"
else
    echo -e "${YELLOW}⏭️  Employee Web UI 未启用${NC}"
fi

echo ""

# 步骤 3: 检查端口
echo "🔌 步骤 3/5: 检查端口"
echo "----------------------------------------"

# 检查主服务端口
check_port 8000 || exit 1

# 检查Admin UI端口
check_port 3000 || exit 1

# 检查Employee UI端口(如果启用)
if [ "$EMPLOYEE_UI_ENABLED" = "true" ]; then
    check_port $EMPLOYEE_UI_PORT || exit 1
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
if [ ! -f "backend/.venv_installed" ]; then
    echo "⚠️  后端依赖未安装，正在安装..."
    pip3 install -r backend/requirements.txt
    touch backend/.venv_installed
fi

mkdir -p logs

echo ""
echo "=========================================="
echo "启动后端服务"
echo "=========================================="

# 启动 FastAPI 主服务（Admin API，端口8000）
echo "🚀 启动 FastAPI 主服务（Admin API + Employee API）..."
$PYTHON_CMD -m backend.main > logs/backend.log 2>&1 &
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

# 启动 Employee UI (如果启用)
if [ "$EMPLOYEE_UI_ENABLED" = "true" ]; then
    if [ -d "frontend-employee" ]; then
        echo "🚀 启动 Employee UI (端口$EMPLOYEE_UI_PORT)..."
        cd frontend-employee

        if [ ! -d "node_modules" ]; then
            echo "⚠️  Employee UI依赖未安装，正在安装..."
            npm install
        fi

        npm run dev > ../logs/frontend-employee.log 2>&1 &
        EMPLOYEE_UI_PID=$!
        echo $EMPLOYEE_UI_PID > ../logs/frontend-employee.pid
        echo -e "${GREEN}   PID: $EMPLOYEE_UI_PID${NC}"
        echo "   运行在: http://localhost:$EMPLOYEE_UI_PORT"

        cd ..

        # 等待Employee UI启动
        sleep 5

        if curl -s http://localhost:$EMPLOYEE_UI_PORT > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Employee UI 启动成功${NC}"
        else
            echo -e "${RED}❌ Employee UI 启动失败${NC}"
            echo "请查看日志: cat logs/frontend-employee.log"
        fi
    else
        echo -e "${YELLOW}⚠️  frontend-employee/ 目录不存在，跳过启动${NC}"
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
if [ "$EMPLOYEE_UI_ENABLED" = "true" ] && [ -d "frontend-employee" ]; then
    echo "   Employee UI: http://localhost:$EMPLOYEE_UI_PORT"
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
if [ "$EMPLOYEE_UI_ENABLED" = "true" ] && [ -d "frontend-employee" ]; then
    echo "   Employee UI: logs/frontend-employee.log"
fi
echo ""
echo "=========================================="

# 自动打开浏览器
if command -v open &> /dev/null; then
    echo "3 秒后自动打开浏览器..."
    sleep 3
    open http://localhost:3000
fi
