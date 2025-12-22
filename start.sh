#!/bin/bash

# Open-AutoGLM 一键启动脚本
# 用于同时启动后端和前端服务

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

# 全局变量
DEV_MODE="false"
USE_HTTPS="true"  # 默认启用 HTTPS

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}正在停止服务...${NC}"
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
            echo -e "${BLUE}停止后端服务 (PID: $BACKEND_PID)${NC}"
            kill "$BACKEND_PID" 2>/dev/null || true
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
            echo -e "${BLUE}停止前端服务 (PID: $FRONTEND_PID)${NC}"
            kill "$FRONTEND_PID" 2>/dev/null || true
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    # 清理可能的残留进程
    pkill -f "uvicorn.*gui.server.app" 2>/dev/null || true
    pkill -f "vite.*--host" 2>/dev/null || true
    
    echo -e "${GREEN}清理完成${NC}"
    exit 0
}

# 注册清理函数
trap cleanup SIGINT SIGTERM EXIT

# 检查 Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}错误: 未找到 Python3${NC}"
        echo "请先安装 Python 3.10 或更高版本"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓ Python 版本: $PYTHON_VERSION${NC}"
}

# 检查 Node.js 和 npm
check_node() {
    if ! command -v node &> /dev/null; then
        echo -e "${RED}错误: 未找到 Node.js${NC}"
        echo "请先安装 Node.js"
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}错误: 未找到 npm${NC}"
        echo "请先安装 npm"
        exit 1
    fi
    
    NODE_VERSION=$(node --version)
    NPM_VERSION=$(npm --version)
    echo -e "${GREEN}✓ Node.js 版本: $NODE_VERSION${NC}"
    echo -e "${GREEN}✓ npm 版本: $NPM_VERSION${NC}"
}

# 检查依赖
check_dependencies() {
    echo -e "${BLUE}检查依赖...${NC}"
    
    # 检查 Python 依赖
    if ! python3 -c "import uvicorn" 2>/dev/null; then
        echo -e "${YELLOW}警告: 未找到 uvicorn，正在安装 GUI 依赖...${NC}"
        
        # 尝试安装，如果遇到 PEP 668 错误，提供建议
        if ! python3 -m pip install uvicorn fastapi websockets python-multipart 2>&1 | tee /tmp/pip_install.log | grep -v "already satisfied"; then
            if grep -q "externally-managed-environment\|PEP 668" /tmp/pip_install.log 2>/dev/null; then
                echo -e "${RED}错误: 系统 Python 环境受保护，无法直接安装依赖${NC}"
                echo -e "${YELLOW}建议解决方案：${NC}"
                echo "  1. 使用虚拟环境（推荐）："
                echo "     python3 -m venv venv"
                echo "     source venv/bin/activate"
                echo "     pip install -r requirements.txt"
                echo "     pip install uvicorn fastapi websockets python-multipart"
                echo ""
                echo "  2. 或使用 --break-system-packages（不推荐）："
                echo "     python3 -m pip install --break-system-packages uvicorn fastapi websockets python-multipart"
                exit 1
            fi
        fi
    fi
    
    # 检查其他必需的依赖
    if ! python3 -c "import fastapi" 2>/dev/null; then
        echo -e "${YELLOW}警告: 未找到 fastapi，正在安装...${NC}"
        python3 -m pip install fastapi 2>&1 | grep -v "already satisfied" || true
    fi
    
    # 安装 GUI 依赖（如果 requirements-gui.txt 存在）
    if [ -f "requirements-gui.txt" ]; then
        echo -e "${BLUE}安装 GUI 依赖...${NC}"
        python3 -m pip install -r requirements-gui.txt 2>&1 | grep -v "already satisfied" || true
    fi
    
    # 安装基础依赖（如果 requirements.txt 存在）
    if [ -f "requirements.txt" ]; then
        echo -e "${BLUE}安装基础依赖...${NC}"
        python3 -m pip install -r requirements.txt 2>&1 | grep -v "already satisfied" || true
    fi
    
    # 检查前端依赖
    if [ ! -d "gui/web/node_modules" ]; then
        echo -e "${YELLOW}警告: 未找到前端依赖，正在安装...${NC}"
        cd gui/web
        npm install
        cd "$PROJECT_ROOT"
    fi
    
    # 最终验证关键依赖
    if ! python3 -c "import uvicorn" 2>/dev/null; then
        echo -e "${RED}错误: uvicorn 安装失败或未正确安装${NC}"
        echo "请检查 Python 环境，或使用虚拟环境："
        echo "  python3 -m venv venv"
        echo "  source venv/bin/activate"
        echo "  pip install uvicorn fastapi websockets python-multipart"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 依赖检查完成${NC}"
}

