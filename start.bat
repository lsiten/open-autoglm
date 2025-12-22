@echo off
REM Open-AutoGLM 一键启动脚本 (Windows)
REM 用于同时启动后端和前端服务

setlocal enabledelayedexpansion

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM 默认值
set "DEV_MODE=0"
set "USE_HTTPS=1"

REM 解析命令行参数
:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="--dev" (
    set "DEV_MODE=1"
    shift
    goto parse_args
)
if /i "%~1"=="-d" (
    set "DEV_MODE=1"
    shift
    goto parse_args
)
if /i "%~1"=="--https" (
    set "USE_HTTPS=1"
    shift
    goto parse_args
)
if /i "%~1"=="--http" (
    set "USE_HTTPS=0"
    shift
    goto parse_args
)
if /i "%~1"=="--help" (
    echo 用法: %~nx0 [选项]
    echo.
    echo 选项:
    echo   --dev, -d      启动开发模式（启用自动重载）
    echo   --https         使用 HTTPS（默认）
    echo   --http          使用 HTTP
    echo   --help          显示此帮助信息
    exit /b 0
)
if /i "%~1"=="-h" (
    echo 用法: %~nx0 [选项]
    echo.
    echo 选项:
    echo   --dev, -d    启动开发模式（启用自动重载）
    echo   --help       显示此帮助信息
    exit /b 0
)
echo [错误] 未知参数: %~1
echo 使用 --help 查看帮助信息
exit /b 1
:args_done

REM PID 文件路径
set "BACKEND_PID_FILE=%PROJECT_ROOT%.backend.pid"
set "FRONTEND_PID_FILE=%PROJECT_ROOT%.frontend.pid"

echo ========================================
echo   Open-AutoGLM 一键启动脚本
if "%DEV_MODE%"=="1" (
    echo   开发模式 (自动重载已启用)
)
if "%USE_HTTPS%"=="1" (
    echo   HTTPS 模式 (安全连接)
) else (
    echo   HTTP 模式
)
echo ========================================
echo.

REM 检查 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo 请先安装 Python 3.10 或更高版本
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python 未正确安装
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo [✓] Python 版本: %PYTHON_VERSION%

REM 检查 Node.js 和 npm
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js
    echo 请先安装 Node.js
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 npm
    echo 请先安装 npm
    pause
    exit /b 1
)

for /f %%v in ('node --version') do set NODE_VERSION=%%v
for /f %%v in ('npm --version') do set NPM_VERSION=%%v
echo [✓] Node.js 版本: %NODE_VERSION%
echo [✓] npm 版本: %NPM_VERSION%

echo.
echo 检查依赖...

REM 检查 Python 依赖
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 uvicorn，正在安装 GUI 依赖...
    python -m pip install uvicorn fastapi websockets python-multipart >nul 2>&1
)

REM 检查其他必需的依赖
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 fastapi，正在安装...
    python -m pip install fastapi >nul 2>&1
)

REM 安装 GUI 依赖（如果 requirements-gui.txt 存在）
if exist "requirements-gui.txt" (
    echo [信息] 安装 GUI 依赖...
    python -m pip install -r requirements-gui.txt >nul 2>&1
)

REM 安装基础依赖（如果 requirements.txt 存在）
if exist "requirements.txt" (
    echo [信息] 安装基础依赖...
    python -m pip install -r requirements.txt >nul 2>&1
)

REM 最终验证关键依赖
python -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [错误] uvicorn 安装失败
    echo 请手动运行: python -m pip install uvicorn fastapi websockets python-multipart
    pause
    exit /b 1
)

REM 检查前端依赖
if not exist "gui\web\node_modules" (
    echo [警告] 未找到前端依赖，正在安装...
    cd gui\web
    call npm install
    cd ..\..
)

echo [✓] 依赖检查完成

