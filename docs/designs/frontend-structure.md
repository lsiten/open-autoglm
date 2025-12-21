# 前端项目结构文档

## 概述

本文档描述了 Open-AutoGLM GUI 前端项目的结构组织，包括组件、Composables、工具函数等的详细说明。

## 项目结构

```
gui/web/src/
├── App.vue                    # 根组件
├── main.ts                    # 应用入口
├── router/                    # 路由配置
│   └── index.ts
├── i18n.ts                    # 国际化配置
├── style.css                  # 全局样式
├── vite-env.d.ts             # TypeScript 类型定义
│
├── views/                     # 页面视图
│   └── Dashboard.vue         # 主仪表板页面（~800行，已优化）
│
├── components/                # Vue 组件
│   ├── dashboard/            # 仪表板相关组件
│   │   ├── DeviceSidebar.vue          # 设备侧边栏
│   │   ├── TopBar.vue                # 顶部导航栏
│   │   ├── ChatArea.vue              # 聊天区域容器
│   │   ├── ChatInput.vue              # 聊天输入框
│   │   ├── MessageList.vue            # 消息列表
│   │   ├── ScreenMirror.vue            # 屏幕镜像
│   │   ├── EmptyState.vue             # 空状态显示
│   │   ├── TaskDialog.vue             # 任务创建/编辑对话框
│   │   ├── ConfigDialog.vue           # 模型配置对话框
│   │   ├── PermissionsDialog.vue      # 权限配置对话框
│   │   ├── AppMatchingConfigDialog.vue # 应用匹配配置对话框
│   │   ├── SystemPromptConfigDialog.vue # 系统提示词配置对话框
│   │   ├── ConnectionGuideDialog.vue   # 设备连接向导
│   │   ├── ImagePreviewDialog.vue      # 图片预览对话框
│   │   └── messages/                   # 消息类型组件
│   │       ├── InfoMessage.vue         # 信息消息
│   │       ├── ScreenshotMessage.vue   # 截图消息
│   │       ├── ThinkMessage.vue        # 思考/推理消息
│   │       ├── AnswerMessage.vue        # 回答/操作消息
│   │       ├── ErrorMessage.vue        # 错误消息
│   │       ├── ConfirmMessage.vue      # 确认交互消息
│   │       └── InputMessage.vue        # 输入交互消息
│   └── HelloWorld.vue         # 示例组件
│
├── composables/              # Vue Composables（可复用逻辑）
│   ├── useWebSocket.ts        # WebSocket 连接管理
│   ├── useScreenStream.ts     # 屏幕流管理
│   ├── useMessageHandler.ts   # 消息处理逻辑
│   ├── useDeviceManagement.ts # 设备管理
│   ├── useImagePreview.ts    # 图片预览功能
│   ├── useTaskManagement.ts  # 任务管理（创建、选择、删除、执行）
│   ├── useInputEnhancement.ts # 输入增强（应用建议、文件上传）
│   ├── useConnectionWizard.ts # 连接向导（USB、WiFi、WebRTC）
│   ├── useConfigManagement.ts # 配置管理（应用匹配、系统提示词）
│   ├── usePermissions.ts     # 权限管理
│   ├── useInteraction.ts     # 交互处理（确认、输入）
│   ├── useModelConfig.ts     # 模型配置
│   ├── useStreamQuality.ts   # 流质量设置
│   ├── useDeviceEdit.ts      # 设备编辑
│   ├── useTaskEdit.ts        # 任务编辑
│   └── useAppMatchingUI.ts   # 应用匹配 UI 辅助函数
│
├── utils/                     # 工具函数
│   ├── db.ts                 # IndexedDB 数据库操作
│   ├── messageFormatter.ts   # 消息格式化（HTML 转义、样式）
│   └── platformDetector.ts    # 平台检测工具
│
└── locales/                  # 国际化资源
    ├── zh.json               # 中文
    ├── en.json               # 英文
    ├── ja.json               # 日文
    └── ko.json               # 韩文
```

## 核心文件说明

### Dashboard.vue

主仪表板页面，经过优化后从 1701 行减少到约 800 行。

**主要职责：**
- 整合所有子组件和 composables
- 管理全局状态
- 处理组件间通信