# 检查并安装 ADB
check_adb() {
    if command -v adb &> /dev/null; then
        # ADB 已安装，检查设备连接
        DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep "device$" | wc -l | tr -d ' ')
        if [ "$DEVICES" -gt 0 ]; then
            echo -e "${GREEN}✓ 检测到 $DEVICES 个已连接的设备${NC}"
        else
            echo -e "${YELLOW}⚠ 未检测到已连接的设备（可选，不影响启动）${NC}"
        fi
    else
        # ADB 未安装，尝试自动安装
        echo -e "${YELLOW}⚠ 未找到 ADB 工具，正在尝试自动安装...${NC}"
        
        # 检测操作系统类型
        OS_TYPE="unknown"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            OS_TYPE="macos"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            OS_TYPE="linux"
        fi
        
        INSTALL_SUCCESS=false
        
        if [ "$OS_TYPE" = "macos" ]; then
            # macOS: 使用 Homebrew 安装
            if command -v brew &> /dev/null; then
                echo -e "${BLUE}使用 Homebrew 安装 ADB...${NC}"
                # 检查是否已安装
                if brew list android-platform-tools &> /dev/null 2>&1; then
                    echo -e "${GREEN}✓ ADB 已通过 Homebrew 安装${NC}"
                    INSTALL_SUCCESS=true
                else
                    # 尝试安装
                    if brew install android-platform-tools >/dev/null 2>&1; then
                        if command -v adb &> /dev/null; then
                            INSTALL_SUCCESS=true
                            echo -e "${GREEN}✓ ADB 安装成功${NC}"
                        else
                            # 尝试添加到 PATH
                            BREW_PREFIX=$(brew --prefix 2>/dev/null)
                            if [ -n "$BREW_PREFIX" ] && [ -f "$BREW_PREFIX/bin/adb" ]; then
                                export PATH="$PATH:$BREW_PREFIX/bin"
                                if command -v adb &> /dev/null; then
                                    INSTALL_SUCCESS=true
                                    echo -e "${GREEN}✓ ADB 安装成功${NC}"
                                else
                                    echo -e "${YELLOW}⚠ 安装完成，但可能需要重新加载 PATH${NC}"
                                    echo -e "${YELLOW}   请运行: export PATH=\$PATH:\$(brew --prefix)/bin${NC}"
                                fi
                            fi
                        fi
                    else
                        echo -e "${RED}错误: Homebrew 安装 ADB 失败${NC}"
                    fi
                fi
            else
                echo -e "${RED}错误: 未找到 Homebrew${NC}"
                echo -e "${YELLOW}请先安装 Homebrew:${NC}"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                echo -e "${YELLOW}或手动安装 ADB:${NC}"
                echo "  下载地址: https://developer.android.com/studio/releases/platform-tools"
            fi
        elif [ "$OS_TYPE" = "linux" ]; then
            # Linux: 检测包管理器并安装
            if command -v apt-get &> /dev/null; then
                # Debian/Ubuntu
                echo -e "${BLUE}使用 apt 安装 ADB...${NC}"
                if sudo apt-get update -qq && sudo apt-get install -y android-tools-adb 2>&1 | grep -v "already the newest\|0 upgraded"; then
                    if command -v adb &> /dev/null; then
                        INSTALL_SUCCESS=true
                        echo -e "${GREEN}✓ ADB 安装成功${NC}"
                    fi
                else
                    # 检查是否已经安装
                    if dpkg -l | grep -q android-tools-adb; then
                        echo -e "${GREEN}✓ ADB 已安装${NC}"
                        INSTALL_SUCCESS=true
                    fi
                fi
            elif command -v yum &> /dev/null; then
                # CentOS/RHEL (旧版本)
                echo -e "${BLUE}使用 yum 安装 ADB...${NC}"
                if sudo yum install -y android-tools 2>&1 | grep -v "already installed\|Nothing to do"; then
                    if command -v adb &> /dev/null; then
                        INSTALL_SUCCESS=true
                        echo -e "${GREEN}✓ ADB 安装成功${NC}"
                    fi
                fi
            elif command -v dnf &> /dev/null; then
                # Fedora/CentOS/RHEL (新版本)
                echo -e "${BLUE}使用 dnf 安装 ADB...${NC}"
                if sudo dnf install -y android-tools 2>&1 | grep -v "already installed\|Nothing to do"; then
                    if command -v adb &> /dev/null; then
                        INSTALL_SUCCESS=true
                        echo -e "${GREEN}✓ ADB 安装成功${NC}"
                    fi
                fi
            else
                echo -e "${RED}错误: 未找到支持的包管理器 (apt/yum/dnf)${NC}"
                echo -e "${YELLOW}请手动安装 ADB:${NC}"
                echo "  - Debian/Ubuntu: sudo apt-get install android-tools-adb"
                echo "  - CentOS/RHEL: sudo yum install android-tools"
                echo "  - Fedora: sudo dnf install android-tools"
            fi
        else
            echo -e "${RED}错误: 无法自动检测操作系统类型${NC}"
            echo -e "${YELLOW}请手动安装 ADB:${NC}"
            echo "  - macOS: brew install android-platform-tools"
            echo "  - Linux: sudo apt-get install android-tools-adb (或使用对应发行版的包管理器)"
            echo "  - Windows: 下载地址: https://developer.android.com/studio/releases/platform-tools"
        fi
        
        # 验证安装结果
        if [ "$INSTALL_SUCCESS" = "true" ] || command -v adb &> /dev/null; then
            # 验证 ADB 是否可用
            if adb version &> /dev/null; then
                echo -e "${GREEN}✓ ADB 工具已就绪${NC}"
                # 检查设备连接
                DEVICES=$(adb devices 2>/dev/null | grep -v "List" | grep "device$" | wc -l | tr -d ' ')
                if [ "$DEVICES" -gt 0 ]; then
                    echo -e "${GREEN}✓ 检测到 $DEVICES 个已连接的设备${NC}"
                else
                    echo -e "${YELLOW}⚠ 未检测到已连接的设备（可选，不影响启动）${NC}"
                fi
            else
                echo -e "${YELLOW}⚠ ADB 已安装，但可能需要重新加载 PATH 或重启终端${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ ADB 安装失败或需要手动安装（可选，不影响启动）${NC}"
            echo -e "${YELLOW}   如需使用 Android 设备功能，请手动安装 ADB${NC}"
        fi
    fi
}

