<template>
  <!-- Main Container: Force dark background and full viewport -->
  <div class="flex h-screen w-full bg-[#0f1115] text-gray-200 overflow-hidden font-sans">
    
    <!-- Left Sidebar: Device & Settings -->
    <DeviceSidebar
      v-model="sidebarOpen"
      :devices="devices"
      :active-device-id="activeDeviceId"
      :loading-devices="loadingDevices"
      :ws-connected="wsConnected"
      :ws-error="wsError"
      :ws-base-url="wsBaseUrl"
      :backend-root-url="backendRootUrl"
      @refresh-devices="fetchDevices"
      @select-device="selectDevice"
      @delete-device="deleteDevice"
      @show-connection-guide="showConnectionGuide = true"
      @show-config="showConfig = true"
      @show-app-matching-config="loadAppMatchingConfig(); showAppMatchingConfig = true"
      @show-system-prompt-config="loadSystemPromptConfig(); showSystemPromptConfig = true"
      @device-renamed="handleDeviceRenamed"
    />

    <!-- Main Content: Chat & Workspace -->
    <div class="flex-1 flex flex-col min-w-0 bg-[#0f1115] relative z-10">
       <!-- Top Bar -->
       <TopBar
         :active-device-id="activeDeviceId"
         :active-task="activeTask"
         :active-task-id="activeTaskId"
         :sessions="sessions"
         :visible-sessions="visibleSessions"
         :background-tasks="backgroundTasks"
         :agent-status="agentStatus"
         :is-background-task="isBackgroundTask"
         :starting-task="startingTask"
         :stopping-task="stoppingTask"
         :locale="locale"
         @toggle-sidebar="sidebarOpen = !sidebarOpen"
         @select-task="selectTask"
         @create-task="openCreateTaskDialog"
         @edit-task="startEditTask"
         @delete-task="deleteTask"
         @session-scroll="handleSessionScroll"
         @show-permissions="openPermissions"
         @start-task="startBackgroundTask"
         @stop-task="stopTask"
         @change-locale="(lang: string) => locale = lang"
       />

       <!-- Chat Area -->
       <div class="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 custom-scrollbar scroll-smooth" ref="chatContainer" @scroll="handleChatScroll">
          <!-- Empty States -->
          <EmptyState
            v-if="devices.length === 0 && !loadingDevices"
            type="no-devices"
            @refresh="fetchDevices"
          />
          <EmptyState
            v-else-if="chatHistory.length === 0 && !isBackgroundTask"
            type="empty-chat"
            :device-id="activeDeviceId"
          />
          <EmptyState
            v-else-if="chatHistory.length === 0 && isBackgroundTask"
            type="empty-logs"
          />

          <!-- State 3: Active Chat History -->
          <div v-if="isLoadingMore" class="w-full flex justify-center py-2 text-gray-500">
               <el-icon class="is-loading"><Loading /></el-icon>
          </div>
          <div v-for="(msg, index) in filteredChatHistory" :key="msg.id || index" class="group flex w-full" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
             
             <!-- Agent Avatar -->
             <div v-if="msg.role === 'agent'" class="w-8 h-8 mr-3 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 shadow-lg shadow-indigo-500/20 text-white text-xs font-bold">
               AI
             </div>

             <!-- Message Content -->
             <div class="max-w-[85%] sm:max-w-[75%] flex flex-col" :class="msg.role === 'user' ? 'items-end' : 'items-start'">
                
                <!-- User Bubble -->
                <div v-if="msg.role === 'user'" class="bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-md text-sm leading-relaxed">
                   {{ msg.content }}
                </div>

                <!-- Agent Components -->
                <template v-else>
                  <!-- INFO Message -->
                  <InfoMessage
                    v-if="msg.isInfo && msg.content"
                    :message="msg"
                    :collapsed="messageCollapseState[index]?.info ?? true"
                    @toggle="messageCollapseState[index] = { ...messageCollapseState[index], info: !(messageCollapseState[index]?.info ?? true) }"
                    @preview-image="openImagePreview"
                  />

                  <!-- Screenshot Only -->
                  <ScreenshotMessage
                    v-else-if="msg.screenshot && !msg.thought && !msg.content && !msg.isInfo"
                    :screenshot="msg.screenshot"
                    @preview-image="openImagePreview"
                  />

                  <!-- Think/Reasoning -->
                  <ThinkMessage
                    v-if="msg.thought && !msg.action && !msg.isAnswer"
                    :message="msg"
                    :collapsed="messageCollapseState[index]?.thought ?? true"
                    @toggle="messageCollapseState[index] = { ...messageCollapseState[index], thought: !(messageCollapseState[index]?.thought ?? true) }"
                    @preview-image="openImagePreview"
                  />

                  <!-- Answer/Action -->
                  <AnswerMessage
                    v-if="msg.isAnswer || msg.action || (msg.content && !msg.isInfo && !msg.thought && !msg.isThinking)"
                    :message="msg"
                    @preview-image="openImagePreview"
                  />

                  <!-- Task Failed/Error -->
                  <ErrorMessage
                    v-if="msg.isFailed || msg.isError"
                    :message="msg"
                    @preview-image="openImagePreview"
                  />

                    <!-- Interaction: Confirmation/Choice -->
                  <ConfirmMessage
                    v-if="msg.type === 'confirm'"
                    :message="msg"
                    @action="handleCardAction"
                  />

                    <!-- Interaction: Input -->
                  <InputMessage
                    v-if="msg.type === 'input'"
                    :message="msg"
                    @input="handleCardInput"
                  />
                </template>
             </div>
          </div>
       </div>

       <!-- Input Area (Only for Chat Sessions) -->
       <ChatInput
         v-if="!isBackgroundTask"
         :input="input"
         :agent-status="agentStatus"
         :active-device-id="activeDeviceId"
         :available-apps="availableApps"
         :show-app-suggestions="showAppSuggestions"
         :app-suggestion-query="appSuggestionQuery"
         :attachments="attachments"
         :sending="sending"
         @update:input="input = $event"
         @send="sendMessage"
         @input-change="onInputChange"
         @select-app="selectApp"
         @trigger-app-select="triggerAppSelect"
         @trigger-upload="triggerUpload"
         @remove-attachment="removeAttachment"
       />
                 </div>
                 
    <!-- Right: Screen Mirror -->
    <ScreenMirror
      :active-device-id="activeDeviceId"
      :latest-screenshot="latestScreenshot"
      :is-landscape="isLandscape"
      :stream-quality="streamQuality"
      :fps="fps"
      :click-effects="clickEffects"
      :quality-options="qualityOptions"
      @update-quality="updateStreamQuality"
      @mouse-down="handleMouseDown"
      @mouse-move="handleMouseMove"
      @mouse-up="handleMouseUp"
      @go-home="goHome"
      @go-back="goBack"
      @go-recent="goRecent"
    />

    <!-- Permissions Dialog -->
    <PermissionsDialog
      v-model="showPermissions"
      :device-id="activeDeviceId"
      :api-base-url="apiBaseUrl"
    />
    <!-- Config Dialog -->
    <ConfigDialog
      v-model="showConfig"
      :config="config"
      :selected-provider="selectedProvider"
      :api-base-url="apiBaseUrl"
      @update:config="config = $event"
      @update:provider="selectedProvider = $event"
      @save="saveConfig"
    />
    
    <!-- App Matching Config Dialog -->
    <AppMatchingConfigDialog
      v-model="showAppMatchingConfig"
      :api-base-url="apiBaseUrl"
    />

    <!-- System Prompt Config Dialog -->
    <SystemPromptConfigDialog
      v-model="showSystemPromptConfig"
      :api-base-url="apiBaseUrl"
    />

    <!-- Create/Edit Task Dialog -->
    <TaskDialog
      v-model="showTaskDialog"
      :task="taskToEdit"
      @save="handleTaskSave"
    />
    
    <!-- Edit Task Name Dialog (using TaskDialog) -->
    <TaskDialog
      v-model="showEditTaskDialog"
      :task="taskToEdit"
      @save="handleTaskNameSave"
    />

    <!-- Device Connection Wizard -->
    <ConnectionGuideDialog
      v-model="showConnectionGuide"
      :wizard-step="wizardStep"
      :wizard-type="wizardType"
      :checking-usb="checkingUsb"
      :usb-status="usbStatus"
      :enabling-wifi="enablingWifi"
      :connecting-wifi="connectingWifi"
      :wifi-ip="wifiIp"
      :wifi-connected="false"
      :webrtc-url="webrtcUrl"
      :webrtc-connected="false"
      @next-step="handleWizardNext"
      @prev-step="handleWizardPrev"
      @check-usb="checkUsbConnection"
      @enable-wifi="enableWifiMode"
      @connect-wifi="connectWifi"
    />
    <!-- Image Preview Dialog -->
    <ImagePreviewDialog
      v-model="imagePreviewVisible"
      :images="sessionImages"
      :initial-index="imagePreviewIndex"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed, watch } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import QrcodeVue from 'qrcode.vue'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import { v4 as uuidv4 } from 'uuid' // Need UUID for frontend session generation

