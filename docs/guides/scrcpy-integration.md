# Scrcpy 集成指南

## 概述

本项目已集成 scrcpy 作为高性能屏幕镜像方案。scrcpy 使用 H.264 编码传输视频流，比传统的 ADB 截图方法快得多，能够提供更流畅的实时屏幕镜像体验。

## 优势

1. **高性能**：使用 H.264 硬件编码，帧率可达 60fps
2. **低延迟**：比传统 ADB 截图方法延迟更低
3. **低带宽**：H.264 编码压缩率高，网络传输效率高
4. **实时性**：能够实时获取每一帧屏幕画面

## 系统要求

### 必需软件

1. **scrcpy**：必须安装并可在 PATH 中访问
   - 下载：https://github.com/Genymobile/scrcpy
   - 安装后确保 `scrcpy` 命令可用

2. **ffmpeg**：用于解码 H.264 视频流
   - 下载：https://ffmpeg.org/download.html
   - 安装后确保 `ffmpeg` 命令可用

### Python 依赖

- `PIL` (Pillow)：图像处理
- 其他依赖已在 `requirements.txt` 中

## 使用方法

### 自动使用

系统会自动检测 scrcpy 是否可用，如果可用，会优先使用 scrcpy 方法：

```python
from phone_agent.adb.screenshot import get_screenshot

# 自动尝试 scrcpy（如果可用），否则使用其他方法
screenshot = get_screenshot(device_id="your_device_id")
```

### 手动指定方法

```python
# 优先使用 scrcpy
screenshot = get_screenshot(
    device_id="your_device_id",
    preferred_method="scrcpy"
)

# 如果 scrcpy 不可用，会自动 fallback 到其他方法
```

### 配置参数

```python
from phone_agent.adb.scrcpy_capture import get_screenshot_scrcpy

screenshot = get_screenshot_scrcpy(
    device_id="your_device_id",
    max_width=720,      # 最大宽度
    bit_rate=2000000,   # 比特率 (2Mbps)
    max_fps=60,         # 最大帧率
    quality=75          # JPEG 质量
)
```

## 工作原理

1. **启动 scrcpy**：系统启动 scrcpy 进程，配置为无窗口、无控制模式
2. **H.264 编码**：设备端使用硬件编码生成 H.264 视频流
3. **ffmpeg 解码**：使用 ffmpeg 将 H.264 流解码为 PNG 帧
4. **帧提取**：从解码流中提取图像帧
5. **格式转换**：将 PNG 转换为 JPEG 格式供前端使用

## 方法优先级

系统按以下顺序尝试截图方法：

1. **scrcpy**（如果可用）- 最高性能
2. **raw** - 最快的 ADB 方法
3. **gzip** - 适合 USB 2.0/WiFi
4. **png** - 最兼容的 fallback 方法

## 性能对比

| 方法 | 延迟 | 帧率 | 带宽 |
|------|------|------|------|
| scrcpy | ~16ms | 60fps | 低 |
| raw | ~200ms | 5-10fps | 中 |
| gzip | ~300ms | 5-10fps | 中 |
| png | ~500ms | 3-5fps | 高 |

## 故障排除

### scrcpy 不可用

如果 scrcpy 不可用，系统会自动 fallback 到其他方法。检查：

1. scrcpy 是否已安装：`scrcpy --version`
2. scrcpy 是否在 PATH 中
3. 设备是否已连接：`adb devices`

### ffmpeg 不可用

如果 ffmpeg 不可用，scrcpy 方法将无法工作。检查：

1. ffmpeg 是否已安装：`ffmpeg -version`
2. ffmpeg 是否在 PATH 中

### 连接问题

如果遇到连接问题：

1. 检查 ADB 连接：`adb devices`
2. 检查端口是否被占用
3. 查看日志输出获取详细错误信息

## 清理资源

当不再需要 scrcpy 连接时，可以手动清理：

```python
from phone_agent.adb.scrcpy_capture import cleanup_scrcpy

cleanup_scrcpy(device_id="your_device_id")
```

## 注意事项

1. scrcpy 需要设备支持硬件编码（大多数现代 Android 设备都支持）
2. 首次连接可能需要几秒钟启动时间
3. scrcpy 进程会在后台运行，确保在不需要时清理资源
4. 如果设备不支持硬件编码，scrcpy 可能无法工作，系统会自动 fallback

## 未来改进

- [ ] 支持 WebSocket 直接传输 H.264 流
- [ ] 支持硬件解码加速
- [ ] 支持多设备同时连接
- [ ] 优化内存使用