# 启动后端服务
start_backend() {
    echo -e "\n${BLUE}启动后端服务...${NC}"
    
    if [ "$DEV_MODE" = "true" ]; then
        echo -e "${YELLOW}开发模式: 启用自动重载${NC}"
    fi
    
    # 检查端口是否被占用
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}警告: 端口 8000 已被占用${NC}"
        echo "请先停止占用该端口的服务，或修改 run_gui.py 中的端口配置"
        exit 1
    fi
    
    # 构建启动命令
    BACKEND_CMD="python3 run_gui.py --backend-only"
    if [ "$DEV_MODE" = "true" ]; then
        BACKEND_CMD="$BACKEND_CMD --dev"
    fi
    if [ "$USE_HTTPS" = "true" ]; then
        BACKEND_CMD="$BACKEND_CMD --https"
    fi
    
    # 启动后端（后台运行）
    $BACKEND_CMD > .backend.log 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
    
    # 等待后端启动
    echo -e "${BLUE}等待后端服务启动...${NC}"
    sleep 3
    
    # 检查后端是否成功启动
    if ps -p "$BACKEND_PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"
        if [ "$USE_HTTPS" = "true" ]; then
            echo -e "${GREEN}  后端地址: https://127.0.0.1:8000${NC}"
        else
            echo -e "${GREEN}  后端地址: http://127.0.0.1:8000${NC}"
        fi
        if [ "$DEV_MODE" = "true" ]; then
            echo -e "${YELLOW}  开发模式: 代码修改后会自动重载${NC}"
        fi
    else
        echo -e "${RED}错误: 后端服务启动失败${NC}"
        echo "请查看 .backend.log 文件获取详细信息"
        exit 1
    fi
}

# 启动前端服务
start_frontend() {
    echo -e "\n${BLUE}启动前端服务...${NC}"
    
    if [ "$USE_HTTPS" = "true" ]; then
        echo -e "${YELLOW}HTTPS 模式: 启用安全连接${NC}"
        export VITE_HTTPS="true"
    else
        export VITE_HTTPS="false"
    fi
    
    cd gui/web
    
    # 启动前端（后台运行）
    npm run dev -- --host > ../../.frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"
    
    cd "$PROJECT_ROOT"
    
    # 等待前端启动
    echo -e "${BLUE}等待前端服务启动...${NC}"
    sleep 5
    
    # 检查前端是否成功启动
    if ps -p "$FRONTEND_PID" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"
        if [ "$USE_HTTPS" = "true" ]; then
            echo -e "${GREEN}  前端地址: https://localhost:5173${NC}"
        else
            echo -e "${GREEN}  前端地址: http://localhost:5173${NC}"
        fi
    else
        echo -e "${RED}错误: 前端服务启动失败${NC}"
        echo "请查看 .frontend.log 文件获取详细信息"
        exit 1
    fi
}