// Import dashboard components
import DeviceSidebar from '../components/dashboard/DeviceSidebar.vue'
import TopBar from '../components/dashboard/TopBar.vue'
import SystemPromptConfigDialog from '../components/dashboard/SystemPromptConfigDialog.vue'
import AppMatchingConfigDialog from '../components/dashboard/AppMatchingConfigDialog.vue'
import TaskDialog from '../components/dashboard/TaskDialog.vue'
import ConfigDialog from '../components/dashboard/ConfigDialog.vue'
import PermissionsDialog from '../components/dashboard/PermissionsDialog.vue'
import ImagePreviewDialog from '../components/dashboard/ImagePreviewDialog.vue'
import ConnectionGuideDialog from '../components/dashboard/ConnectionGuideDialog.vue'
import EmptyState from '../components/dashboard/EmptyState.vue'
import ChatInput from '../components/dashboard/ChatInput.vue'
import ScreenMirror from '../components/dashboard/ScreenMirror.vue'
import InfoMessage from '../components/dashboard/messages/InfoMessage.vue'
import ScreenshotMessage from '../components/dashboard/messages/ScreenshotMessage.vue'
import ThinkMessage from '../components/dashboard/messages/ThinkMessage.vue'
import AnswerMessage from '../components/dashboard/messages/AnswerMessage.vue'
import ErrorMessage from '../components/dashboard/messages/ErrorMessage.vue'
import ConfirmMessage from '../components/dashboard/messages/ConfirmMessage.vue'
import InputMessage from '../components/dashboard/messages/InputMessage.vue'
import { formatThink, formatAnswer } from '../utils/messageFormatter'
import { useWebSocket } from '../composables/useWebSocket'
import { useScreenStream } from '../composables/useScreenStream'
import { useMessageHandler } from '../composables/useMessageHandler'

// --- State ---
const { t, locale } = useI18n()
const sidebarOpen = ref(true)
const input = ref('')
const devices = ref<any[]>([])
const activeDeviceId = ref('')
const loadingDevices = ref(false)
const sending = ref(false)
// Status management: store status per task/session ID
const taskStatuses = ref<Record<string, string>>({}) // taskId/sessionId -> status
const startingTask = ref(false)
const stoppingTask = ref(false)
const chatHistory = ref<any[]>([])

// Task State (needed by composables)
const sessions = ref<any[]>([])
const backgroundTasks = ref<any[]>([])
const activeTaskId = ref<string | null>(null)

// Collapse state for messages (key: message index, value: { thought: boolean, screenshot: boolean, info?: boolean })
// true = collapsed, false = expanded
// Default: think and info messages are collapsed (true)
const messageCollapseState = ref<Record<number, { thought?: boolean, screenshot?: boolean, info?: boolean }>>({})

// Image preview state
const imagePreviewVisible = ref(false)
const imagePreviewUrl = ref('')
const imagePreviewIndex = ref(0)
const sessionImages = ref<string[]>([])


// Computed status for current active task/session
const agentStatus = computed(() => {
    if (!activeTaskId.value) return 'idle'
    return taskStatuses.value[activeTaskId.value] || 'idle'
})

// Initialize composables
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// Define computed properties needed by composables
const activeTask = computed(() => {
    return sessions.value.find(s => s.id === activeTaskId.value) || 
           backgroundTasks.value.find(t => t.id === activeTaskId.value)
})

const isBackgroundTask = computed(() => {
    return activeTask.value?.type === 'background'
})

// --- API Configuration (needed by composables) ---
const isSecure = window.location.protocol === 'https:'
const hostname = window.location.hostname
const port = 8000 
const backendRootUrl = `${isSecure ? 'https' : 'http'}://${hostname}:${port}`

// Use relative path to leverage Vite Proxy (avoids CORS/SSL issues)
const apiBaseUrl = '/api'
const wsProtocol = isSecure ? 'wss:' : 'ws:'
// Use Vite Proxy for WebSocket to share the same certificate trust as the frontend
const wsBaseUrl = `${wsProtocol}//${window.location.host}/api/agent/ws`

// Use composables
const { 
  latestScreenshot, 
  isLandscape, 
  fps, 
  isStreaming, 
  clickEffects,
  startStreamLoop: startStreamLoopComposable,
  forceRefreshFrame,
  handleMouseDown,
  handleMouseMove,
  handleMouseUp,
  goHome,
  goBack,
  goRecent
} = useScreenStream(apiBaseUrl, activeDeviceId)

const { 
  handleLog, 
  convertLogsToChat 
} = useMessageHandler(chatHistory, activeTaskId, isBackgroundTask, scrollToBottom)