**使用的 Composables：**
- `useWebSocket` - WebSocket 连接
- `useScreenStream` - 屏幕流
- `useMessageHandler` - 消息处理
- `useDeviceManagement` - 设备管理
- `useImagePreview` - 图片预览
- `useTaskManagement` - 任务管理
- `useInputEnhancement` - 输入增强
- `useConnectionWizard` - 连接向导
- `useConfigManagement` - 配置管理
- `usePermissions` - 权限管理
- `useInteraction` - 交互处理
- `useModelConfig` - 模型配置
- `useStreamQuality` - 流质量
- `useDeviceEdit` - 设备编辑
- `useTaskEdit` - 任务编辑
- `useAppMatchingUI` - 应用匹配 UI

## Composables 详细说明

### 通信相关

#### useWebSocket.ts
管理 WebSocket 连接和消息处理。

**功能：**
- WebSocket 连接管理（连接、重连、错误处理）
- 消息路由（log、screenshot、status、interaction）
- 连接状态管理

**返回值：**
- `wsConnected` - 连接状态
- `wsError` - 错误信息
- `connectWS` - 连接函数

#### useScreenStream.ts
管理设备屏幕流和交互。

**功能：**
- 屏幕截图获取和显示
- 鼠标交互（点击、滑动）
- 系统操作（Home、Back、Recent）
- FPS 计算
- 横竖屏检测

**返回值：**
- `latestScreenshot` - 最新截图
- `isLandscape` - 是否横屏
- `fps` - 帧率
- `isStreaming` - 是否正在流式传输
- `clickEffects` - 点击效果
- `startStreamLoop` - 启动流循环
- `forceRefreshFrame` - 强制刷新帧
- `handleMouseDown/Move/Up` - 鼠标事件处理
- `goHome/Back/Recent` - 系统操作

### 数据管理相关

#### useDeviceManagement.ts
设备管理逻辑。

**功能：**
- 获取设备列表
- 选择设备
- 删除设备
- 设备重命名

**返回值：**
- `devices` - 设备列表
- `loadingDevices` - 加载状态
- `fetchDevices` - 获取设备
- `selectDevice` - 选择设备
- `deleteDevice` - 删除设备
- `handleDeviceRenamed` - 处理重命名

#### useTaskManagement.ts
任务管理核心逻辑。

**功能：**
- 获取会话和任务列表
- 创建任务/会话
- 选择任务/会话
- 删除任务/会话
- 加载消息（分页）
- 发送消息
- 启动/停止任务
- 刷新任务日志

**返回值：**
- `startingTask` - 启动中状态
- `stoppingTask` - 停止中状态
- `hasMoreMessages` - 是否有更多消息
- `isLoadingMore` - 是否正在加载更多
- `taskLogRefreshInterval` - 任务日志刷新间隔
- `fetchData` - 获取数据
- `createTask` - 创建任务
- `selectTask` - 选择任务
- `deleteTask` - 删除任务
- `loadMessages` - 加载消息
- `handleChatScroll` - 处理聊天滚动
- `refreshTaskLogs` - 刷新任务日志
- `sendMessage` - 发送消息
- `startBackgroundTask` - 启动后台任务
- `stopTask` - 停止任务

#### useMessageHandler.ts
消息处理逻辑。

**功能：**
- 处理 WebSocket 日志消息
- 转换日志为聊天消息
- 管理消息状态（thinking、info、error 等）

**返回值：**
- `handleLog` - 处理日志
- `convertLogsToChat` - 转换日志为聊天

### UI 交互相关

#### useInputEnhancement.ts
输入增强功能。

**功能：**
- 应用建议（@ 触发）
- 文件上传
- 附件管理

**返回值：**
- `availableApps` - 可用应用列表
- `showAppSuggestions` - 是否显示应用建议
- `appSuggestionQuery` - 应用建议查询
- `attachments` - 附件列表
- `fileInput` - 文件输入引用
- `fetchDeviceApps` - 获取设备应用
- `onInputChange` - 输入变化处理
- `selectApp` - 选择应用
- `triggerAppSelect` - 触发应用选择
- `triggerUpload` - 触发上传
- `handleFileSelect` - 处理文件选择
- `removeAttachment` - 移除附件

