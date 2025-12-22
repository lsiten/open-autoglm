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
      :api-connected="apiConnected"
      :ws-error="wsError"
      :ws-base-url="wsBaseUrl"
      :backend-root-url="backendRootUrl"
      @refresh-devices="fetchDevices"
      @select-device="selectDevice"
      @delete-device="deleteDevice"
      @show-connection-guide="showConnectionGuide = true"
      @show-config="showConfig = true"
      @show-app-matching-config="loadAppMatchingConfig(); showAppMatchingConfig = true"
      @show-system-prompt-config="(deviceId) => { systemPromptDeviceId = deviceId; showSystemPromptConfig = true }"
      @show-device-system-prompt-config="(deviceId) => { systemPromptDeviceId = deviceId; showSystemPromptConfig = true }"
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
         :is-recording="isRecording"
         :starting-recording="startingRecording"
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
         @toggle-recording="handleToggleRecording"
         @show-recordings="showRecordingList = true"
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
                    v-if="(msg.thought || msg.isThinking) && !msg.action && !msg.isAnswer"
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
                    @action="(data) => handleCardAction(data.msg, data.option)"
                  />

                    <!-- Interaction: Input -->
                  <InputMessage
                    v-if="msg.type === 'input'"
                    :message="msg"
                    @input="handleCardInput"
                  />

                    <!-- Interaction: Click Annotation -->
                  <ClickAnnotationMessage
                    v-if="msg.type === 'click_annotation'"
                    :message="msg"
                    :latest-screenshot="latestScreenshot"
                    @annotation="handleCardAnnotation"
                  />

                    <!-- Status Message: Long-running task progress -->
                  <StatusMessage
                    v-if="msg.type === 'status' && ((msg.statusType && msg.statusType.trim()) && ((msg.status && msg.status.trim()) || (msg.message && msg.message.trim()) || msg.progress !== undefined))"
                    :message="msg"
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
      :use-mjpeg-stream="useMjpegStream"
      :mjpeg-stream-url="mjpegStreamUrl"
      @update-quality="updateStreamQuality"
      @mouse-down="handleMouseDown"
      @mouse-move="handleMouseMove"
      @mouse-up="handleMouseUp"
      @go-home="goHome"
      @go-back="goBack"
      @go-recent="goRecent"
      @mjpeg-error="useMjpegStream = false"
      @landscape-update="isLandscape = $event"
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
      :device-id="systemPromptDeviceId"
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

    <!-- Recording Dialog -->
    <RecordingDialog
      v-model="showRecordingDialog"
      :action-count="recordingActionCount"
      :recording-id="recordingId"
      :on-preview="previewRecording"
      :on-debug="debugRecording"
      :on-reset="resetRecordingState"
      :on-execute-action="executeSingleAction"
      :on-replace-action="replaceAction"
      @save="handleSaveRecording"
    />

    <!-- Recording List Dialog -->
    <RecordingListDialog
      v-model="showRecordingList"
      :recordings="recordings"
      :loading="recordingLoading"
      @execute="handleExecuteRecording"
      @delete="handleDeleteRecording"
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
import ClickAnnotationMessage from '../components/dashboard/messages/ClickAnnotationMessage.vue'
import StatusMessage from '../components/dashboard/messages/StatusMessage.vue'
import RecordingDialog from '../components/dashboard/RecordingDialog.vue'
import RecordingListDialog from '../components/dashboard/RecordingListDialog.vue'
import { formatThink, formatAnswer } from '../utils/messageFormatter'
import { detectPlatform, availablePlatforms } from '../utils/platformDetector'
import { useWebSocket } from '../composables/useWebSocket'
import { useScreenStream } from '../composables/useScreenStream'
import { useMessageHandler } from '../composables/useMessageHandler'
import { useDeviceManagement } from '../composables/useDeviceManagement'
import { useImagePreview } from '../composables/useImagePreview'
import { useTaskManagement } from '../composables/useTaskManagement'
import { useInputEnhancement } from '../composables/useInputEnhancement'
import { useConnectionWizard } from '../composables/useConnectionWizard'
import { useConfigManagement } from '../composables/useConfigManagement'
import { usePermissions } from '../composables/usePermissions'
import { useInteraction } from '../composables/useInteraction'
import { useModelConfig } from '../composables/useModelConfig'
import { useStreamQuality } from '../composables/useStreamQuality'
import { useDeviceEdit } from '../composables/useDeviceEdit'
import { useTaskEdit } from '../composables/useTaskEdit'
import { useAppMatchingUI } from '../composables/useAppMatchingUI'
import { useRecording } from '../composables/useRecording'