const { 
  wsConnected, 
  wsError, 
  connectWS 
} = useWebSocket(
  wsBaseUrl,
  activeTaskId,
  chatHistory,
  taskStatuses,
  isBackgroundTask,
  (data: string) => {
    // onScreenshot
    frameCount++
    const now = Date.now()
    if (now - lastFpsTime >= 1000) {
      fps.value = Math.round(frameCount * 1000 / (now - lastFpsTime))
      frameCount = 0
      lastFpsTime = now
    }
    latestScreenshot.value = `data:image/jpeg;base64,${data}`
    const img = new Image()
    img.onload = () => { isLandscape.value = img.width > img.height }
    img.src = latestScreenshot.value
  },
  (taskId: string, status: string) => {
    // onStatusUpdate
    if (taskId === activeTaskId.value) {
      if (status !== 'running') {
        const lastMsg = chatHistory.value[chatHistory.value.length - 1]
        if (lastMsg && lastMsg.isThinking) lastMsg.isThinking = false
      }
      if (isBackgroundTask.value) {
        fetchData()
      }
    }
  },
  (data: any) => {
    // onInteraction
    const interactionMsg: any = {
      role: 'agent',
      type: data.data.type,
      title: data.data.title,
      content: data.data.content,
      options: data.data.options,
      placeholder: data.data.placeholder,
      sessionId: activeTaskId.value,
      submitted: false,
      inputValue: '',
      selectedValue: null
    }
    chatHistory.value.push(interactionMsg)
    db.addMessage(interactionMsg).then(id => interactionMsg.id = id)
    scrollToBottom()
  },
  handleLog,
  () => {
    // onOpen
    syncConfigToBackend()
  }
)
const showConfig = ref(false)
const showAppMatchingConfig = ref(false)
const appMatchingTab = ref('mappings')
const appMatchingConfig = ref<{
  system_app_mappings: Record<string, Array<{package: string, platform?: string}>>,
  llm_prompt_template: string
}>({
  system_app_mappings: {},
  llm_prompt_template: ''
})

const showSystemPromptConfig = ref(false)
const systemPromptTab = ref('cn')
const systemPromptConfig = ref({
  cn: '',
  en: ''
})

// Platform detection function
const detectPlatform = (packageName: string): string => {
  const pkg = packageName.toLowerCase()
  if (pkg.includes('huawei')) return '华为'
  if (pkg.includes('miui') || pkg.includes('xiaomi')) return '小米'
  if (pkg.includes('oppo') || pkg.includes('coloros')) return 'OPPO'
  if (pkg.includes('vivo') || pkg.includes('funtouch')) return 'vivo'
  if (pkg.includes('samsung')) return '三星'
  if (pkg.includes('tencent')) return '腾讯'
  if (pkg.includes('qihoo')) return '360'
  if (pkg.includes('baidu')) return '百度'
  if (pkg.includes('wandoujia')) return '豌豆荚'
  if (pkg.includes('yingyonghui')) return '应用汇'
  if (pkg.startsWith('com.android.') && !pkg.includes('huawei') && !pkg.includes('miui')) return 'Android'
  return '其他'
}

// Available platforms for selection
const availablePlatforms = ['华为', '小米', 'OPPO', 'vivo', '三星', 'Android', '腾讯', '360', '百度', '豌豆荚', '应用汇', '其他']
const showPermissions = ref(false)
const devicePermissions = ref({
    install_app: false,
    payment: false,
    wechat_reply: false,
    send_sms: false,
    make_call: false
})

const openPermissions = async () => {
    if (!activeDeviceId.value) return
    try {
        const res = await api.get(`/devices/${activeDeviceId.value}/permissions`)
        devicePermissions.value = res.data
        showPermissions.value = true
    } catch (e) {
        console.error('Failed to load permissions', e)
        // Set defaults if failed
        devicePermissions.value = {
            install_app: false,
            payment: false,
            wechat_reply: false,
            send_sms: false,
            make_call: false
        }
        showPermissions.value = true
    }
}

const savePermissions = async () => {
    if (!activeDeviceId.value) return
    try {
        await api.post(`/devices/${activeDeviceId.value}/permissions`, devicePermissions.value)
        showPermissions.value = false
        ElMessage.success(t('settings.saved'))
    } catch (e) {
        console.error('Failed to save permissions', e)
        ElMessage.error(t('error.failed_save_permissions'))
    }
}
const showConnectionGuide = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const selectedProvider = ref('vllm')
const streamQuality = ref('auto')
let frameCount = 0
let lastFpsTime = Date.now()

const qualityOptions = [
    { key: '1080p' },
    { key: '720p' },
    { key: '480p' },
    { key: '360p' },
    { key: 'auto' }
]

// Interaction state is now managed in useScreenStream composable

// --- Wizard State ---
const wizardStep = ref(1)
const wizardType = ref<'usb' | 'wifi' | 'webrtc' | ''>('')
const checkingUsb = ref(false)
const usbStatus = ref<'found' | 'not_found' | ''>('')
const enablingWifi = ref(false)
const connectingWifi = ref(false)
const wifiIp = ref('')
const webrtcUrl = ref('')

const deviceAliases = ref<Record<string, string>>({})
const editingDeviceId = ref('')
const editName = ref('')

// --- Task State ---
const visibleSessionCount = ref(5)
const visibleSessions = computed(() => sessions.value.slice(0, visibleSessionCount.value))

const handleSessionScroll = (e: Event) => {
    const target = e.target as HTMLElement
    // Check if scrolled near bottom (within 20px)
    if (target.scrollTop + target.clientHeight >= target.scrollHeight - 20) {
        if (visibleSessionCount.value < sessions.value.length) {
            visibleSessionCount.value += 5
        }
    }
}

const showTaskDialog = ref(false)
const hasMoreMessages = ref(true)
const isLoadingMore = ref(false)
const MESSAGES_PER_PAGE = 20
const newTask = ref({
    type: 'chat',
    name: '',
    role: '',
    details: ''
})

// Rename Task State
const showEditTaskDialog = ref(false)
const editTaskNameValue = ref('')
const taskToEdit = ref<any>(null)

// Task Log Refresh Interval
const taskLogRefreshInterval = ref<NodeJS.Timeout | null>(null)

