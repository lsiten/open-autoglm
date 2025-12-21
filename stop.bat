@echo off
REM Open-AutoGLM 停止脚本 (Windows)
REM 用于停止所有运行中的服务

setlocal enabledelayedexpansion

REM 项目根目录
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

echo ========================================
echo   停止 Open-AutoGLM 服务
echo ========================================
echo.

REM 停止后端服务（uvicorn）
echo 停止后端服务...
taskkill /F /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1
for /f "tokens=2" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="" (
        taskkill /F /PID !PID! >nul 2>&1
        echo [✓] 已停止后端服务 (PID: !PID!)
    )
)

REM 停止前端服务（vite）
echo 停止前端服务...
taskkill /F /FI "WINDOWTITLE eq *Open-AutoGLM Frontend*" >nul 2>&1
for /f "tokens=2" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    set "PID=%%a"
    if not "!PID!"=="" (
        taskkill /F /PID !PID! >nul 2>&1
        echo [✓] 已停止前端服务 (PID: !PID!)
    )
)

REM 清理 Python 进程（与项目相关）
echo.
echo 清理残留进程...
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if not errorlevel 1 (
    for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr "PID:"') do (
        set "PID=%%a"
        set "PID=!PID:PID:=!"
        wmic process where "ProcessId=!PID!" get CommandLine 2>nul | findstr /I "run_gui.py" >nul
        if not errorlevel 1 (
            taskkill /F /PID !PID! >nul 2>&1
            echo [✓] 已清理后端残留进程 (PID: !PID!)
        )
    )
)

REM 检查端口占用
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 8000 仍被占用
    echo   可能需要手动停止占用该端口的进程
)

netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 5173 仍被占用
    echo   可能需要手动停止占用该端口的进程
)

echo.
echo ========================================
echo   所有服务已停止
echo ========================================
echo.
pause