#### useImagePreview.ts
图片预览功能。

**功能：**
- 打开图片预览
- 图片导航（上一张/下一张）
- 键盘导航（方向键、ESC）

**返回值：**
- `imagePreviewVisible` - 预览可见性
- `imagePreviewUrl` - 预览图片 URL
- `imagePreviewIndex` - 当前图片索引
- `sessionImages` - 会话图片列表
- `openImagePreview` - 打开预览
- `showPreviousImage` - 显示上一张
- `showNextImage` - 显示下一张
- `handleImagePreviewKeydown` - 键盘事件处理

#### useInteraction.ts
交互处理（确认、输入）。

**功能：**
- 处理确认交互
- 处理输入交互
- 发送交互响应到后端

**返回值：**
- `handleCardAction` - 处理确认操作
- `handleCardInput` - 处理输入

### 配置相关

#### useConfigManagement.ts
配置管理（应用匹配、系统提示词）。

**功能：**
- 加载/保存应用匹配配置
- 加载/保存系统提示词配置
- 重置配置到默认值

**返回值：**
- `showAppMatchingConfig` - 应用匹配配置对话框可见性
- `appMatchingConfig` - 应用匹配配置数据
- `showSystemPromptConfig` - 系统提示词配置对话框可见性
- `systemPromptConfig` - 系统提示词配置数据
- `loadAppMatchingConfig` - 加载应用匹配配置
- `saveAppMatchingConfig` - 保存应用匹配配置
- `resetAppMatchingConfig` - 重置应用匹配配置
- `loadSystemPromptConfig` - 加载系统提示词配置
- `saveSystemPromptConfig` - 保存系统提示词配置
- `resetSystemPromptConfig` - 重置系统提示词配置

#### useModelConfig.ts
模型配置管理。

**功能：**
- 管理模型配置（baseUrl、model、apiKey）
- 提供商切换（vLLM、Ollama、Bailian、Gemini、Claude）
- 同步配置到后端

**返回值：**
- `showConfig` - 配置对话框可见性
- `selectedProvider` - 选中的提供商
- `config` - 配置数据
- `updateProviderConfig` - 更新提供商配置
- `syncConfigToBackend` - 同步配置到后端
- `saveConfig` - 保存配置

#### usePermissions.ts
权限管理。

**功能：**
- 加载设备权限
- 保存设备权限

**返回值：**
- `showPermissions` - 权限对话框可见性
- `devicePermissions` - 设备权限数据
- `openPermissions` - 打开权限对话框
- `savePermissions` - 保存权限

#### useStreamQuality.ts
流质量设置。

**功能：**
- 更新流质量（1080p、720p、480p、360p、auto）

**返回值：**
- `streamQuality` - 当前流质量
- `updateStreamQuality` - 更新流质量

### 向导相关

#### useConnectionWizard.ts
设备连接向导。

**功能：**
- USB 连接检测
- WiFi 模式启用
- WiFi 连接
- WebRTC 连接

**返回值：**
- `wizardStep` - 向导步骤
- `wizardType` - 向导类型
- `checkingUsb` - USB 检测中状态
- `usbStatus` - USB 状态
- `enablingWifi` - WiFi 启用中状态
- `connectingWifi` - WiFi 连接中状态
- `wifiIp` - WiFi IP 地址
- `webrtcUrl` - WebRTC URL
- `checkUsbConnection` - 检测 USB 连接
- `enableWifiMode` - 启用 WiFi 模式
- `connectWifi` - 连接 WiFi
- `handleWizardNext` - 下一步
- `handleWizardPrev` - 上一步
- `finishWizard` - 完成向导

### 编辑相关

#### useDeviceEdit.ts
设备编辑功能。

**功能：**
- 开始编辑设备名称
- 取消编辑
- 保存设备名称

**返回值：**
- `editingDeviceId` - 正在编辑的设备 ID
- `editName` - 编辑中的名称
- `startEdit` - 开始编辑
- `cancelEdit` - 取消编辑
- `saveDeviceName` - 保存设备名称

#### useTaskEdit.ts
任务编辑功能。

**功能：**
- 开始编辑任务名称
- 保存任务名称