// --- Input Enhancements ---
const availableApps = ref<Array<{name: string, package?: string, type: string}>>([])
const showAppSuggestions = ref(false)
const appSuggestionQuery = ref('')
const attachments = ref<any[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const inputRef = ref<any>(null)

// --- Config ---
const config = ref({
  baseUrl: 'http://localhost:8080/v1', // Model Server (vLLM)
  model: 'autoglm-phone-9b',
  apiKey: 'EMPTY'
})

const api = axios.create({ baseURL: apiBaseUrl }) // GUI Backend

// --- Computed ---
const filteredChatHistory = computed(() => chatHistory.value)

// --- Methods ---

const updateProviderConfig = (val: string) => {
  switch (val) {
    case 'vllm':
      config.value.baseUrl = 'http://localhost:8080/v1'
      config.value.model = 'autoglm-phone-9b'
      config.value.apiKey = 'EMPTY'
      break
    case 'ollama':
      config.value.baseUrl = 'http://localhost:11434/v1'
      config.value.model = 'autoglm-phone-9b'
      config.value.apiKey = 'ollama'
      break
    case 'bailian':
      config.value.baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
      config.value.model = 'qwen-plus' 
      config.value.apiKey = '' 
      break
    case 'gemini':
      config.value.baseUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/'
      config.value.model = 'gemini-1.5-flash'
      config.value.apiKey = ''
      break
    case 'claude':
      config.value.baseUrl = 'https://api.anthropic.com/v1'
      config.value.model = 'claude-3-haiku-20240307'
      config.value.apiKey = ''
      break
  }
}

const fetchDevices = async () => {
  loadingDevices.value = true
  try {
    const res = await api.get('/devices/')
    devices.value = res.data.map((d: any) => ({
        ...d,
        displayName: deviceAliases.value[d.id] || d.model,
        brand: d.brand || null  // Ensure brand is preserved
    }))
    console.log('Fetched devices:', devices.value)  // Debug log
    if (devices.value.length > 0) {
      const current = devices.value.find((d: any) => d.id === activeDeviceId.value)
      if (!current || current.status === 'offline') {
         activeDeviceId.value = ''
         const next = devices.value.find((d: any) => d.status !== 'offline')
         if (next) {
            selectDevice(next)
         }
      }
    } else {
       activeDeviceId.value = ''
    }
  } catch (err) {
    ElMessage.error(t('error.failed_connect_backend'))
  } finally {
    loadingDevices.value = false
  }
}

const selectDevice = async (device: any) => {
  if (device.status === 'offline') {
      ElMessage.warning(t('error.cannot_select_offline'))
      return
  }
  try {
    await api.post('/devices/select', { device_id: device.id, type: device.type })
    activeDeviceId.value = device.id
  } catch (err) {
    ElMessage.error(t('error.failed_select_device'))
  }
}

const deleteDevice = async (device: any) => {
    try {
        await api.delete(`/devices/${device.id}`)
        devices.value = devices.value.filter(d => d.id !== device.id)
        if (activeDeviceId.value === device.id) {
            activeDeviceId.value = ''
        }
        ElMessage.success(t('success.device_removed'))
    } catch (err) {
        ElMessage.error(t('error.failed_remove_device'))
    }
}

const startEdit = (device: any) => {
    editingDeviceId.value = device.id
    editName.value = device.displayName || device.model || device.id
}

const cancelEdit = () => {
    editingDeviceId.value = ''
    editName.value = ''
}

const saveDeviceName = async (device: any) => {
    if (editName.value.trim()) {
        const newName = editName.value.trim()
        await db.saveDeviceAlias(device.id, newName)
        deviceAliases.value[device.id] = newName
        const idx = devices.value.findIndex(d => d.id === device.id)
        if (idx !== -1) {
            devices.value[idx].displayName = newName
        }
    }
    cancelEdit()
}

// Handler for DeviceSidebar device-renamed event
const handleDeviceRenamed = async (device: any, newName: string) => {
    await db.saveDeviceAlias(device.id, newName)
    deviceAliases.value[device.id] = newName
    const idx = devices.value.findIndex(d => d.id === device.id)
    if (idx !== -1) {
        devices.value[idx].displayName = newName
    }
}

// Handler for TaskDialog save event
const handleTaskSave = async (data: any) => {
    if (data.name) {
        await createTask(data)
    }
}

// Handler for TaskDialog save event (edit mode)
const handleTaskNameSave = async (data: any) => {
    if (taskToEdit.value && data.name) {
        await saveTaskName()
    }
}

// --- Task Methods ---

const fetchData = async () => {
    if (!activeDeviceId.value) return
    
    // 1. Fetch Sessions from IndexedDB and filter by current device
    const allSessions = await db.getSessions()
    sessions.value = allSessions
        .filter((s: any) => s.deviceId === activeDeviceId.value)
        .sort((a: any, b: any) => (b.createdAt || 0) - (a.createdAt || 0))
    
    // 2. Fetch Tasks from Backend
    try {
        const res = await api.get(`/tasks/${activeDeviceId.value}`)
        backgroundTasks.value = res.data.filter((t: any) => t.type === 'background')
        // Update statuses for background tasks
        for (const task of backgroundTasks.value) {
            if (task.status) {
                taskStatuses.value[task.id] = task.status
            }
        }
    } catch (e) {
        console.error('Failed to fetch tasks', e)
        backgroundTasks.value = []
        // Optional: ElMessage.error(t('error.failed_fetch_tasks'))
    }

    // Auto-select logic
    if (!activeTaskId.value) {
        // Check for an existing empty session
        let emptySession = null;
        
        // Check most recent sessions first
        for (const session of sessions.value) {
            const msgs = await db.getMessages(session.id);
            if (msgs.length === 0) {
                emptySession = session;
                break; 
            }
        }

        if (emptySession) {
            selectTask(emptySession);
        } else {
            // Create a new empty session
            await createDefaultSession();
        }
    }
}

const createDefaultSession = async () => {
    const id = uuidv4()
    const session = {
        id,
        name: `${t('debug.session_prefix')}${sessions.value.length + 1}`,
        type: 'chat',
        deviceId: activeDeviceId.value,
        createdAt: Date.now()
    }
    await db.addSession(session)
    sessions.value.unshift(session)
    selectTask(session)
}

const openCreateTaskDialog = (type: 'chat' | 'background' = 'chat') => {
    taskToEdit.value = null
    newTask.value = {
        type,
        name: type === 'chat' ? `${t('debug.session_prefix')}${sessions.value.length + 1}` : t('debug.new_task'),
        role: '',
        details: ''
    }
    showTaskDialog.value = true
}

const createTask = async (taskData?: any) => {
    const data = taskData || newTask.value
    if (!activeDeviceId.value) return

    if (data.type === 'chat') {
        // Create in IndexedDB
        const id = uuidv4()
        const session = {
            id,
            name: data.name || `${t('debug.session_prefix')}${sessions.value.length + 1}`,
            type: 'chat',
            deviceId: activeDeviceId.value,
            createdAt: Date.now()
        }
        await db.addSession(session)
        sessions.value.unshift(session)
        showTaskDialog.value = false
        selectTask(session)
    } else {
        // Create Background Task on Backend
        try {
            const res = await api.post('/tasks/', {
                device_id: activeDeviceId.value,
                ...data
            })
            showTaskDialog.value = false
            await fetchData() // Refresh lists
            selectTask(res.data.task)
            // Don't start automatically - let user start it manually
        } catch (e: any) {
            ElMessage.error(e.response?.data?.detail || t('error.failed_create_task'))
        }
    }
}

const refreshTaskLogs = async () => {
    if (!activeTaskId.value || !isBackgroundTask.value) return
    try {
        const res = await api.get(`/tasks/detail/${activeTaskId.value}`)
        const details = res.data.task
        chatHistory.value = convertLogsToChat(details.logs)
        if (details.details) {
            // Check if details already in history
            const hasDetails = chatHistory.value.some((msg: any) => msg.role === 'user' && msg.content === details.details)
            if (!hasDetails) {
                chatHistory.value.unshift({ role: 'user', content: details.details })
            }
        }
        scrollToBottom()
    } catch (e) {
        console.error('Failed to refresh task logs', e)
    }
}

const selectTask = async (task: any) => {
    // Clear previous interval if exists
    if (taskLogRefreshInterval.value) {
        clearInterval(taskLogRefreshInterval.value)
        taskLogRefreshInterval.value = null
    }
    
    activeTaskId.value = task.id
    chatHistory.value = []
    hasMoreMessages.value = true
    
    // Initialize status if not exists
    if (!taskStatuses.value[task.id]) {
        if (task.type === 'background' && task.status) {
            taskStatuses.value[task.id] = task.status
        } else {
            taskStatuses.value[task.id] = 'idle'
        }
    }
    
    if (task.type === 'chat') {
        // Load from DB (Paged)
        await loadMessages(task.id)
    } else {
        // Load from Backend
        await refreshTaskLogs()
        // For background tasks, set up periodic refresh
        taskLogRefreshInterval.value = setInterval(() => {
            if (isBackgroundTask.value && activeTaskId.value === task.id) {
                refreshTaskLogs()
            }
        }, 5000) // Refresh every 5 seconds
    }
    scrollToBottom()
}

const loadMessages = async (sessionId: string, beforeId?: number) => {
    try {
        const msgs = await db.getMessages(sessionId, MESSAGES_PER_PAGE, beforeId)
        if (msgs.length < MESSAGES_PER_PAGE) {
            hasMoreMessages.value = false
        }
        
        if (beforeId) {
            chatHistory.value = [...msgs, ...chatHistory.value]
        } else {
            chatHistory.value = msgs
        }
    } catch (e) {
        console.error('Failed to load messages', e)
        // ElMessage.error(t('error.failed_load_messages'))
    }
}

const handleChatScroll = async (e: Event) => {
    const target = e.target as HTMLElement
    if (target.scrollTop === 0 && hasMoreMessages.value && !isLoadingMore.value && activeTaskId.value) {
        // Load more
        isLoadingMore.value = true
        // Capture the ID of the top message before loading
        const oldestId = chatHistory.value[0]?.id
        const oldScrollHeight = target.scrollHeight
        
        if (oldestId) {
            await loadMessages(activeTaskId.value, oldestId)
            
            // Wait for DOM update
            nextTick(() => {
                // Adjust scroll position to maintain stability
                const newScrollHeight = target.scrollHeight
                const diff = newScrollHeight - oldScrollHeight
                if (diff > 0) {
                    target.scrollTop = diff
                }
            })
        }
        isLoadingMore.value = false
    }
}

// convertLogsToChat is now provided by useMessageHandler composable

const deleteTask = async (task: any) => {
    if (task.type === 'chat') {
        await db.deleteSession(task.id)
        sessions.value = sessions.value.filter(s => s.id !== task.id)
        // Remove status
        delete taskStatuses.value[task.id]
        if (activeTaskId.value === task.id) {
            activeTaskId.value = null
            chatHistory.value = []
        }
        ElMessage.success(t('success.session_deleted'))
    } else {
        try {
            await api.delete(`/tasks/${task.id}`)
            backgroundTasks.value = backgroundTasks.value.filter(t => t.id !== task.id)
            // Remove status
            delete taskStatuses.value[task.id]
            if (activeTaskId.value === task.id) {
                activeTaskId.value = null
                chatHistory.value = []
            }
            ElMessage.success(t('success.task_deleted'))
        } catch (e) {
            ElMessage.error(t('error.failed_delete_task'))
        }
    }
}

// --- Renaming ---
const startEditTask = (task: any) => {
    taskToEdit.value = task
    editTaskNameValue.value = task.name
    showEditTaskDialog.value = true
}

const saveTaskName = async () => {
    if (!taskToEdit.value || !editTaskNameValue.value.trim()) return
    const newName = editTaskNameValue.value.trim()
    
    if (taskToEdit.value.type === 'chat') {
        await db.updateSession(taskToEdit.value.id, { name: newName })
        taskToEdit.value.name = newName // Update local ref
    } else {
        try {
            await api.put(`/tasks/${taskToEdit.value.id}`, { name: newName })
            taskToEdit.value.name = newName
        } catch (e) {
            ElMessage.error(t('error.failed_rename_task'))
        }
    }
    showEditTaskDialog.value = false
    ElMessage.success(t('success.renamed'))
}

// --- Input Enhancement Methods ---

const fetchDeviceApps = async (deviceId: string) => {
    try {
        const res = await api.get(`/devices/${deviceId}/apps`)
        // Filter out apps that are just in the static list but not actually installed
        // The backend returns {name, package, type}
        // If type is 'supported' it means it's in APP_PACKAGES and installed (or system)
        // If type is 'other' it means it's a user installed 3rd party app
        
        // We want ONLY installed apps. The backend logic for get_device_apps already does this:
        // It iterates user_packages and checks if they are in pkg_to_name.
        // It also adds supported system apps that are installed.
        // So the list returned by API *should* already be only installed apps.
        
        // However, if the user sees too many apps, maybe we should filter further?
        // But the requirement says "don't show built-in apps.py list", implying 
        // we shouldn't show apps that are NOT on the device.
        
        // The current implementation of fetchDeviceApps replaces availableApps.value completely.
        // But if fetchStaticApps was called before, availableApps might have static data.
        
        availableApps.value = res.data.apps
    } catch (e) {
        console.error('Failed to fetch device apps', e)
        // Do NOT fallback to static apps if device fetch fails, as requested
        availableApps.value = [] 
        // Optional: ElMessage.error(t('error.failed_fetch_apps'))
    }
}

const onInputChange = (val: string) => {
    const lastAt = val.lastIndexOf('@')
    if (lastAt !== -1) {
        const query = val.slice(lastAt + 1)
        if (!query.includes(' ')) {
             // Fetch apps dynamically if not already fetched for this device
             // AND ensure we are not using the static list (which might have been loaded initially)
             if (activeDeviceId.value) {
                 // Always fetch to ensure freshness and correctness, or check if we have "real" data
                 // For now, let's just fetch if empty or if we suspect it's stale/static
                 if (availableApps.value.length === 0 || availableApps.value.some(a => a.type === 'static')) {
                     fetchDeviceApps(activeDeviceId.value)
                 }
             }
             showAppSuggestions.value = true
             appSuggestionQuery.value = query.toLowerCase()
             return
        }
    }
    showAppSuggestions.value = false
}

const selectApp = (appName: string) => {
    const lastAt = input.value.lastIndexOf('@')
    if (lastAt !== -1) {
        input.value = input.value.slice(0, lastAt) + appName + ' '
    }
    showAppSuggestions.value = false
    nextTick(() => {
        if (inputRef.value) inputRef.value.focus()
    })
}

const triggerAppSelect = () => {
    if (showAppSuggestions.value) {
        showAppSuggestions.value = false
        return
    }
    const val = input.value
    if (!val.trim().endsWith('@')) {
        input.value += (val && !val.endsWith(' ') ? ' ' : '') + '@'
    }
    nextTick(() => {
        if (inputRef.value) {
            inputRef.value.focus()
        }
        onInputChange(input.value)
    })
}

const triggerUpload = (type: string) => {
    if (fileInput.value) {
        fileInput.value.accept = type === 'image' ? 'image/*' : 
                                 type === 'video' ? 'video/*' :
                                 type === 'audio' ? 'audio/*' : '*/*'
        fileInput.value.click()
    }
}

const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement
    if (target.files && target.files.length > 0) {
        const file = target.files[0]
        attachments.value.push({
            name: file.name,
            type: file.type.split('/')[0],
            file: file,
            url: URL.createObjectURL(file)
        })
    }
    target.value = '' 
}