REM 检查并安装 ADB
where adb >nul 2>&1
if not errorlevel 1 (
    REM ADB 已安装，检查设备连接
    adb devices >nul 2>&1
    if not errorlevel 1 (
        echo [✓] ADB 工具已就绪
    ) else (
        echo [警告] 未检测到已连接的设备（可选，不影响启动）
    )
) else (
    REM ADB 未安装，尝试自动安装
    echo [警告] 未找到 ADB 工具，正在尝试自动安装...
    
    set "INSTALL_SUCCESS=0"
    
    REM 尝试使用 Chocolatey 安装
    where choco >nul 2>&1
    if not errorlevel 1 (
        echo [信息] 使用 Chocolatey 安装 ADB...
        choco install adb -y >nul 2>&1
        if not errorlevel 1 (
            REM 刷新环境变量（如果 refreshenv 可用）
            where refreshenv >nul 2>&1
            if not errorlevel 1 (
                call refreshenv >nul 2>&1
            )
            REM 尝试添加到 PATH（Chocolatey 通常安装到 ProgramData）
            set "PATH=%PATH%;%ProgramData%\chocolatey\bin"
            where adb >nul 2>&1
            if not errorlevel 1 (
                set "INSTALL_SUCCESS=1"
                echo [✓] ADB 安装成功
            )
        )
    )
    
    REM 如果 Chocolatey 安装失败，尝试使用 winget
    if "%INSTALL_SUCCESS%"=="0" (
        where winget >nul 2>&1
        if not errorlevel 1 (
            echo [信息] 使用 winget 安装 ADB...
            winget install --id Google.PlatformTools --accept-package-agreements --accept-source-agreements >nul 2>&1
            if not errorlevel 1 (
                REM 刷新 PATH（winget 通常安装到 Program Files）
                set "PATH=%PATH%;%ProgramFiles%\Android\android-sdk\platform-tools"
                where adb >nul 2>&1
                if not errorlevel 1 (
                    set "INSTALL_SUCCESS=1"
                    echo [✓] ADB 安装成功
                )
            )
        )
    )
    
    REM 验证安装结果
    if "%INSTALL_SUCCESS%"=="1" (
        where adb >nul 2>&1
        if not errorlevel 1 (
            adb version >nul 2>&1
            if not errorlevel 1 (
                echo [✓] ADB 工具已就绪
                REM 检查设备连接
                adb devices >nul 2>&1
                if not errorlevel 1 (
                    echo [✓] 检测到已连接的设备
                ) else (
                    echo [警告] 未检测到已连接的设备（可选，不影响启动）
                )
            ) else (
                echo [警告] ADB 已安装，但可能需要重新启动终端或刷新环境变量
            )
        )
    ) else (
        echo [警告] ADB 自动安装失败，请手动安装
        echo [信息] 手动安装方法：
        echo   1. 使用 Chocolatey: choco install adb
        echo   2. 使用 winget: winget install Google.PlatformTools
        echo   3. 手动下载: https://developer.android.com/studio/releases/platform-tools
        echo      下载后解压，将 platform-tools 目录添加到系统 PATH 环境变量
        echo [警告] ADB 未安装（可选，不影响启动）
    )
)

echo.
echo 启动后端服务...

if "%DEV_MODE%"=="1" (
    echo [开发模式] 启用自动重载
)

REM 检查端口是否被占用（Windows 方式）
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8000 已被占用
    echo 请先停止占用该端口的服务，或修改 run_gui.py 中的端口配置
    pause
    exit /b 1
)

REM 构建启动命令
set "BACKEND_CMD=python run_gui.py --backend-only"
if "%DEV_MODE%"=="1" (
    set "BACKEND_CMD=%BACKEND_CMD% --dev"
)
if "%USE_HTTPS%"=="1" (
    set "BACKEND_CMD=%BACKEND_CMD% --https"
)

REM 启动后端（后台运行）
start /b %BACKEND_CMD% > .backend.log 2>&1
timeout /t 3 /nobreak >nul

echo [✓] 后端服务已启动
if "%USE_HTTPS%"=="1" (
    echo    后端地址: https://127.0.0.1:8000
) else (
    echo    后端地址: http://127.0.0.1:8000
)
if "%DEV_MODE%"=="1" (
    echo    开发模式: 代码修改后会自动重载
)

echo.
echo 启动前端服务...

cd gui\web

REM 设置 HTTPS 环境变量
if "%USE_HTTPS%"=="1" (
    set "VITE_HTTPS=true"
) else (
    set "VITE_HTTPS=false"
)

REM 启动前端（新窗口运行，方便查看日志）
start "Open-AutoGLM Frontend" cmd /k "set VITE_HTTPS=%VITE_HTTPS% && npm run dev -- --host"

cd ..\..

timeout /t 5 /nobreak >nul

echo [✓] 前端服务已启动
if "%USE_HTTPS%"=="1" (
    echo    前端地址: https://localhost:5173
) else (
    echo    前端地址: http://localhost:5173
)

echo.
echo ========================================
echo   服务启动成功！
echo ========================================
if "%USE_HTTPS%"=="1" (
    echo 后端地址: https://127.0.0.1:8000
    echo 前端地址: https://localhost:5173
    echo 注意: 使用自签名证书，浏览器会显示安全警告，请点击"高级"-^>"继续访问"
) else (
    echo 后端地址: http://127.0.0.1:8000
    echo 前端地址: http://localhost:5173
)
if "%DEV_MODE%"=="1" (
    echo 开发模式: 代码修改后会自动重载
)
echo.
echo 提示:
echo   - 关闭此窗口将停止后端服务
echo   - 前端服务在独立窗口中运行
echo   - 后端日志: .backend.log
if "%DEV_MODE%"=="1" (
    echo   - 开发模式: 修改代码后后端会自动重载
)
echo.
echo 正在运行中...
echo 按 Ctrl+C 停止后端服务

REM 保持脚本运行
:loop
timeout /t 1 /nobreak >nul
goto loop

