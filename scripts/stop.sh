#!/bin/bash

# EFKA - Stop Script
# Usage: ./scripts/stop.sh

echo "=========================================="
echo "🛑 EFKA - Stopping Services"
echo "=========================================="
echo ""

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Read WeWork port configuration from .env (default 8081 if not set)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi
WEWORK_PORT=${WEWORK_PORT:-8081}

# Read process IDs
# Stop FastAPI main service (port 8000)
if [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    echo "Stopping FastAPI main service (PID: $BACKEND_PID)..."

    if kill $BACKEND_PID 2>/dev/null; then
        echo -e "${GREEN}✅ FastAPI main service stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  FastAPI main service process not found or already stopped${NC}"
    fi

    rm logs/backend.pid
else
    echo -e "${YELLOW}⚠️  backend.pid file not found${NC}"

    # Try to find and stop by port
    BACKEND_PID=$(lsof -ti :8000)
    if [ ! -z "$BACKEND_PID" ]; then
        echo "Found FastAPI main service process (PID: $BACKEND_PID), stopping..."
        kill $BACKEND_PID
        echo -e "${GREEN}✅ FastAPI main service stopped${NC}"
    fi
fi

# Stop Flask WeWork callback service (using configured port)
if [ -f "logs/wework.pid" ]; then
    WEWORK_PID=$(cat logs/wework.pid)
    echo "Stopping Flask WeWork callback service (PID: $WEWORK_PID)..."

    if kill $WEWORK_PID 2>/dev/null; then
        echo -e "${GREEN}✅ Flask WeWork callback service stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  Flask WeWork callback service process not found or already stopped${NC}"
    fi

    rm logs/wework.pid
else
    echo -e "${YELLOW}⚠️  wework.pid file not found${NC}"

    # Try to find and stop by port
    WEWORK_PID=$(lsof -ti :$WEWORK_PORT)
    if [ ! -z "$WEWORK_PID" ]; then
        echo "Found Flask WeWork callback service process (PID: $WEWORK_PID), stopping..."
        kill $WEWORK_PID
        echo -e "${GREEN}✅ Flask WeWork callback service stopped${NC}"
    fi
fi

# Function to stop UI services (handles npm -> node -> vite process chain)
stop_ui_service() {
    local main_pid=$1
    local port=$2
    local service_name=$3
    local stopped=false

    if [ ! -z "$main_pid" ]; then
        echo "Stopping $service_name main process (PID: $main_pid)..."

        # Find all child processes (recursive)
        local child_pids=$(pgrep -P $main_pid)

        # Try graceful stop first
        if kill $main_pid 2>/dev/null; then
            sleep 0.5

            # Check if main process exited
            if ! kill -0 $main_pid 2>/dev/null; then
                stopped=true
            else
                # Main process didn't exit, force kill
                kill -9 $main_pid 2>/dev/null
                stopped=true
            fi
        fi

        # Clean up all child processes
        if [ ! -z "$child_pids" ]; then
            echo "Cleaning up $service_name child processes: $child_pids"
            for pid in $child_pids; do
                # Recursively clean up grandchild processes
                local grandchild_pids=$(pgrep -P $pid)
                if [ ! -z "$grandchild_pids" ]; then
                    kill -9 $grandchild_pids 2>/dev/null
                fi
                kill -9 $pid 2>/dev/null
            done
        fi
    fi

    # Final cleanup: find and kill all processes using the specified port
    local port_pids=$(lsof -ti :$port 2>/dev/null)
    if [ ! -z "$port_pids" ]; then
        echo "Cleaning up processes on port $port: $port_pids"
        kill -9 $port_pids 2>/dev/null
        stopped=true
    fi

    if [ "$stopped" = true ]; then
        echo -e "${GREEN}✅ $service_name stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  $service_name not running${NC}"
    fi
}

# Stop frontend service (Admin UI, port 3000)
stop_frontend() {
    stop_ui_service "$1" 3000 "Admin UI"
}

# Stop user frontend service (User UI, port 3001)
stop_user_ui() {
    local port=${USER_UI_PORT:-3001}
    stop_ui_service "$1" $port "User UI"
}

# Stop frontend service
if [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    stop_frontend $FRONTEND_PID
    rm logs/frontend.pid
else
    echo -e "${YELLOW}⚠️  frontend.pid file not found${NC}"
    # Find directly by port
    FRONTEND_PID=$(lsof -ti :3000 2>/dev/null | head -1)
    stop_frontend $FRONTEND_PID
fi

# Stop User UI service
if [ -f "logs/frontend-user.pid" ]; then
    USER_UI_PID=$(cat logs/frontend-user.pid)
    stop_user_ui $USER_UI_PID
    rm logs/frontend-user.pid
else
    echo -e "${YELLOW}⚠️  frontend-user.pid file not found${NC}"
    # Find directly by port
    USER_UI_PORT=${USER_UI_PORT:-3001}
    USER_UI_PID=$(lsof -ti :$USER_UI_PORT 2>/dev/null | head -1)
    stop_user_ui $USER_UI_PID
fi

# Stop wework-mcp service
echo "Stopping wework-mcp service..."
WEWORK_MCP_PIDS=$(pgrep -f wework-mcp)
if [ ! -z "$WEWORK_MCP_PIDS" ]; then
    echo "Found wework-mcp processes (PIDs: $WEWORK_MCP_PIDS), stopping..."
    kill $WEWORK_MCP_PIDS 2>/dev/null
    sleep 1
    # Check for remaining processes
    STILL_RUNNING=$(pgrep -f wework-mcp)
    if [ ! -z "$STILL_RUNNING" ]; then
        echo "Force stopping wework-mcp processes..."
        kill -9 $STILL_RUNNING 2>/dev/null
    fi
    echo -e "${GREEN}✅ wework-mcp service stopped${NC}"
else
    echo -e "${YELLOW}⚠️  wework-mcp process not found${NC}"
fi

# Stop other IM channel services (feishu, dingtalk, slack)
for channel in feishu dingtalk slack; do
    pid_file="logs/${channel}.pid"
    if [ -f "$pid_file" ]; then
        CHANNEL_PID=$(cat "$pid_file")
        echo "Stopping $channel channel service (PID: $CHANNEL_PID)..."
        if kill $CHANNEL_PID 2>/dev/null; then
            echo -e "${GREEN}✅ $channel channel service stopped${NC}"
        else
            echo -e "${YELLOW}⚠️  $channel channel service process not found or already stopped${NC}"
        fi
        rm "$pid_file"
    else
        # Try to find and stop by port
        channel_upper=$(echo "$channel" | tr '[:lower:]' '[:upper:]')
        port_var="${channel_upper}_PORT"
        port=${!port_var}
        if [ -z "$port" ]; then
            case $channel in
                feishu) port=8082 ;;
                dingtalk) port=8083 ;;
                slack) port=8084 ;;
                *) port=8080 ;;
            esac
        fi
        CHANNEL_PID=$(lsof -ti :$port 2>/dev/null)
        if [ ! -z "$CHANNEL_PID" ]; then
            echo "Found $channel channel service process (PID: $CHANNEL_PID), stopping..."
            kill $CHANNEL_PID
            echo -e "${GREEN}✅ $channel channel service stopped${NC}"
        fi
    fi
done

echo ""
echo "=========================================="
echo -e "${GREEN}✅ All services stopped${NC}"
echo "=========================================="
echo ""
echo "📝 Log files retained in logs/ directory"
echo "💡 Restart: ./scripts/start.sh"
echo ""