const removeAttachment = (index: number) => {
    attachments.value.splice(index, 1)
}

const handleCardAction = async (msg: any, option: any) => {
    msg.submitted = true
    msg.selectedValue = option.label
    if (msg.id) {
        await db.updateMessage(msg.id, { submitted: true, selectedValue: option.label })
    }
    
    // Send Interaction Response to Backend
    if (activeTaskId.value) {
        try {
            await api.post(`/tasks/${activeTaskId.value}/interaction`, {
                response: option.value
            })
        } catch (e) {
            console.error('Failed to send interaction response', e)
            ElMessage.error(t('error.failed_send_interaction'))
        }
    }
}

const handleCardInput = async (msg: any) => {
    if (!msg.inputValue) return
    msg.submitted = true
    if (msg.id) {
        await db.updateMessage(msg.id, { submitted: true, inputValue: msg.inputValue })
    }
    
    // Send Interaction Response to Backend
    if (activeTaskId.value) {
        try {
            await api.post(`/tasks/${activeTaskId.value}/interaction`, {
                response: msg.inputValue
            })
        } catch (e) {
            console.error('Failed to send interaction response', e)
            ElMessage.error(t('error.failed_send_interaction'))
        }
    }
}

const sendMessage = async () => {
  if (!input.value || !activeDeviceId.value || !activeTaskId.value) return
  
  // Prevent sending messages for background tasks
  if (isBackgroundTask.value) {
      ElMessage.warning(t('task.cannot_send_message_to_background_task'))
      return
  }

  // Debug/Test Commands for UI Cards
  if (input.value === '/debug-confirm') {
      input.value = ''
      const msg: any = {
          role: 'agent',
          type: 'confirm',
          title: t('debug.permission_request'),
          content: t('debug.install_app_request'),
          options: [
              { label: t('common.deny'), value: 'No', type: 'danger' },
              { label: t('common.allow'), value: 'Yes', type: 'success' }
          ],
          sessionId: activeTaskId.value,
          submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
  }
  if (input.value === '/debug-input') {
      input.value = ''
      const msg: any = {
          role: 'agent',
          type: 'input',
          title: t('debug.sms_verification'),
          content: t('debug.enter_verification_code'),
          placeholder: '123456',
          sessionId: activeTaskId.value,
          submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
  }
  
  const prompt = input.value
  input.value = ''
  sending.value = true
  
  // 1. Auto-rename session (IndexedDB)
  const currentTask = activeTask.value
  if (currentTask && currentTask.type === 'chat' && currentTask.name.startsWith(t('debug.session_prefix'))) {
      const newName = prompt.length > 20 ? prompt.substring(0, 20) + '...' : prompt
      await db.updateSession(currentTask.id, { name: newName })
      currentTask.name = newName
  }

  // 2. Save User Message to IndexedDB (linked to sessionId)
  const userMsg = { role: 'user', content: prompt, sessionId: activeTaskId.value }
  const id1 = await db.addMessage(userMsg)
  chatHistory.value.push({ ...userMsg, id: id1 })
  
  // 3. Add placeholder for agent
  const agentMsg = { 
      role: 'agent', 
      thought: '', 
      isThinking: true,
      sessionId: activeTaskId.value 
  }
  const id2 = await db.addMessage(agentMsg)
  chatHistory.value.push({ ...agentMsg, id: id2 })
  
  scrollToBottom()

  // 4. Trigger Backend
  try {
    // Ensure Backend Task Exists (Sync)
    try {
        await api.get(`/tasks/detail/${activeTaskId.value}`)
        // Task exists, update it with latest prompt/name
        await api.put(`/tasks/${activeTaskId.value}`, {
            name: currentTask?.name || t('debug.chat_sync'),
            details: prompt
        })
    } catch (e) {
        // Not found, create it (ephemeral or persistent depending on backend logic)
        await api.post('/tasks/', {
            id: activeTaskId.value,
            device_id: activeDeviceId.value,
            type: 'chat',
            name: currentTask?.name || t('debug.chat_sync'),
            details: prompt
        })
    }

    // Ensure apps are fetched so we can pass them to the agent
    if (availableApps.value.length === 0 && activeDeviceId.value) {
        await fetchDeviceApps(activeDeviceId.value)
    }

    // Start Execution
    await api.post(`/tasks/${activeTaskId.value}/start`, { 
        prompt,
        installed_apps: availableApps.value.map(a => ({ name: a.name, package: a.package }))
    })
    if (activeTaskId.value) {
        taskStatuses.value[activeTaskId.value] = 'running'
    }
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || t('error.failed_start_task')
    ElMessage.error(errorMsg)
    chatHistory.value.pop() 
    const errM = { role: 'agent', content: `${t('common.error_prefix')}${errorMsg}`, sessionId: activeTaskId.value }
    chatHistory.value.push(errM)
    db.addMessage(errM)
  } finally {
    sending.value = false
  }
}

const startBackgroundTask = async () => {
  if (!activeTaskId.value || !activeDeviceId.value) return
  
  startingTask.value = true
  try {
    // Ensure apps are fetched so we can pass them to the agent
    if (availableApps.value.length === 0 && activeDeviceId.value) {
        await fetchDeviceApps(activeDeviceId.value)
    }
    
    await api.post(`/tasks/${activeTaskId.value}/start`, {
        installed_apps: availableApps.value.map(a => ({ name: a.name, package: a.package }))
    })
    if (activeTaskId.value) {
        taskStatuses.value[activeTaskId.value] = 'running'
    }
    await fetchData() // Refresh task status
    ElMessage.success(t('success.task_started'))
  } catch (err: any) {
    const errorMsg = err.response?.data?.detail || t('error.failed_start_task')
    ElMessage.error(errorMsg)
  } finally {
    startingTask.value = false
  }
}

const stopTask = async () => {
  stoppingTask.value = true
  try {
  if (activeTaskId.value) {
      await api.post(`/tasks/${activeTaskId.value}/stop`)
        taskStatuses.value[activeTaskId.value] = 'idle'
  } else {
      await api.post('/agent/stop')
        // Clear all statuses if stopping without active task
        taskStatuses.value = {}
  }
    if (isBackgroundTask.value) {
        await fetchData() // Refresh task status
    }
  ElMessage.warning(t('success.task_stopped'))
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || t('error.failed_stop_task'))
  } finally {
    stoppingTask.value = false
  }
}

// --- Wizard Methods ---
const checkUsbConnection = async () => {
  checkingUsb.value = true
  usbStatus.value = ''
  try {
    await fetchDevices()
    if (devices.value.length > 0) {
       usbStatus.value = 'found'
       setTimeout(() => wizardStep.value = 3, 1000)
    } else {
       usbStatus.value = 'not_found'
    }
  } catch (e) {
    usbStatus.value = 'not_found'
  } finally {
    checkingUsb.value = false
  }
}

const enableWifiMode = async () => {
  enablingWifi.value = true
  try {
    const res = await api.post('/devices/wifi/enable')
    ElMessage.success(t('success.wifi_enabled'))
    if (res.data.ip) {
      wifiIp.value = res.data.ip
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || t('error.failed_enable_wifi'))
  } finally {
    enablingWifi.value = false
  }
}

const connectWifi = async () => {
  connectingWifi.value = true
  try {
    await api.post('/devices/connect', { address: wifiIp.value, type: 'adb' })
    ElMessage.success(t('success.connected_wifi'))
    wizardStep.value = 3
    fetchDevices()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || t('error.connection_failed'))
  } finally {
    connectingWifi.value = false
  }
}

