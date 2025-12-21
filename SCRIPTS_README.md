# 一键启动脚本使用说明

本项目提供了一键启动和停止脚本，方便快速启动后端和前端服务。

## 脚本说明

### macOS / Linux

- **`start.sh`** - 一键启动脚本
- **`stop.sh`** - 一键停止脚本

### Windows

- **`start.bat`** - 一键启动脚本
- **`stop.bat`** - 一键停止脚本

## 使用方法

### macOS / Linux

#### 启动服务

```bash
# 普通模式
./start.sh

# 开发模式（启用自动重载）
./start.sh --dev
# 或
./start.sh -d
```

脚本会自动：
1. 检查 Python 和 Node.js 环境
2. 检查并安装依赖（如果需要）
3. 检查 ADB 连接（可选）
4. 启动后端服务（http://127.0.0.1:8000）
5. 启动前端服务（http://localhost:5173）

**开发模式说明：**
- 使用 `--dev` 或 `-d` 参数启动开发模式
- 开发模式下，后端代码修改后会自动重载
- 适合开发调试时使用

#### 停止服务

```bash
./stop.sh
```

或者直接按 `Ctrl+C` 停止所有服务。

### Windows

#### 启动服务

双击 `start.bat` 或在命令行中运行：

```cmd
REM 普通模式
start.bat

REM 开发模式（启用自动重载）
start.bat --dev
REM 或
start.bat -d
```

脚本会自动：
1. 检查 Python 和 Node.js 环境
2. 检查并安装依赖（如果需要）
3. 检查 ADB 连接（可选）
4. 启动后端服务（http://127.0.0.1:8000）
5. 启动前端服务（http://localhost:5173，在新窗口中运行）

**开发模式说明：**
- 使用 `--dev` 或 `-d` 参数启动开发模式
- 开发模式下，后端代码修改后会自动重载
- 适合开发调试时使用

#### 停止服务

双击 `stop.bat` 或在命令行中运行：

```cmd
stop.bat
```

或者关闭前端服务窗口和启动脚本窗口。

## 功能特性

### 启动脚本功能

- ✅ 自动检查环境（Python、Node.js、npm）
- ✅ 自动检查并安装依赖
- ✅ 检查端口占用情况
- ✅ 检查 ADB 设备连接（可选）
- ✅ 后台运行服务
- ✅ 彩色输出，易于阅读
- ✅ 自动清理功能（Ctrl+C 时）

### 停止脚本功能

- ✅ 停止所有相关服务
- ✅ 清理残留进程
- ✅ 检查端口占用情况

## 服务地址

启动成功后，可以通过以下地址访问：

- **后端 API**: http://127.0.0.1:8000
- **前端界面**: http://localhost:5173

## 日志文件

- **后端日志**: `.backend.log`
- **前端日志**: `.frontend.log`

## 常见问题

### 端口被占用

如果启动时提示端口被占用，可以：

1. 使用 `stop.sh` 或 `stop.bat` 停止之前的服务
2. 手动查找并停止占用端口的进程
3. 修改 `run_gui.py` 中的端口配置

### 依赖安装失败

如果依赖安装失败，可以手动安装：

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd gui/web
npm install
```

### 服务启动失败

如果服务启动失败，请查看日志文件：

- `.backend.log` - 后端日志
- `.frontend.log` - 前端日志

## 高级用法

### 开发模式（自动重载）

使用启动脚本的 `--dev` 参数：

```bash
# macOS / Linux
./start.sh --dev

# Windows
start.bat --dev
```

或者直接使用 Python 脚本：

```bash
python run_gui.py --dev
```

### 仅启动后端

```bash
python run_gui.py --backend-only
```

### 使用 HTTPS

```bash
python run_gui.py --https
```

注意：使用 HTTPS 需要先配置证书文件（`certs/key.pem` 和 `certs/cert.pem`）。

### 查看帮助信息

```bash
# macOS / Linux
./start.sh --help

# Windows
start.bat --help
```

## 注意事项

1. 首次运行需要安装依赖，可能需要一些时间
2. 确保 Python 3.10+ 和 Node.js 已正确安装
3. 如果使用 ADB，确保设备已连接并授权
4. 停止服务时建议使用 `stop.sh` 或 `stop.bat`，确保完全清理

