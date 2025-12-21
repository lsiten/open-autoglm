<template>
  <div class="p-4 sm:p-6 bg-[#0f1115] border-t border-gray-800 z-20 shrink-0">
    <div class="relative max-w-4xl mx-auto w-full">
      <!-- Toolbar & Preview -->
      <div class="mb-3 flex flex-col gap-2">
        <!-- Attachments Preview -->
        <div v-if="attachments.length > 0" class="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
          <div v-for="(file, idx) in attachments" :key="idx" class="relative group bg-[#161b22] border border-gray-700 rounded-lg p-2 flex items-center gap-2 min-w-[120px] max-w-[200px]">
            <div v-if="file.type === 'image'" class="w-8 h-8 rounded bg-cover bg-center shrink-0" :style="{ backgroundImage: `url(${file.url})` }"></div>
            <div v-else class="w-8 h-8 rounded bg-gray-800 flex items-center justify-center text-gray-400 shrink-0">
              <el-icon v-if="file.type === 'video'"><VideoCamera /></el-icon>
              <el-icon v-else-if="file.type === 'audio'"><Microphone /></el-icon>
              <el-icon v-else><Document /></el-icon>
            </div>
            <span class="text-xs text-gray-300 truncate flex-1">{{ file.name }}</span>
            <button @click="$emit('remove-attachment', idx)" class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">
              <el-icon :size="10"><Close /></el-icon>
            </button>
          </div>
        </div>
        
        <!-- Toolbar -->
        <div v-if="activeDeviceId" class="flex items-center gap-4 px-1">
          <el-tooltip :content="t('input.upload_image')" placement="top">
            <button @click="$emit('trigger-upload', 'image')" class="text-gray-500 hover:text-blue-400 transition-colors">
              <el-icon :size="20"><Picture /></el-icon>
            </button>
          </el-tooltip>
          <el-tooltip :content="t('input.select_app')" placement="top">
            <button @click="$emit('trigger-app-select')" class="text-gray-500 hover:text-green-400 transition-colors">
              <el-icon :size="20"><Grid /></el-icon>
            </button>
          </el-tooltip>
          <input type="file" ref="fileInput" class="hidden" @change="handleFileSelect" />
        </div>
      </div>

      <!-- App Suggestions Popover -->
      <div v-if="showAppSuggestions" class="absolute bottom-full left-0 mb-2 bg-[#161b22] border border-gray-700 rounded-lg shadow-xl max-h-64 overflow-y-auto w-72 z-50 custom-scrollbar animate-fade-in">
        <div class="px-3 py-1.5 text-[10px] text-gray-500 font-bold uppercase tracking-wider border-b border-gray-700/50 flex justify-between">
          <span>{{ t('input.apps') }}</span>
          <span class="text-[9px] bg-gray-800 px-1 rounded">{{ availableApps.length }}</span>
        </div>
        <div v-for="app in availableApps.filter(a => a.name.toLowerCase().includes(appSuggestionQuery))" :key="app.name" 
             @click="$emit('select-app', app.name)" 
             class="px-3 py-2 hover:bg-blue-900/20 hover:text-blue-400 cursor-pointer text-sm text-gray-300 flex items-center gap-2 transition-colors border-b border-gray-800/30 last:border-0">
          <div class="w-8 h-8 bg-gray-800 rounded flex items-center justify-center text-xs font-bold shrink-0" :class="app.type === 'supported' ? 'text-green-400 bg-green-900/10' : 'text-gray-500'">{{ app.name[0].toUpperCase() }}</div>
          <div class="flex flex-col min-w-0 flex-1">
            <span class="truncate font-medium">{{ app.name }}</span>
            <span v-if="app.package" class="text-[10px] text-gray-500 truncate font-mono">{{ app.package }}</span>
          </div>
          <el-tag v-if="app.type === 'supported'" size="small" type="success" effect="plain" class="scale-75 origin-right">{{ t('input.support_tag') }}</el-tag>
        </div>
      </div>

      <el-input
        ref="inputRef"
        :model-value="input"
        @update:model-value="$emit('update:input', $event)"
        @input="$emit('input-change', ($event.target as HTMLInputElement).value)"
        :disabled="agentStatus === 'running' || !activeDeviceId"
        :placeholder="activeDeviceId ? t('chat.input_placeholder') : t('chat.select_device_placeholder')"
        class="custom-input !text-base w-full"
        size="large"
        @keyup.enter="$emit('send')"
      >
        <template #prefix>
          <el-icon class="text-gray-500"><Search /></el-icon>
        </template>
        <template #suffix>
          <el-button type="primary" circle @click="$emit('send')" :loading="sending" :disabled="!input">
            <el-icon><Position /></el-icon>
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Picture, Grid, VideoCamera, Microphone, Document, Close, Search, Position } from '@element-plus/icons-vue'

defineProps<{
  input: string
  agentStatus: string
  activeDeviceId: string
  availableApps: any[]
  showAppSuggestions: boolean
  appSuggestionQuery: string
  attachments: any[]
  sending: boolean
}>()

defineEmits<{
  'update:input': [value: string]
  'send': []
  'input-change': [value: string]
  'select-app': [name: string]
  'trigger-app-select': []
  'trigger-upload': [type: string]
  'remove-attachment': [index: number]
}>()

const { t } = useI18n()
const fileInput = ref<HTMLInputElement | null>(null)
const inputRef = ref<any>(null)

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    // Emit file select event to parent
    const file = target.files[0]
    // Parent will handle file addition
  }
  target.value = ''
}
</script>