const connectWebRTC = async () => {
  try {
     const res = await api.post('/devices/webrtc/init')
     webrtcUrl.value = res.data.url
     const poll = setInterval(async () => {
        if (wizardStep.value !== 2 || wizardType.value !== 'webrtc') {
           clearInterval(poll)
           return
        }
         try {
             const res = await api.get('/devices/')
             devices.value = res.data
             const found = devices.value.find((d: any) => d.type === 'webrtc' && d.status !== 'offline')
             if (found) {
                ElMessage.success(t('success.webrtc_connected'))
                wizardStep.value = 3
                clearInterval(poll)
             }
         } catch (e) { }
     }, 2000)
   } catch (err: any) {
     console.error(err)
     ElMessage.error(t('error.failed_init_webrtc'))
   }
}

watch([wizardStep, wizardType], ([newStep, newType]) => {
   if (newStep === 2 && newType === 'webrtc') {
      connectWebRTC()
   }
})

// Wizard step handlers
const handleWizardNext = () => {
    if (wizardStep.value < 3) {
        wizardStep.value++
    }
}

const handleWizardPrev = () => {
    if (wizardStep.value > 1) {
        wizardStep.value--
    } else {
        // Reset wizard when going back from step 1
        wizardStep.value = 1
        wizardType.value = ''
        usbStatus.value = ''
        wifiIp.value = ''
        webrtcUrl.value = ''
        showConnectionGuide.value = false
    }
}

