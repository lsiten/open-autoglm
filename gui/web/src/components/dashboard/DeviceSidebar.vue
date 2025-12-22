<template>
  <transition name="slide-fade">
    <div v-if="modelValue" class="w-72 min-w-[18rem] bg-[#161b22] border-r border-gray-800 flex flex-col shrink-0 z-30">
      <!-- Brand -->
      <div class="h-16 border-b border-gray-800 flex items-center px-5 gap-3 shrink-0">
        <div class="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
          <img src="/logo.svg" alt="Logo" class="w-5 h-5 invert brightness-0" />
        </div>
        <span class="font-bold text-lg tracking-tight text-white">AutoGLM</span>
      </div>

      <!-- Connection Error Banner -->
      <div v-if="!apiConnected && !loadingDevices" class="bg-red-900/20 border-b border-red-900/50 p-2 text-center">
        <p class="text-[10px] text-red-300 mb-1">{{ t('sidebar.connection_failed') }}</p>
        <p v-if="wsError && !wsConnected" class="text-[9px] text-red-400 mb-1 font-mono break-all">{{ wsError }}</p>
        <a :href="`${backendRootUrl}/docs`" target="_blank" class="text-[10px] text-blue-400 underline hover:text-blue-300 block">
          {{ t('sidebar.trust_certificate') }}
        </a>
        <span class="text-[9px] text-gray-500 block mt-1">{{ t('sidebar.accept_unsafe') }}</span>
      </div>

      <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
        <!-- Device Section -->
        <div class="flex items-center justify-between mb-3">
          <div class="text-xs font-bold text-gray-500 uppercase tracking-wider">{{ t('sidebar.devices') }}</div>
          <el-button link type="primary" size="small" @click="$emit('refresh-devices')" :loading="loadingDevices">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
        
        <div class="space-y-2">
          <!-- Always show Connect Guide button -->
          <div 
            class="p-3 rounded-lg border border-dashed border-gray-700 text-center hover:bg-gray-800/50 cursor-pointer transition-colors flex items-center justify-center gap-2" 
            @click="$emit('show-connection-guide')"
          >
            <el-icon class="text-blue-400"><Plus /></el-icon>
            <span class="text-xs text-gray-500">{{ t('sidebar.add_device') }}</span>
          </div>

          <div 
            v-for="dev in devices"  
            :key="dev.id"
            class="group relative p-3 rounded-xl border border-gray-700/50 bg-gray-800/30 transition-all duration-200"
            :class="{ 
              '!bg-blue-900/10 !border-blue-500/80 shadow-[0_0_15px_-3px_rgba(59,130,246,0.3)]': activeDeviceId === dev.id,
              'opacity-60 grayscale cursor-not-allowed': dev.status === 'offline',
              'hover:bg-gray-800 hover:border-blue-500/50 cursor-pointer': dev.status !== 'offline'
            }"
            @click="$emit('select-device', dev)"
          >
            <div class="flex items-center justify-between mb-1">
              <div class="flex items-center gap-2 overflow-hidden flex-1 mr-2">
                <el-icon :class="activeDeviceId === dev.id ? 'text-blue-400' : 'text-gray-400'" class="shrink-0"><Iphone /></el-icon>
                
                <!-- Rename UI -->
                <div v-if="editingDeviceId === dev.id" class="flex items-center gap-1 w-full" @click.stop>
                  <el-input v-model="editName" size="small" @keyup.enter="handleSaveDeviceName(dev)" ref="renameInput" />
                  <el-button size="small" circle type="success" @click="handleSaveDeviceName(dev)"><el-icon><Check /></el-icon></el-button>
                  <el-button size="small" circle @click="handleCancelEdit"><el-icon><Close /></el-icon></el-button>
                </div>
                <div v-else class="flex items-center gap-2 group/name w-full overflow-hidden">
                  <span class="text-sm font-medium text-gray-200 truncate" :title="dev.id">{{ dev.displayName || dev.model || dev.id }}</span>
                  <el-icon class="opacity-0 group-hover/name:opacity-100 cursor-pointer text-gray-500 hover:text-white" @click.stop="handleStartEdit(dev)"><Edit /></el-icon>
                </div>
              </div>
              
              <div class="flex items-center gap-2">
                <!-- Delete Button (visible on hover) -->
                <el-button 
                  v-if="dev.type === 'webrtc'"
                  class="!p-1 opacity-0 group-hover:opacity-100 transition-opacity" 
                  type="danger" 
                  link 
                  @click.stop="$emit('delete-device', dev)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>

                <div class="flex h-2 w-2 shrink-0">
                  <span v-if="dev.status !== 'offline'" class="animate-ping absolute inline-flex h-2 w-2 rounded-full opacity-75" :class="dev.status === 'device' || dev.status === 'connected' ? 'bg-green-400' : 'bg-red-400'"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2" :class="{
                    'bg-green-500': dev.status === 'device' || dev.status === 'connected',
                    'bg-red-500': dev.status === 'unauthorized',
                    'bg-gray-500': dev.status === 'offline'
                  }"></span>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 text-[10px] text-gray-500 font-mono">
              <span class="px-1.5 py-0.5 rounded bg-gray-700/50">{{ dev.type.toUpperCase() }}</span>
              <span v-if="dev.brand" class="px-1.5 py-0.5 rounded bg-blue-700/50 text-blue-300">{{ dev.brand }}</span>
              <span>{{ dev.connection_type }}</span>
              <span v-if="dev.status === 'offline'" class="text-red-400 italic">{{ t('sidebar.offline') || 'Offline' }}</span>
            </div>
            <!-- Device-specific system prompt config button (always visible) -->
            <div 
              v-if="dev.status !== 'offline'"
              class="mt-2 pt-2 border-t border-gray-700/50"
              @click.stop
            >
              <div 
                @click="$emit('show-device-system-prompt-config', dev.id)"
                class="flex items-center gap-2 p-1.5 rounded hover:bg-gray-700/50 cursor-pointer transition-colors"
              >
                <el-icon class="text-gray-500 hover:text-blue-400"><Document /></el-icon>
                <span class="text-[10px] text-gray-500 hover:text-gray-300">{{ t('sidebar.device_system_prompt') }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Config -->
        <div v-if="activeDeviceId" @click="$emit('show-config')" class="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 cursor-pointer group transition-colors mt-4">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center group-hover:bg-gray-700 transition-colors">
              <el-icon><Setting /></el-icon>
            </div>
            <span class="text-sm text-gray-400 group-hover:text-gray-200">{{ t('sidebar.model_settings') }}</span>
          </div>
          <el-icon class="text-gray-600 group-hover:text-gray-400"><ArrowRight /></el-icon>
        </div>
        <div v-if="activeDeviceId" @click="$emit('show-app-matching-config')" class="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 cursor-pointer group transition-colors">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center group-hover:bg-gray-700 transition-colors">
              <el-icon><Tools /></el-icon>
            </div>
            <span class="text-sm text-gray-400 group-hover:text-gray-200">{{ t('sidebar.app_matching_settings') }}</span>
          </div>
          <el-icon class="text-gray-600 group-hover:text-gray-400"><ArrowRight /></el-icon>
        </div>
        <!-- Global system prompt config (no device_id) -->
        <div @click="$emit('show-system-prompt-config', null)" class="flex items-center justify-between p-2 rounded-lg hover:bg-white/5 cursor-pointer group transition-colors">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center group-hover:bg-gray-700 transition-colors">
              <el-icon><Document /></el-icon>
            </div>
            <span class="text-sm text-gray-400 group-hover:text-gray-200">{{ t('sidebar.system_prompt_settings') }}</span>
          </div>
          <el-icon class="text-gray-600 group-hover:text-gray-400"><ArrowRight /></el-icon>
        </div>
      </div>
      
      <!-- Sidebar Footer -->
      <div class="p-4 border-t border-gray-800 bg-[#161b22] shrink-0">
        <div class="flex items-center gap-2 text-xs text-gray-500">
          <div class="w-2 h-2 rounded-full" :class="apiConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-red-500'"></div>
          <span>{{ apiConnected ? t('sidebar.connected') : t('sidebar.disconnected') }}</span>
        </div>
        <div v-if="apiConnected && !wsConnected" class="flex items-center gap-2 text-[10px] text-yellow-500 mt-1">
          <span>{{ t('sidebar.ws_disconnected') || 'WebSocket未连接' }}</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Refresh, Plus, Iphone, Check, Close, Edit, Delete,
  Setting, Tools, Document, ArrowRight
} from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  devices: any[]
  activeDeviceId: string
  loadingDevices: boolean
  wsConnected: boolean
  apiConnected: boolean
  wsError: string
  wsBaseUrl: string
  backendRootUrl: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'refresh-devices': []
  'select-device': [device: any]
  'delete-device': [device: any]
  'show-connection-guide': []
  'show-config': []
  'show-app-matching-config': []
  'show-system-prompt-config': [deviceId: string | null]  // null for global, device_id for device-specific
  'show-device-system-prompt-config': [deviceId: string]  // Device-specific system prompt config
  'device-renamed': [device: any, newName: string]
}>()

const { t } = useI18n()
const editingDeviceId = ref('')
const editName = ref('')
const renameInput = ref<any>(null)

const handleStartEdit = (device: any) => {
  editingDeviceId.value = device.id
  editName.value = device.displayName || device.model || device.id
  nextTick(() => {
    if (renameInput.value && renameInput.value.length > 0) {
      renameInput.value[0].focus()
    }
  })
}

const handleCancelEdit = () => {
  editingDeviceId.value = ''
  editName.value = ''
}

const handleSaveDeviceName = async (device: any) => {
  const newName = editName.value.trim()
  if (newName) {
    emit('device-renamed', device, newName)
  }
  handleCancelEdit()
}
</script>

<style scoped>
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateX(-20px);
  opacity: 0;
}
</style>