**返回值：**
- `showEditTaskDialog` - 编辑对话框可见性
- `editTaskNameValue` - 编辑中的任务名称
- `taskToEdit` - 正在编辑的任务
- `startEditTask` - 开始编辑任务
- `saveTaskName` - 保存任务名称

#### useAppMatchingUI.ts
应用匹配 UI 辅助函数。

**功能：**
- 添加/删除映射
- 更新映射关键字
- 添加/删除包名
- 更新包平台

**返回值：**
- `addMapping` - 添加映射
- `removeMapping` - 删除映射
- `updateMappingKey` - 更新映射关键字
- `addPackage` - 添加包名
- `removePackage` - 删除包名
- `updatePackagePlatform` - 更新包平台

## 工具函数说明

### db.ts
IndexedDB 数据库操作封装。

**主要功能：**
- 会话管理（添加、获取、更新、删除）
- 消息管理（添加、获取、更新、删除，支持分页）
- 设备别名管理
- 配置管理

### messageFormatter.ts
消息格式化工具。

**主要功能：**
- `escapeHtml` - HTML 转义（防止 XSS）
- `formatThink` - 格式化思考内容（琥珀色主题）
- `formatAnswer` - 格式化回答内容（绿色主题）

### platformDetector.ts
平台检测工具。

**主要功能：**
- `detectPlatform` - 根据包名检测平台（华为、小米、OPPO 等）
- `availablePlatforms` - 可用平台列表

## 组件说明

### 布局组件

#### DeviceSidebar.vue
设备侧边栏组件。

**功能：**
- 显示设备列表
- 设备连接状态
- 设备选择
- 设备重命名
- 设备删除
- 导航到设置

#### TopBar.vue
顶部导航栏组件。

**功能：**
- 侧边栏切换
- 任务/会话选择器
- 权限按钮
- 任务管理按钮（创建、编辑、删除、启动、停止）
- 语言切换

### 内容组件

#### ChatArea.vue
聊天区域容器。

**功能：**
- 包含 EmptyState 和 MessageList
- 管理滚动

#### MessageList.vue
消息列表组件。

**功能：**
- 渲染消息列表
- 使用各种消息类型组件

#### ChatInput.vue
聊天输入组件。

**功能：**
- 文本输入
- 应用建议
- 附件上传
- 发送消息

#### ScreenMirror.vue
屏幕镜像组件。

**功能：**
- 显示设备屏幕
- 鼠标交互
- 系统操作按钮
- 流质量选择

### 对话框组件

#### TaskDialog.vue
任务创建/编辑对话框。

**功能：**
- 创建新任务/会话
- 编辑任务名称
- 任务类型选择（chat/background）
- 任务详情输入

#### ConfigDialog.vue
模型配置对话框。

**功能：**
- 选择模型提供商
- 配置模型参数（baseUrl、model、apiKey）
- 保存配置

#### PermissionsDialog.vue
权限配置对话框。

**功能：**
- 配置设备权限（安装应用、支付、微信回复、发送短信、打电话）

#### AppMatchingConfigDialog.vue
应用匹配配置对话框。

**功能：**
- 系统应用映射配置
- LLM 提示词模板配置
- 支持滚动（最大高度 60vh）

#### SystemPromptConfigDialog.vue
系统提示词配置对话框。

**功能：**
- 中文系统提示词编辑
- 英文系统提示词编辑
- 保存/重置配置

#### ConnectionGuideDialog.vue
设备连接向导对话框。

**功能：**
- USB 连接向导
- WiFi 连接向导
- WebRTC 连接向导

#### ImagePreviewDialog.vue
图片预览对话框。

**功能：**
- 全屏图片预览
- 图片导航（上一张/下一张）
- 键盘导航支持

### 消息类型组件

#### InfoMessage.vue
信息消息组件。

**功能：**
- 显示信息消息
- 可折叠
- 支持截图显示

#### ScreenshotMessage.vue
截图消息组件。

**功能：**
- 显示独立截图
- 点击放大

#### ThinkMessage.vue
思考消息组件。

**功能：**
- 显示 AI 思考过程
- 可折叠（默认折叠）
- 支持截图显示
- 格式化显示推理链