// --- State ---
const { t, locale } = useI18n()
const sidebarOpen = ref(true)
const input = ref('')
const activeDeviceId = ref('')
const systemPromptDeviceId = ref<string | null>(null)  // null for global, device_id for device-specific
const sending = ref(false)
// Status management: store status per task/session ID
const taskStatuses = ref<Record<string, string>>({}) // taskId/sessionId -> status
const chatHistory = ref<any[]>([])

// Task State (needed by composables)
const sessions = ref<any[]>([])
const backgroundTasks = ref<any[]>([])
const activeTaskId = ref<string | null>(null)

// Collapse state for messages (key: message index, value: { thought: boolean, screenshot: boolean, info?: boolean })
// true = collapsed, false = expanded
// Default: think and info messages are collapsed (true)
const messageCollapseState = ref<Record<number, { thought?: boolean, screenshot?: boolean, info?: boolean }>>({})

// Image preview state is now managed by useImagePreview composable


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
  useMjpegStream,
  mjpegStreamUrl,
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
    // Landscape detection is handled by ScreenMirror component via @load event
    // No need to detect here to avoid conflicts
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
    // onStatusMessage - Long-running task progress (e.g., installation)
    console.log('[onStatusMessage] Received status data:', data)
    if (data.taskId === activeTaskId.value && data.data) {
      const statusMsg: any = {
        role: 'agent',
        type: 'status',
        statusType: data.data.status_type || '',
        status: data.data.status || '',
        message: data.data.message || '',
        app: data.data.app || '',
        progress: data.data.progress !== undefined ? data.data.progress : null,
        sessionId: activeTaskId.value,
        timestamp: Date.now()
      }
      console.log('[onStatusMessage] Created status message:', statusMsg)
      chatHistory.value.push(statusMsg)
      db.addMessage(statusMsg).then(id => statusMsg.id = id)
      scrollToBottom()
    } else {
      console.warn('[onStatusMessage] Invalid data:', { taskId: data.taskId, activeTaskId: activeTaskId.value, hasData: !!data.data })
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
      screenshot: data.data.screenshot,
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
const appMatchingTab = ref('mappings')
const systemPromptTab = ref('cn')

// Platform detection is now provided by platformDetector utility
const chatContainer = ref<HTMLElement | null>(null)
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

// Wizard state is now managed by useConnectionWizard composable
// Device edit state is now managed by useDeviceEdit composable

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
const newTask = ref({
    type: 'chat',
    name: '',
    role: '',
    details: ''
})

// Task edit is now managed by useTaskEdit composable

// Input enhancement is now managed by useInputEnhancement composable
const inputRef = ref<any>(null)

// Config is now managed by useModelConfig composable

const api = axios.create({ baseURL: apiBaseUrl }) // GUI Backend

// Initialize additional composables
const deviceAliases = ref<Record<string, string>>({})
const { 
  devices,
  loadingDevices,
  apiConnected,
  fetchDevices,
  selectDevice,
  deleteDevice,
  handleDeviceRenamed
} = useDeviceManagement(apiBaseUrl, activeDeviceId, deviceAliases)

// Initialize device edit
const {
  editingDeviceId,
  editName,
  startEdit,
  cancelEdit,
  saveDeviceName
} = useDeviceEdit(devices, deviceAliases)

const {
  imagePreviewVisible,
  imagePreviewUrl,
  imagePreviewIndex,
  sessionImages,
  openImagePreview,
  showPreviousImage,
  showNextImage,
  handleImagePreviewKeydown
} = useImagePreview(chatHistory)

// Initialize input enhancement first (needed by task management)
const {
  availableApps,
  allApps,
  showAppSuggestions,
  appSuggestionQuery,
  attachments,
  fileInput,
  fetchDeviceApps,
  onInputChange,
  selectApp,
  triggerAppSelect,
  triggerUpload,
  handleFileSelect,
  removeAttachment
} = useInputEnhancement(apiBaseUrl, activeDeviceId, input, inputRef)

// Initialize task management (uses allApps for LLM and fetchDeviceApps from above)
const {
  startingTask,
  stoppingTask,
  hasMoreMessages,
  isLoadingMore,
  taskLogRefreshInterval,
  fetchData,
  createTask,
  selectTask,
  deleteTask,
  loadMessages,
  handleChatScroll,
  refreshTaskLogs,
  sendMessage: sendMessageComposable,
  startBackgroundTask,
  stopTask
} = useTaskManagement(
  apiBaseUrl,
  activeDeviceId,
  activeTaskId,
  sessions,
  backgroundTasks,
  chatHistory,
  taskStatuses,
  allApps,
  isBackgroundTask,
  activeTask,
  convertLogsToChat,
  scrollToBottom,
  fetchDeviceApps
)

// Initialize connection wizard
const {
  wizardStep,
  wizardType,
  checkingUsb,
  usbStatus,
  enablingWifi,
  connectingWifi,
  wifiIp,
  webrtcUrl,
  checkUsbConnection,
  enableWifiMode,
  connectWifi,
  handleWizardNext,
  handleWizardPrev,
  finishWizard
} = useConnectionWizard(apiBaseUrl, fetchDevices, devices)

// Initialize config management
const {
  showAppMatchingConfig,
  appMatchingConfig,
  showSystemPromptConfig,
  systemPromptConfig,
  loadAppMatchingConfig,
  saveAppMatchingConfig,
  resetAppMatchingConfig,
  loadSystemPromptConfig,
  saveSystemPromptConfig,
  resetSystemPromptConfig
} = useConfigManagement(apiBaseUrl)

// Initialize permissions
const {
  showPermissions,
  devicePermissions,
  openPermissions,
  savePermissions
} = usePermissions(apiBaseUrl, activeDeviceId)

// Initialize recording
const {
  isRecording,
  recordingId,
  actionCount: recordingActionCount,
  recordings,
  loading: recordingLoading,
  startRecording,
  stopRecording,
  saveRecording,
  fetchRecordings,
  deleteRecording: deleteRecordingComposable,
  executeRecording,
  getRecordingStatus,
  previewRecording,
  debugRecording,
  resetRecordingState,
  executeSingleAction,
  replaceAction,
  startingRecording
} = useRecording(apiBaseUrl, activeDeviceId)

const showRecordingDialog = ref(false)
const showRecordingList = ref(false)

// Initialize interaction handlers
const {
  handleCardAction,
  handleCardInput,
  handleCardAnnotation
} = useInteraction(apiBaseUrl, activeTaskId)

// Initialize model config
const {
  showConfig,
  selectedProvider,
  config,
  updateProviderConfig,
  syncConfigToBackend,
  saveConfig
} = useModelConfig(apiBaseUrl)

// Initialize stream quality
const {
  streamQuality,
  updateStreamQuality
} = useStreamQuality(apiBaseUrl)

// Initialize task edit
const {
  showEditTaskDialog,
  editTaskNameValue,
  taskToEdit,
  startEditTask,
  saveTaskName
} = useTaskEdit(apiBaseUrl)

// Initialize app matching UI helpers
const {
  addMapping,
  removeMapping,
  updateMappingKey,
  addPackage,
  removePackage,
  updatePackagePlatform
} = useAppMatchingUI(appMatchingConfig)

// Initialize connection guide
const showConnectionGuide = ref(false)

// --- Computed ---
const filteredChatHistory = computed(() => {
  console.log('[filteredChatHistory] All messages before filter:', chatHistory.value.map((msg: any) => ({
    role: msg.role,
    thought: msg.thought,
    thoughtLength: msg.thought?.length,
    isThinking: msg.isThinking,
    content: msg.content,
    contentLength: msg.content?.length,
    action: msg.action,
    type: msg.type,
    isInfo: msg.isInfo,
    isFailed: msg.isFailed,
    isError: msg.isError,
    hasScreenshot: !!msg.screenshot
  })))
  
  const filtered = chatHistory.value.filter((msg: any) => {
    // User messages always have content, so keep them
    if (msg.role === 'user') {
      return true
    }
    
    // Agent messages: filter out completely empty ones
    // A message is considered empty if it has:
    // - No thought (or empty/whitespace thought) AND
    // - No content (or empty/whitespace content) AND
    // - No action AND
    // - No type (interaction messages) AND
    // - No special flags (isInfo, isFailed, isError) AND
    // - No screenshot (screenshot-only messages should be shown)
    // BUT: Keep messages with isThinking=true even if thought is empty (will show "思考中...")
    const hasThought = msg.thought && msg.thought.trim()
    const hasContent = msg.content && msg.content.trim()
    const hasAction = msg.action
    const hasType = msg.type // interaction messages (confirm, input, click_annotation, status)
    const hasSpecialFlags = msg.isInfo || msg.isFailed || msg.isError
    const hasScreenshot = msg.screenshot
    const isThinking = msg.isThinking === true
    
    // Check if action is non-empty (could be string or object)
    const hasValidAction = hasAction && (
      typeof hasAction === 'string' ? hasAction.trim() : 
      typeof hasAction === 'object' ? Object.keys(hasAction).length > 0 : 
      false
    )
    
    // For status messages, check if they have valid status data
    // A status message is valid if it has statusType AND at least one of: status, message, or progress
    const hasValidStatus = hasType === 'status' && (
      (msg.statusType && (msg.statusType.trim ? msg.statusType.trim() : msg.statusType)) &&
      ((msg.status && msg.status.trim()) || (msg.message && msg.message.trim()) || msg.progress !== undefined || msg.progress !== null)
    )
    
    // Keep if has any content, or is thinking (will show placeholder), or has screenshot, or has valid status
    // For status messages, only keep if they have valid data
    const shouldKeep = hasThought || hasContent || hasValidAction || hasValidStatus || (hasType && hasType !== 'status') || hasSpecialFlags || hasScreenshot || isThinking
    
    if (!shouldKeep) {
      console.log('[filteredChatHistory] Filtered out message:', {
        role: msg.role,
        thought: msg.thought,
        isThinking: msg.isThinking,
        content: msg.content,
        action: msg.action,
        type: msg.type
      })
    }
    
    return shouldKeep
  })
  
  console.log('[filteredChatHistory] Filtered messages:', filtered.map((msg: any) => ({
    role: msg.role,
    thought: msg.thought,
    thoughtLength: msg.thought?.length,
    isThinking: msg.isThinking,
    content: msg.content,
    contentLength: msg.content?.length,
    action: msg.action,
    type: msg.type
  })))
  
  return filtered
})

// --- Methods ---
const handleTaskSave = async (data: any) => {
    if (data.name) await createTask(data)
}

// Recording handlers
const handleToggleRecording = async () => {
  if (isRecording.value) {
    const recordingId = await stopRecording()
    if (recordingId && recordingActionCount.value > 0) {
      showRecordingDialog.value = true
    }
  } else {
    await startRecording()
    // Start polling for recording status
    startRecordingStatusPolling()
  }
}

const handleSaveRecording = async (name: string, keywords: string[], description?: string) => {
  const success = await saveRecording(name, keywords, description)
  if (success) {
    showRecordingDialog.value = false
    await fetchRecordings(activeDeviceId.value)
  }
}

const handleExecuteRecording = async (recording: any) => {
  showRecordingList.value = false
  await executeRecording(recording.id)
}

const handleDeleteRecording = async (recordingId: string) => {
  await deleteRecordingComposable(recordingId)
  await fetchRecordings(activeDeviceId.value)
}

let recordingStatusInterval: any = null
const startRecordingStatusPolling = () => {
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
  }
  recordingStatusInterval = setInterval(async () => {
    if (isRecording.value && activeDeviceId.value) {
      await getRecordingStatus()
    } else {
      if (recordingStatusInterval) {
        clearInterval(recordingStatusInterval)
        recordingStatusInterval = null
      }
    }
  }, 1000) // Poll every second
}