# 检查并生成证书
check_certificates() {
    CERT_DIR="$PROJECT_ROOT/certs"
    KEY_FILE="$CERT_DIR/key.pem"
    CERT_FILE="$CERT_DIR/cert.pem"
    CONFIG_FILE="$CERT_DIR/openssl.cnf"
    
    if [ ! -f "$KEY_FILE" ] || [ ! -f "$CERT_FILE" ]; then
        echo -e "${YELLOW}证书文件不存在，正在生成自签名证书...${NC}"
        
        # 确保 certs 目录存在
        mkdir -p "$CERT_DIR"
        
        # 如果 openssl.cnf 不存在，创建一个默认的
        if [ ! -f "$CONFIG_FILE" ]; then
            cat > "$CONFIG_FILE" << 'EOF'
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_req

[dn]
C = CN
ST = State
L = City
O = Open-AutoGLM
CN = localhost

[v3_req]
subjectAltName = @alt_names

[alt_names]
IP.1 = 127.0.0.1
IP.2 = ::1
DNS.1 = localhost
DNS.2 = *.localhost
EOF
        fi
        
        # 生成私钥和证书
        openssl req -x509 -newkey rsa:2048 -keyout "$KEY_FILE" -out "$CERT_FILE" \
            -days 365 -nodes -config "$CONFIG_FILE" 2>/dev/null
        
        if [ $? -eq 0 ] && [ -f "$KEY_FILE" ] && [ -f "$CERT_FILE" ]; then
            echo -e "${GREEN}✓ 证书生成成功${NC}"
            chmod 600 "$KEY_FILE"
            chmod 644 "$CERT_FILE"
        else
            echo -e "${RED}错误: 证书生成失败${NC}"
            echo "请确保已安装 openssl，或手动生成证书："
            echo "  openssl req -x509 -newkey rsa:2048 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ 证书文件已存在${NC}"
    fi
}

# 解析命令行参数
parse_args() {
    DEV_MODE="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev|-d)
                DEV_MODE="true"
                shift
                ;;
            --http)
                USE_HTTPS="false"
                shift
                ;;
            --https)
                USE_HTTPS="true"
                shift
                ;;
            --help|-h)
                echo "用法: $0 [选项]"
                echo ""
                echo "选项:"
                echo "  --dev, -d      启动开发模式（启用自动重载）"
                echo "  --https        使用 HTTPS（默认）"
                echo "  --http         使用 HTTP"
                echo "  --help, -h      显示此帮助信息"
                exit 0
                ;;
            *)
                echo -e "${RED}未知参数: $1${NC}"
                echo "使用 --help 查看帮助信息"
                exit 1
                ;;
        esac
    done
}

# 主函数
main() {
    # 解析命令行参数
    parse_args "$@"
    
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Open-AutoGLM 一键启动脚本${NC}"
    if [ "$DEV_MODE" = "true" ]; then
        echo -e "${YELLOW}  开发模式 (自动重载已启用)${NC}"
    fi
    if [ "$USE_HTTPS" = "true" ]; then
        echo -e "${YELLOW}  HTTPS 模式 (安全连接)${NC}"
    else
        echo -e "${BLUE}  HTTP 模式${NC}"
    fi
    echo -e "${BLUE}========================================${NC}\n"
    
    # 检查环境
    check_python
    check_node
    check_dependencies
    check_adb
    
    # 如果使用 HTTPS，检查证书
    if [ "$USE_HTTPS" = "true" ]; then
        echo ""
        check_certificates
    fi
    
    echo ""
    
    # 启动服务
    start_backend
    start_frontend
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  服务启动成功！${NC}"
    echo -e "${GREEN}========================================${NC}"
    if [ "$USE_HTTPS" = "true" ]; then
        echo -e "${BLUE}后端地址: ${GREEN}https://127.0.0.1:8000${NC}"
        echo -e "${BLUE}前端地址: ${GREEN}https://localhost:5173${NC}"
        echo -e "${YELLOW}注意: 使用自签名证书，浏览器会显示安全警告，请点击"高级"->"继续访问"${NC}"
    else
        echo -e "${BLUE}后端地址: ${GREEN}http://127.0.0.1:8000${NC}"
        echo -e "${BLUE}前端地址: ${GREEN}http://localhost:5173${NC}"
    fi
    if [ "$DEV_MODE" = "true" ]; then
        echo -e "${YELLOW}开发模式: 代码修改后会自动重载${NC}"
    fi
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo -e "  - 按 Ctrl+C 停止所有服务"
    echo -e "  - 后端日志: ${BLUE}.backend.log${NC}"
    echo -e "  - 前端日志: ${BLUE}.frontend.log${NC}"
    if [ "$DEV_MODE" = "true" ]; then
        echo -e "  - 开发模式: 修改代码后后端会自动重载"
    fi
    echo ""
    echo -e "${BLUE}正在运行中...${NC}"
    
    # 保持脚本运行
    wait
}

# 运行主函数
main "$@"

