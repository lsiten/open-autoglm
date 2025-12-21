#!/bin/bash

# Open-AutoGLM 停止脚本
# 用于停止所有运行中的服务

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

# PID 文件路径
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  停止 Open-AutoGLM 服务${NC}"
echo -e "${BLUE}========================================${NC}\n"

# 停止后端服务
if [ -f "$BACKEND_PID_FILE" ]; then
    BACKEND_PID=$(cat "$BACKEND_PID_FILE")
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo -e "${BLUE}停止后端服务 (PID: $BACKEND_PID)${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
        echo -e "${GREEN}✓ 后端服务已停止${NC}"
    else
        echo -e "${YELLOW}后端服务未运行${NC}"
    fi
    rm -f "$BACKEND_PID_FILE"
else
    echo -e "${YELLOW}未找到后端 PID 文件${NC}"
fi

# 停止前端服务
if [ -f "$FRONTEND_PID_FILE" ]; then
    FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo -e "${BLUE}停止前端服务 (PID: $FRONTEND_PID)${NC}"
        kill "$FRONTEND_PID" 2>/dev/null || true
        echo -e "${GREEN}✓ 前端服务已停止${NC}"
    else
        echo -e "${YELLOW}前端服务未运行${NC}"
    fi
    rm -f "$FRONTEND_PID_FILE"
else
    echo -e "${YELLOW}未找到前端 PID 文件${NC}"
fi

# 清理可能的残留进程
echo -e "\n${BLUE}清理残留进程...${NC}"

# 停止所有 uvicorn 进程（与项目相关）
pkill -f "uvicorn.*gui.server.app" 2>/dev/null && echo -e "${GREEN}✓ 已清理后端残留进程${NC}" || echo -e "${YELLOW}未找到后端残留进程${NC}"

# 停止所有 vite 进程（与项目相关）
pkill -f "vite.*--host" 2>/dev/null && echo -e "${GREEN}✓ 已清理前端残留进程${NC}" || echo -e "${YELLOW}未找到前端残留进程${NC}"

# 检查端口占用
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}警告: 端口 8000 仍被占用${NC}"
    echo "  可能需要手动停止占用该端口的进程"
fi

if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}警告: 端口 5173 仍被占用${NC}"
    echo "  可能需要手动停止占用该端口的进程"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"

