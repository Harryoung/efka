#!/bin/bash

# EFKA v3.0 - Multi-channel Startup Script
# Supports: standalone mode and IM integration (WeWork, Feishu, DingTalk, Slack)
# Usage: ./scripts/start.sh [--mode <mode>]
# Modes: standalone (default), wework, feishu, dingtalk, slack

set -e  # Exit on error

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
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

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}⚠️  Port $port is already in use${NC}"
        return 1
    else
        echo -e "${GREEN}✅ Port $port is available${NC}"
        return 0
    fi
}

# Check if command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    else
        echo -e "${GREEN}✅ $1 is installed${NC}"
        return 0
    fi
}

# Check Node.js version (requires >= 20.19.0)
check_node_version() {
    local node_version=$(node --version 2>/dev/null | sed 's/v//')
    local required_version="20.19.0"

    if [ -z "$node_version" ]; then
        echo -e "${RED}❌ Cannot get Node.js version${NC}"
        return 1
    fi

    # Compare version numbers
    local node_major=$(echo "$node_version" | cut -d. -f1)
    local node_minor=$(echo "$node_version" | cut -d. -f2)
    local req_major=$(echo "$required_version" | cut -d. -f1)
    local req_minor=$(echo "$required_version" | cut -d. -f2)

    if [ "$node_major" -gt "$req_major" ] || \
       ([ "$node_major" -eq "$req_major" ] && [ "$node_minor" -ge "$req_minor" ]); then
        echo -e "${GREEN}✅ Node.js version: v$node_version (satisfies >= $required_version)${NC}"
        return 0
    else
        echo -e "${RED}❌ Node.js version too low: v$node_version${NC}"
        echo -e "${YELLOW}   Requires Node.js >= $required_version (Vite 7.x requirement)${NC}"
        echo -e "${YELLOW}   Upgrade methods:${NC}"
        echo -e "${YELLOW}   1. Using n: npm install -g n && n 22${NC}"
        echo -e "${YELLOW}   2. Using nvm: nvm install 22 && nvm use 22${NC}"
        echo -e "${YELLOW}   3. Direct download: https://nodejs.org/${NC}"
        return 1
    fi
}

# Step 1: Environment check
echo "📋 Step 1/5: Environment Check"
echo "----------------------------------------"

check_command python3 || exit 1
check_command node || exit 1
check_node_version || exit 1
check_command npm || exit 1

# Check environment file
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ .env file does not exist${NC}"
    echo "Please copy .env.example and configure environment variables"
    exit 1
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# Check and activate virtual environment
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Virtual environment detected, activating...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}⚠️  No virtual environment detected, creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    # New venv needs to reinstall dependencies, remove old marker
    rm -f backend/.venv_installed
    echo -e "${GREEN}✅ Virtual environment created and activated${NC}"
fi
PYTHON_CMD="python"

# Load environment variables
echo ""
echo "Loading environment variables..."
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✅ Environment variables loaded${NC}"
fi

echo ""

# Step 2: Determine run mode
echo "🔍 Step 2/5: Determine Run Mode"
echo "----------------------------------------"

# Determine run mode (CLI > ENV > default)
if [ -n "$MODE" ]; then
    RUN_MODE="$MODE"
elif [ -z "$RUN_MODE" ]; then
    RUN_MODE="standalone"
fi
export RUN_MODE

# Validate mode and set IM flag
case $RUN_MODE in
    standalone)
        IM_ENABLED=false
        echo -e "${GREEN}✅ Run mode: standalone (Pure Web)${NC}"
        ;;
    wework|feishu|dingtalk|slack)
        IM_ENABLED=true
        IM_CHANNEL=$RUN_MODE
        ENABLED_CHANNELS=$RUN_MODE
        echo -e "${GREEN}✅ Run mode: $RUN_MODE (IM Integration)${NC}"
        ;;
    *)
        echo -e "${RED}❌ Invalid mode: $RUN_MODE${NC}"
        echo "Valid modes: standalone, wework, feishu, dingtalk, slack"
        exit 1
        ;;