const finishWizard = () => {
  showConnectionGuide.value = false
  wizardStep.value = 1
  wizardType.value = ''
  usbStatus.value = ''
  wifiIp.value = ''
  webrtcUrl.value = ''
}

const syncConfigToBackend = async () => {
    try {
        await api.post('/agent/config', {
            base_url: config.value.baseUrl,
            model: config.value.model,
            api_key: config.value.apiKey
        })
        console.log("Config synced to backend")
    } catch (e) {
        console.error("Failed to sync config", e)
    }
}

const saveConfig = async () => {
  const configToSave = { 
    ...config.value, 
    selectedProvider: selectedProvider.value 
  }
  await db.saveConfig(configToSave)
  await syncConfigToBackend()
  ElMessage.success(t('success.config_saved'))
  showConfig.value = false
}

const loadAppMatchingConfig = async () => {
  try {
    const res = await api.get('/agent/app-matching-config')
    const mappings = res.data.system_app_mappings || {}
    
    // Convert old format (string[]) to new format (Array<{package, platform}>)
    const convertedMappings: Record<string, Array<{package: string, platform?: string}>> = {}
    for (const [keyword, packages] of Object.entries(mappings)) {
      if (Array.isArray(packages)) {
        convertedMappings[keyword] = packages.map((pkg: any) => {
          if (typeof pkg === 'string') {
            return { package: pkg, platform: detectPlatform(pkg) }
          }
          return { package: pkg.package || '', platform: pkg.platform || detectPlatform(pkg.package || '') }
        })
      }
    }
    
    appMatchingConfig.value = {
      system_app_mappings: convertedMappings,
      llm_prompt_template: res.data.llm_prompt_template || ''
        }
    } catch (e) {
    console.error('Failed to load app matching config', e)
    ElMessage.error(t('error.failed_load_config'))
  }
}

const saveAppMatchingConfig = async () => {
  try {
    // Convert to format expected by backend (can be simplified or keep full format)
    const configToSave = {
      system_app_mappings: appMatchingConfig.value.system_app_mappings,
      llm_prompt_template: appMatchingConfig.value.llm_prompt_template
    }
    await api.post('/agent/app-matching-config', configToSave)
    ElMessage.success(t('success.config_saved'))
    showAppMatchingConfig.value = false
  } catch (e) {
    console.error('Failed to save app matching config', e)
    ElMessage.error(t('error.failed_save_config'))
  }
}

const resetAppMatchingConfig = async () => {
  try {
    const res = await api.get('/agent/app-matching-config')
    // Reset to defaults (would need to get from backend or use hardcoded defaults)
    ElMessage.info(t('settings.reset_not_implemented'))
  } catch (e) {
    console.error('Failed to reset config', e)
  }
}

const addMapping = () => {
  const newKey = `新关键词_${Object.keys(appMatchingConfig.value.system_app_mappings).length + 1}`
  appMatchingConfig.value.system_app_mappings[newKey] = []
}

const removeMapping = (keyword: string) => {
  delete appMatchingConfig.value.system_app_mappings[keyword]
}

const updateMappingKey = (oldIndex: number, oldKey: string, newKey: string) => {
  if (newKey && newKey !== oldKey) {
    const packages = appMatchingConfig.value.system_app_mappings[oldKey]
    delete appMatchingConfig.value.system_app_mappings[oldKey]
    appMatchingConfig.value.system_app_mappings[newKey] = packages
  }
}

const addPackage = (keyword: string) => {
  if (!appMatchingConfig.value.system_app_mappings[keyword]) {
    appMatchingConfig.value.system_app_mappings[keyword] = []
  }
  appMatchingConfig.value.system_app_mappings[keyword].push({ package: '', platform: '' })
}

const removePackage = (keyword: string, index: number) => {
  appMatchingConfig.value.system_app_mappings[keyword].splice(index, 1)
}

