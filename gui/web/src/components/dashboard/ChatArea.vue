<template>
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
      @toggle-sidebar="$emit('toggle-sidebar')"
      @select-task="$emit('select-task', $event)"
      @create-task="$emit('create-task', $event)"
      @edit-task="$emit('edit-task', $event)"
      @delete-task="$emit('delete-task', $event)"
      @session-scroll="$emit('session-scroll', $event)"
      @show-permissions="$emit('show-permissions')"
      @start-task="$emit('start-task')"
      @stop-task="$emit('stop-task')"
      @change-locale="$emit('change-locale', $event)"
    />

    <!-- Chat Messages Area -->
    <div class="flex-1 overflow-y-auto p-4 sm:p-8 space-y-6 custom-scrollbar scroll-smooth" ref="chatContainer" @scroll="$emit('chat-scroll', $event)">
      <!-- Empty States -->
      <EmptyState
        v-if="devices.length === 0 && !loadingDevices"
        type="no-devices"
        @refresh="$emit('refresh-devices')"
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

      <!-- Loading More Indicator -->
      <div v-if="isLoadingMore" class="w-full flex justify-center py-2 text-gray-500">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>

      <!-- Messages -->
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

          <!-- Agent Messages -->
          <template v-else>
            <slot name="message" :msg="msg" :index="index" :collapse-state="messageCollapseState[index] || {}" />
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
      @update:input="$emit('update:input', $event)"
      @send="$emit('send-message')"
      @input-change="$emit('input-change', $event)"
      @select-app="$emit('select-app', $event)"
      @trigger-app-select="$emit('trigger-app-select')"
      @trigger-upload="$emit('trigger-upload', $event)"
      @remove-attachment="$emit('remove-attachment', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import TopBar from './TopBar.vue'
import EmptyState from './EmptyState.vue'
import ChatInput from './ChatInput.vue'

defineProps<{
  activeDeviceId: string
  activeTask: any
  activeTaskId: string | null
  sessions: any[]
  visibleSessions: any[]
  backgroundTasks: any[]
  agentStatus: string
  isBackgroundTask: boolean
  startingTask: boolean
  stoppingTask: boolean
  locale: string
  devices: any[]
  loadingDevices: boolean
  chatHistory: any[]
  filteredChatHistory: any[]
  isLoadingMore: boolean
  messageCollapseState: Record<number, { thought?: boolean, screenshot?: boolean, info?: boolean }>
  input: string
  availableApps: any[]
  showAppSuggestions: boolean
  appSuggestionQuery: string
  attachments: any[]
  sending: boolean
}>()

defineEmits<{
  'toggle-sidebar': []
  'select-task': [task: any]
  'create-task': [type: 'chat' | 'background']
  'edit-task': [task: any]
  'delete-task': [task: any]
  'session-scroll': [event: Event]
  'show-permissions': []
  'start-task': []
  'stop-task': []
  'change-locale': [lang: string]
  'refresh-devices': []
  'chat-scroll': [event: Event]
  'update:input': [value: string]
  'send-message': []
  'input-change': [value: string]
  'select-app': [name: string]
  'trigger-app-select': []
  'trigger-upload': [type: string]
  'remove-attachment': [index: number]
}>()

const chatContainer = ref<HTMLElement | null>(null)
</script>