esac

# Detect User Web UI configuration
USER_UI_ENABLED=${USER_UI_ENABLED:-true}
USER_UI_PORT=${USER_UI_PORT:-3001}

if [ "$USER_UI_ENABLED" = "true" ]; then
    echo -e "${GREEN}✅ User Web UI enabled (port: $USER_UI_PORT)${NC}"
else
    echo -e "${YELLOW}⏭️  User Web UI not enabled${NC}"
fi

echo ""

# Step 3: Check ports
echo "🔌 Step 3/5: Check Ports"
echo "----------------------------------------"

# Check main service port
check_port 8000 || exit 1

# Check Admin UI port
check_port 3000 || exit 1

# Check User UI port (if enabled)
if [ "$USER_UI_ENABLED" = "true" ]; then
    check_port $USER_UI_PORT || exit 1
fi

# Check channel ports
for channel in $ENABLED_CHANNELS; do
    channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
    port_var="${channel_upper}_PORT"
    port=${!port_var}

    if [ -z "$port" ]; then
        # Use default port
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

# Step 4: Start backend services
echo "🔧 Step 4/5: Start Backend Services"
echo "----------------------------------------"

# Check backend dependencies
# Use .venv_installed file to mark dependency installation status
# Note: If requirements.txt is updated, manually delete this file to reinstall
if [ ! -f "backend/.venv_installed" ]; then
    echo "⚠️  Backend dependencies not installed, installing..."
    pip3 install -r backend/requirements.txt
    touch backend/.venv_installed
    echo "✅  Backend dependencies installed"
else
    echo "✅  Backend dependencies already installed (to update, delete backend/.venv_installed)"
fi

mkdir -p logs

# Create knowledge_base directory and copy skills (Agent security boundary requirement)
echo "📁 Creating knowledge base directory structure..."
mkdir -p "$PROJECT_ROOT/knowledge_base/.claude"
if [ -d "$PROJECT_ROOT/skills" ]; then
    echo "📋 Copying skills to knowledge base..."
    cp -r "$PROJECT_ROOT/skills" "$PROJECT_ROOT/knowledge_base/.claude/" 2>/dev/null || true
    echo -e "${GREEN}✅ Skills directory copied to knowledge_base/.claude/skills/${NC}"
fi

echo ""
echo "=========================================="
echo "Starting Backend Services"
echo "=========================================="

# Start FastAPI main service (Admin API, port 8000)
echo "🚀 Starting FastAPI main service (Admin API + User API)..."
echo "   Run mode: $RUN_MODE"
$PYTHON_CMD -m backend.main --mode $RUN_MODE > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > logs/backend.pid
echo -e "${GREEN}   PID: $BACKEND_PID${NC}"
echo "   Running at: http://localhost:8000"
echo "   Health check: http://localhost:8000/health"

# Wait for main service to start
echo "   Waiting for service initialization..."
sleep 8

# Health check
MAX_RETRIES=5
RETRY_COUNT=0
SERVICE_STARTED=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        SERVICE_STARTED=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Health check failed, retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ "$SERVICE_STARTED" = true ]; then
    echo -e "${GREEN}✅ FastAPI main service started successfully${NC}"
else
    echo -e "${RED}❌ FastAPI main service failed to start${NC}"
    echo "Please check logs: cat logs/backend.log"
    exit 1
fi

echo ""

