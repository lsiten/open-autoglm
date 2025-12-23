#!/bin/bash

# Open-AutoGLM 停止脚本
# 用于停止所有运行中的服务（通过端口直接 kill）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 端口定义
BACKEND_PORT=8000
FRONTEND_PORT=5173

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  停止 Open-AutoGLM 服务${NC}"
echo -e "${BLUE}========================================${NC}\n"

# 通过端口停止后端服务
echo -e "${BLUE}停止后端服务 (端口: $BACKEND_PORT)...${NC}"
BACKEND_PIDS=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
if [ -n "$BACKEND_PIDS" ]; then
    for PID in $BACKEND_PIDS; do
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${BLUE}  停止进程 (PID: $PID)${NC}"
            kill "$PID" 2>/dev/null || true
            # 等待进程结束，如果还在运行则强制 kill
            sleep 1
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
    done
    echo -e "${GREEN}✓ 后端服务已停止${NC}"
else
    echo -e "${YELLOW}后端服务未运行 (端口 $BACKEND_PORT 未被占用)${NC}"
fi

# 通过端口停止前端服务
echo -e "${BLUE}停止前端服务 (端口: $FRONTEND_PORT)...${NC}"
FRONTEND_PIDS=$(lsof -ti:$FRONTEND_PORT 2>/dev/null || true)
if [ -n "$FRONTEND_PIDS" ]; then
    for PID in $FRONTEND_PIDS; do
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${BLUE}  停止进程 (PID: $PID)${NC}"
            kill "$PID" 2>/dev/null || true
            # 等待进程结束，如果还在运行则强制 kill
            sleep 1
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null || true
            fi
        fi
    done
    echo -e "${GREEN}✓ 前端服务已停止${NC}"
else
    echo -e "${YELLOW}前端服务未运行 (端口 $FRONTEND_PORT 未被占用)${NC}"
fi

# 清理可能的残留进程
echo -e "\n${BLUE}清理残留进程...${NC}"

# 停止所有 uvicorn 进程（与项目相关）
pkill -f "uvicorn.*gui.server.app" 2>/dev/null && echo -e "${GREEN}✓ 已清理后端残留进程${NC}" || echo -e "${YELLOW}未找到后端残留进程${NC}"

# 停止所有 vite 进程（与项目相关）
pkill -f "vite.*--host" 2>/dev/null && echo -e "${GREEN}✓ 已清理前端残留进程${NC}" || echo -e "${YELLOW}未找到前端残留进程${NC}"

# 清理 PID 文件（如果存在）
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"
rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE" 2>/dev/null || true

# 最终检查端口占用
echo -e "\n${BLUE}最终检查端口占用...${NC}"
if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}警告: 端口 $BACKEND_PORT 仍被占用${NC}"
    echo "  可能需要手动停止占用该端口的进程"
else
    echo -e "${GREEN}✓ 端口 $BACKEND_PORT 已释放${NC}"
fi

if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}警告: 端口 $FRONTEND_PORT 仍被占用${NC}"
    echo "  可能需要手动停止占用该端口的进程"
else
    echo -e "${GREEN}✓ 端口 $FRONTEND_PORT 已释放${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"

