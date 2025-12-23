@echo off
REM Open-AutoGLM 停止脚本 (Windows)
REM 用于停止所有运行中的服务（通过端口直接 kill）

setlocal enabledelayedexpansion

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM 端口定义
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

echo ========================================
echo   停止 Open-AutoGLM 服务
echo ========================================
echo.

REM 通过端口停止后端服务
echo 停止后端服务 (端口: %BACKEND_PORT%)...
set "BACKEND_FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT%" ^| findstr "LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="" (
        set "BACKEND_FOUND=1"
        echo   停止进程 (PID: !PID!)
        taskkill /F /PID !PID! >nul 2>&1
        if errorlevel 1 (
            echo   [警告] 无法停止进程 !PID!，可能需要管理员权限
        ) else (
            echo   [✓] 已停止进程 (PID: !PID!)
        )
    )
)
if "!BACKEND_FOUND!"=="0" (
    echo   [信息] 后端服务未运行 (端口 %BACKEND_PORT% 未被占用)
) else (
    echo [✓] 后端服务已停止
)

REM 通过端口停止前端服务
echo.
echo 停止前端服务 (端口: %FRONTEND_PORT%)...
set "FRONTEND_FOUND=0"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="" (
        set "FRONTEND_FOUND=1"
        echo   停止进程 (PID: !PID!)
        taskkill /F /PID !PID! >nul 2>&1
        if errorlevel 1 (
            echo   [警告] 无法停止进程 !PID!，可能需要管理员权限
        ) else (
            echo   [✓] 已停止进程 (PID: !PID!)
        )
    )
)
if "!FRONTEND_FOUND!"=="0" (
    echo   [信息] 前端服务未运行 (端口 %FRONTEND_PORT% 未被占用)
) else (
    echo [✓] 前端服务已停止
)

REM 清理残留进程
echo.
echo 清理残留进程...

REM 停止所有 uvicorn 相关进程
taskkill /F /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1
if errorlevel 1 (
    echo   [信息] 未找到 uvicorn 残留进程
) else (
    echo   [✓] 已清理后端残留进程
)

REM 停止所有 vite 相关进程
taskkill /F /FI "WINDOWTITLE eq *vite*" >nul 2>&1
if errorlevel 1 (
    echo   [信息] 未找到 vite 残留进程
) else (
    echo   [✓] 已清理前端残留进程
)

REM 清理 Python 进程（与项目相关）
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if not errorlevel 1 (
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr "PID:"') do (
        set "PID=%%a"
        set "PID=!PID:PID:=!"
        wmic process where "ProcessId=!PID!" get CommandLine 2>nul | findstr /I "run_gui.py" >nul
        if not errorlevel 1 (
            taskkill /F /PID !PID! >nul 2>&1
            echo   [✓] 已清理 Python 残留进程 (PID: !PID!)
        )
    )
)

REM 清理 PID 文件（如果存在）
if exist "%PROJECT_ROOT%\.backend.pid" del /f /q "%PROJECT_ROOT%\.backend.pid" >nul 2>&1
if exist "%PROJECT_ROOT%\.frontend.pid" del /f /q "%PROJECT_ROOT%\.frontend.pid" >nul 2>&1

REM 最终检查端口占用
echo.
echo 最终检查端口占用...
netstat -ano | findstr ":%BACKEND_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 %BACKEND_PORT% 仍被占用
    echo   可能需要手动停止占用该端口的进程
) else (
    echo [✓] 端口 %BACKEND_PORT% 已释放
)

netstat -ano | findstr ":%FRONTEND_PORT%" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 %FRONTEND_PORT% 仍被占用
    echo   可能需要手动停止占用该端口的进程
) else (
    echo [✓] 端口 %FRONTEND_PORT% 已释放
)

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
echo.
pause