# Start IM channel services (if enabled)
if [ "$IM_ENABLED" = true ]; then
    echo "=========================================="
    echo "Starting IM Channel Services"
    echo "=========================================="

    for channel in $ENABLED_CHANNELS; do
        channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
        port_var="${channel_upper}_PORT"
        port=${!port_var}

        # Use default port
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
        echo "🚀 Starting $channel channel service..."
        echo "   Port: $port"

        # Start corresponding service based on channel type
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
                echo -e "${RED}   ❌ Unknown channel: $channel${NC}"
                continue
                ;;
        esac

        echo -e "${GREEN}   PID: $CHANNEL_PID${NC}"
        echo "   Running at: http://localhost:$port"

        # Wait for service to start
        sleep 6

        # Check if port is listening
        if lsof -i:$port > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $channel channel service started successfully${NC}"
        else
            echo -e "${YELLOW}⚠️  $channel channel service may not have started${NC}"
            echo "Please check logs: cat logs/${channel}.log"
        fi
    done
else
    echo -e "${BLUE}ℹ️  Skipping IM channel services (not configured)${NC}"
fi

echo ""

# Step 5: Start frontend services
echo "🎨 Step 5/5: Start Frontend Services"
echo "----------------------------------------"

# Start Admin UI (port 3000)
echo "🚀 Starting Admin UI (port 3000)..."
cd frontend

if [ ! -d "node_modules" ]; then
    echo "⚠️  Frontend dependencies not installed, installing..."
    npm install
fi

npm run dev > ../logs/frontend.log 2>&1 &
ADMIN_UI_PID=$!
echo $ADMIN_UI_PID > ../logs/frontend.pid
echo -e "${GREEN}   PID: $ADMIN_UI_PID${NC}"
echo "   Running at: http://localhost:3000"

cd ..

# Wait for Admin UI to start
sleep 5

if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Admin UI started successfully${NC}"
else
    echo -e "${RED}❌ Admin UI failed to start${NC}"
    echo "Please check logs: cat logs/frontend.log"
fi

echo ""

# Start User UI (if enabled) - uses same frontend project in user mode
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "🚀 Starting User UI (port $USER_UI_PORT)..."
    cd frontend

    # Start second instance with VITE_APP_MODE=user
    VITE_APP_MODE=user npm run dev -- --port $USER_UI_PORT > ../logs/frontend-user.log 2>&1 &
    USER_UI_PID=$!
    echo $USER_UI_PID > ../logs/frontend-user.pid
    echo -e "${GREEN}   PID: $USER_UI_PID${NC}"
    echo "   Running at: http://localhost:$USER_UI_PORT"

    cd ..

    # Wait for User UI to start
    sleep 5

    if curl -s http://localhost:$USER_UI_PORT > /dev/null 2>&1; then
        echo -e "${GREEN}✅ User UI started successfully${NC}"
    else
        echo -e "${RED}❌ User UI failed to start${NC}"
        echo "Please check logs: cat logs/frontend-user.log"
    fi
fi

echo ""

# Complete
echo "=========================================="
echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo "=========================================="
echo ""
echo "📱 Access URLs:"
echo "   Admin UI: http://localhost:3000"
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "   User UI: http://localhost:$USER_UI_PORT"
fi
echo "   FastAPI Main Service: http://localhost:8000"
if [ "$IM_ENABLED" = true ]; then
    for channel in $ENABLED_CHANNELS; do
        channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
        port_var="${channel_upper}_PORT"
        port=${!port_var:-8081}
        echo "   $channel Channel Service: http://localhost:$port"
    done
fi
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "🛑 Stop services:"
echo "   ./scripts/stop.sh"
echo ""
echo "📝 Log files:"
echo "   FastAPI Main Service: logs/backend.log"
if [ "$IM_ENABLED" = true ]; then
    for channel in $ENABLED_CHANNELS; do
        echo "   $channel Channel Service: logs/${channel}.log"
    done
fi
echo "   Admin UI: logs/frontend.log"
if [ "$USER_UI_ENABLED" = "true" ]; then
    echo "   User UI: logs/frontend-user.log"
fi
echo ""
echo "=========================================="

# Auto-open browser
if command -v open &> /dev/null; then
    echo "Opening browser in 3 seconds..."
    sleep 3
    open http://localhost:3000
    if [ "$USER_UI_ENABLED" = "true" ]; then
        open http://localhost:$USER_UI_PORT
    fi
fi