const updatePackagePlatform = (keyword: string, index: number) => {
  const pkgItem = appMatchingConfig.value.system_app_mappings[keyword][index]
  if (pkgItem.package && !pkgItem.platform) {
    pkgItem.platform = detectPlatform(pkgItem.package)
  }
}

const loadSystemPromptConfig = async () => {
  try {
    const resCn = await api.get('/agent/system-prompt?lang=cn')
    const resEn = await api.get('/agent/system-prompt?lang=en')
    systemPromptConfig.value = {
      cn: resCn.data.prompt || '',
      en: resEn.data.prompt || ''
    }
  } catch (e) {
    console.error('Failed to load system prompt config', e)
    ElMessage.error(t('error.failed_load_config'))
  }
}

const saveSystemPromptConfig = async () => {
  try {
    await api.post('/agent/system-prompt', {
      prompt: systemPromptConfig.value.cn,
      lang: 'cn'
    })
    await api.post('/agent/system-prompt', {
      prompt: systemPromptConfig.value.en,
      lang: 'en'
    })
    ElMessage.success(t('success.config_saved'))
    showSystemPromptConfig.value = false
  } catch (e) {
    console.error('Failed to save system prompt config', e)
    ElMessage.error(t('error.failed_save_config'))
  }
}

const resetSystemPromptConfig = async () => {
  try {
    await api.post('/agent/system-prompt/reset?lang=cn')
    await api.post('/agent/system-prompt/reset?lang=en')
    await loadSystemPromptConfig()
    ElMessage.success(t('success.config_reset'))
  } catch (e) {
    console.error('Failed to reset system prompt config', e)
    ElMessage.error(t('error.failed_reset_config'))
  }
}

const updateStreamQuality = async (key: string, silent = false) => {
    streamQuality.value = key
    let q = 60
    let w = 480
    
    switch (key) {
        case '1080p': q = 80; w = 1080; break
        case '720p': q = 70; w = 720; break
        case '480p': q = 60; w = 480; break
        case '360p': q = 50; w = 360; break
        case 'auto': q = 50; w = 360; break // Auto prioritizes speed, similar to 360p
    }
    
    try {
        await api.post('/control/stream/settings', { quality: q, max_width: w })
        if (!silent) {
            const label = t('mirror.quality_' + key)
            ElMessage.success(t('success.quality_set', { quality: label }))
        }
    } catch (e) {
        // ElMessage.error('Failed to update stream settings')
    }
}

// Screen interaction, WebSocket, and message handling functions are now provided by composables

onMounted(async () => {
  const savedConfig = await db.getConfig()
  if (savedConfig) {
    config.value = { ...config.value, ...savedConfig }
    if (savedConfig.selectedProvider) selectedProvider.value = savedConfig.selectedProvider
    syncConfigToBackend()
  }

  // Initial Data Fetch happens in watcher after device load, or here if we want global sessions?
  // We need to fetch devices first.
  deviceAliases.value = await db.getDeviceAliases()
  fetchDevices()
  connectWS()
  
  // Init default stream settings
  // Use nextTick to ensure the method is available if order matters, though hoisting should handle it
  // But just in case of any weird scoping issue with <script setup>
  await nextTick()
  updateStreamQuality('auto', true)
  if (activeDeviceId.value) {
      startStreamLoopComposable()
  }
})

watch(activeDeviceId, (newId) => {
    if (newId) {
        visibleSessionCount.value = 5
        activeTaskId.value = null 
        chatHistory.value = []
        fetchDeviceApps(newId)
        fetchData() // Replaces fetchTasks
        startStreamLoopComposable() // Start polling
    } else {
        isStreaming.value = false // Stop polling
        if (taskLogRefreshInterval.value) {
            clearInterval(taskLogRefreshInterval.value)
            taskLogRefreshInterval.value = null
        }
        sessions.value = []
        backgroundTasks.value = []
        activeTaskId.value = null
        chatHistory.value = []
        availableApps.value = []
        // Clear statuses when device changes
        taskStatuses.value = {}
    }
})

// Clean up interval when task changes
watch(activeTaskId, (newId, oldId) => {
    if (oldId && taskLogRefreshInterval.value) {
        clearInterval(taskLogRefreshInterval.value)
        taskLogRefreshInterval.value = null
    }
})

// Image preview functions
const openImagePreview = (imageUrl: string) => {
    // Collect all images from current session
    const images: string[] = []
    chatHistory.value.forEach((msg: any) => {
        if (msg.screenshot) {
            images.push(msg.screenshot)
        }
    })
    
    if (images.length === 0) {
        return
    }
    
    sessionImages.value = images
    const index = images.indexOf(imageUrl)
    imagePreviewIndex.value = index >= 0 ? index : 0
    imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    imagePreviewVisible.value = true
}

const showPreviousImage = () => {
    if (imagePreviewIndex.value > 0) {
        imagePreviewIndex.value--
        imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    }
}

const showNextImage = () => {
    if (imagePreviewIndex.value < sessionImages.value.length - 1) {
        imagePreviewIndex.value++
        imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    }
}

// Keyboard navigation for image preview
const handleImagePreviewKeydown = (e: KeyboardEvent) => {
    if (!imagePreviewVisible.value) return
    
    if (e.key === 'ArrowLeft') {
        e.preventDefault()
        showPreviousImage()
    } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        showNextImage()
    } else if (e.key === 'Escape') {
        e.preventDefault()
        imagePreviewVisible.value = false
    }
}

// Add keyboard event listener
onMounted(() => {
    window.addEventListener('keydown', handleImagePreviewKeydown)
})

// Remove keyboard event listener
onUnmounted(() => {
    window.removeEventListener('keydown', handleImagePreviewKeydown)
})
</script>

<style scoped>
/* Custom Styles for deep selectors */
:deep(.el-input__wrapper) {
  background-color: #161b22;
  box-shadow: none;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 12px 16px;
}
:deep(.el-input__wrapper.is-focus) {
  border-color: #58a6ff;
  box-shadow: 0 0 0 1px #58a6ff;
}
:deep(.el-input__inner) {
  color: #e6edf3;
}

/* Custom Dialog */
:deep(.custom-dialog) {
  background-color: #161b22;
  border: 1px solid #30363d;
  border-radius: 16px;
}
:deep(.dark-dialog) {
    background-color: #ffffff;
    border-radius: 12px;
}
:deep(.permissions-dialog .el-dialog__title) {
    color: #000000 !important;
    font-weight: 600;
}
:deep(.el-dialog__title) { color: #e6edf3; }
:deep(.el-form-item__label) { color: #8b949e; }
:deep(.el-dialog__headerbtn .el-dialog__close) { color: #8b949e; }

/* Image Preview Dialog */
:deep(.image-preview-dialog .el-dialog__body) {
  padding: 0;
}

/* Transitions */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.3s ease-out;
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(-20px);
  opacity: 0;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #58a6ff;
}
</style>