#### AnswerMessage.vue
回答消息组件。

**功能：**
- 显示 AI 回答/操作
- 格式化显示操作命令

#### ErrorMessage.vue
错误消息组件。

**功能：**
- 显示任务失败/错误信息
- 红色主题
- 显示失败原因

#### ConfirmMessage.vue
确认交互消息组件。

**功能：**
- 显示确认选项
- 处理用户选择

#### InputMessage.vue
输入交互消息组件。

**功能：**
- 显示输入提示
- 处理用户输入

### 其他组件

#### EmptyState.vue
空状态组件。

**功能：**
- 无设备状态
- 空聊天状态
- 空日志状态

## 数据流

### WebSocket 消息流

```
后端 → WebSocket → useWebSocket → 
  ├─ log → useMessageHandler → chatHistory
  ├─ screenshot → useScreenStream → latestScreenshot
  ├─ status → taskStatuses
  └─ interaction → chatHistory (交互消息)
```

### 任务执行流

```
用户输入 → ChatInput → sendMessage (useTaskManagement) → 
  API POST /tasks/{id}/start → 
  后端执行 → WebSocket 推送日志 → 
  useMessageHandler 处理 → chatHistory 更新 → UI 显示
```

### 设备管理流

```
设备列表 → useDeviceManagement.fetchDevices → 
  API GET /devices/ → 
  更新 devices → DeviceSidebar 显示
```

## 状态管理

### 全局状态（Dashboard.vue）

- `activeDeviceId` - 当前选中的设备 ID
- `activeTaskId` - 当前选中的任务/会话 ID
- `sessions` - 会话列表
- `backgroundTasks` - 后台任务列表
- `chatHistory` - 聊天历史
- `taskStatuses` - 任务状态映射
- `devices` - 设备列表（来自 useDeviceManagement）
- `availableApps` - 可用应用列表（来自 useInputEnhancement）

### 本地状态（各 Composables）

每个 composable 管理自己的局部状态，通过返回值暴露给组件使用。

## 优化历史

### 2025-01-XX: Dashboard.vue 模块化优化

**目标：** 将 Dashboard.vue 从 1701 行减少到 800 行以内

**优化措施：**
1. 提取业务逻辑到 Composables
2. 拆分 UI 组件
3. 提取工具函数

**结果：**
- 代码行数：1701 → 806 行（减少 52.5%）
- 创建了 16 个 Composables
- 创建了 20+ 个组件
- 创建了 3 个工具函数

## 开发指南

### 添加新功能

1. **如果是业务逻辑：** 创建新的 composable
2. **如果是 UI 组件：** 创建新的 Vue 组件
3. **如果是工具函数：** 添加到 `utils/` 目录

### 修改现有功能

1. **查找对应的 composable 或组件**
2. **在对应文件中修改**
3. **确保类型定义正确**

### 最佳实践

1. **保持 Composables 单一职责**
2. **组件尽量小而专注**
3. **使用 TypeScript 类型**
4. **遵循 Vue 3 Composition API 规范**
5. **保持代码可读性和可维护性**

## 依赖关系

```
Dashboard.vue
├── Components (UI)
│   ├── DeviceSidebar
│   ├── TopBar
│   ├── ChatArea
│   │   ├── EmptyState
│   │   └── MessageList
│   │       └── Message Components
│   ├── ChatInput
│   ├── ScreenMirror
│   └── Dialogs
├── Composables (Logic)
│   ├── useWebSocket
│   ├── useScreenStream
│   ├── useMessageHandler
│   ├── useDeviceManagement
│   ├── useTaskManagement (依赖 useInputEnhancement)
│   ├── useInputEnhancement
│   └── ... (其他 composables)
└── Utils (Helpers)
    ├── db
    ├── messageFormatter
    └── platformDetector
```

## 注意事项

1. **初始化顺序：** 某些 composables 有依赖关系，需要按正确顺序初始化（如 `useInputEnhancement` 需要在 `useTaskManagement` 之前）
2. **状态同步：** 多个 composables 可能共享状态，需要确保状态同步
3. **错误处理：** 所有 API 调用都应该有错误处理
4. **类型安全：** 使用 TypeScript 确保类型安全