const handleTaskNameSave = async (data: any) => {
    if (taskToEdit.value && data.name) await saveTaskName()
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

const sendMessage = () => sendMessageComposable(input, sending)

onMounted(async () => {
  // Initialize recording status
  if (activeDeviceId.value) {
    await getRecordingStatus()
    await fetchRecordings(activeDeviceId.value)
  }
  const savedConfig = await db.getConfig()
  if (savedConfig) {
    // Restore configuration, preserving all fields including apiKey
    console.log('Loading saved config:', savedConfig)
    if (savedConfig.baseUrl) config.value.baseUrl = savedConfig.baseUrl
    if (savedConfig.model) config.value.model = savedConfig.model
    if (savedConfig.apiKey !== undefined) config.value.apiKey = savedConfig.apiKey  // Preserve API key even if empty
    if (savedConfig.selectedProvider) {
      selectedProvider.value = savedConfig.selectedProvider
    }
    console.log('Restored config:', config.value)
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
        fetchData()
        startStreamLoopComposable()
    } else {
        isStreaming.value = false
        if (taskLogRefreshInterval.value) {
            clearInterval(taskLogRefreshInterval.value)
            taskLogRefreshInterval.value = null
        }
        sessions.value = []
        backgroundTasks.value = []
        activeTaskId.value = null
        chatHistory.value = []
        allApps.value = []
        taskStatuses.value = {}
    }
})

watch(activeTaskId, (newId, oldId) => {
    if (oldId && taskLogRefreshInterval.value) {
        clearInterval(taskLogRefreshInterval.value)
        taskLogRefreshInterval.value = null
    }
})

onMounted(() => window.addEventListener('keydown', handleImagePreviewKeydown))

onUnmounted(() => {
  if (recordingStatusInterval) {
    clearInterval(recordingStatusInterval)
  }
})
onUnmounted(() => window.removeEventListener('keydown', handleImagePreviewKeydown))
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
