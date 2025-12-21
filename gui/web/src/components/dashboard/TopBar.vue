<template>
  <div class="h-16 border-b border-gray-800 flex items-center justify-between px-4 sm:px-6 bg-[#0f1115]/80 backdrop-blur z-20 sticky top-0 shrink-0">
    <div class="flex items-center gap-4">
      <el-button circle text @click="$emit('toggle-sidebar')">
        <el-icon><Menu /></el-icon>
      </el-button>
      
      <!-- Current Session / Task Selector -->
      <el-dropdown v-if="activeDeviceId" trigger="click" @command="$emit('select-task', $event)" class="min-w-[200px]">
        <div class="flex items-center gap-3 cursor-pointer hover:bg-gray-800 px-3 py-1.5 rounded-lg transition-colors border border-transparent hover:border-gray-700">
          <div class="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-blue-400 shrink-0">
            <el-icon v-if="activeTask?.type === 'background'"><Monitor /></el-icon>
            <el-icon v-else><ChatLineRound /></el-icon>
          </div>
          <div class="flex flex-col min-w-0">
            <span class="text-[10px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-1">
              {{ activeTask?.type === 'background' ? t('task.task') : t('task.session') }}
              <span v-if="agentStatus === 'running'" class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
            </span>
            <span class="text-sm font-medium text-white flex items-center gap-2 truncate max-w-[150px]">
              {{ activeTask?.name || t('task.select_session') }}
              <el-icon class="text-gray-500 text-xs shrink-0"><ArrowDown /></el-icon>
            </span>
          </div>
        </div>
        <template #dropdown>
          <el-dropdown-menu class="min-w-[280px] p-2 custom-dropdown">
            <!-- Sessions (IndexedDB) -->
            <div class="px-3 py-2 text-[10px] font-bold text-gray-500 uppercase flex justify-between items-center bg-gray-50/5 rounded mb-1">
              <span>{{ t('task.sessions_local') }}</span>
              <el-button link type="primary" size="small" @click.stop="$emit('create-task', 'chat')">
                <el-icon><Plus /></el-icon>
              </el-button>
            </div>
            
            <div class="max-h-[200px] overflow-y-auto custom-scrollbar" @scroll="$emit('session-scroll', $event)">
              <el-dropdown-item 
                v-for="s in visibleSessions" 
                :key="s.id" 
                :command="s" 
                :class="{'!text-blue-400 !bg-blue-900/10': activeTaskId === s.id}"
              >
                <div class="flex items-center justify-between w-full gap-3 group/item">
                  <div class="flex items-center gap-2 overflow-hidden flex-1">
                    <el-icon><ChatLineRound /></el-icon>
                    <span class="truncate">{{ s.name }}</span>
                  </div>
                  <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
                    <el-icon class="text-gray-500 hover:text-white" @click.stop="$emit('edit-task', s)">
                      <Edit />
                    </el-icon>
                    <el-icon class="text-gray-500 hover:text-red-400" @click.stop="$emit('delete-task', s)">
                      <Delete />
                    </el-icon>
                  </div>
                </div>
              </el-dropdown-item>
              <div v-if="sessions.length > visibleSessions.length" class="text-center py-2 text-[10px] text-gray-500">
                <el-icon class="is-loading"><Loading /></el-icon>
              </div>
            </div>
            <div v-if="sessions.length === 0" class="px-4 py-2 text-xs text-gray-500 italic">
              {{ t('task.no_sessions') }}
            </div>

            <div class="border-t border-gray-700/50 my-2"></div>

            <!-- Tasks (Backend) -->
            <div class="px-3 py-2 text-[10px] font-bold text-gray-500 uppercase flex justify-between items-center bg-gray-50/5 rounded mb-1">
              <span>{{ t('task.background_tasks_remote') }}</span>
              <el-button link type="primary" size="small" @click.stop="$emit('create-task', 'background')">
                <el-icon><Plus /></el-icon>
              </el-button>
            </div>
            <el-dropdown-item 
              v-for="t in backgroundTasks" 
              :key="t.id" 
              :command="t" 
              :class="{'!text-blue-400 !bg-blue-900/10': activeTaskId === t.id}"
            >
              <div class="flex items-center justify-between w-full gap-3 group/item">
                <div class="flex items-center gap-2 overflow-hidden flex-1">
                  <el-icon><Monitor /></el-icon>
                  <span class="truncate">{{ t.name }}</span>
                </div>
                <div class="flex items-center gap-1 shrink-0 opacity-0 group-hover/item:opacity-100 transition-opacity">
                  <span v-if="t.status === 'running'" class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                  <el-icon class="text-gray-500 hover:text-white" @click.stop="$emit('edit-task', t)">
                    <Edit />
                  </el-icon>
                  <el-icon class="text-gray-500 hover:text-red-400" @click.stop="$emit('delete-task', t)">
                    <Delete />
                  </el-icon>
                </div>
              </div>
            </el-dropdown-item>
            <div v-if="backgroundTasks.length === 0" class="px-4 py-2 text-xs text-gray-500 italic">
              {{ t('task.no_tasks') }}
            </div>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <div class="flex items-center gap-3">
      <!-- Permissions Button -->
      <el-tooltip :content="t('permissions.title')" placement="bottom">
        <el-button 
          v-if="activeDeviceId" 
          circle 
          class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" 
          @click="$emit('show-permissions')"
        >
          <el-icon><Lock /></el-icon>
        </el-button>
      </el-tooltip>

      <!-- Task Management Buttons (Only for Background Tasks) -->
      <template v-if="isBackgroundTask && activeTaskId">
        <el-button 
          v-if="activeTask?.status !== 'running'" 
          type="success" 
          size="small" 
          round 
          @click="$emit('start-task')"
          :loading="startingTask"
        >
          <el-icon class="mr-1"><VideoPlay /></el-icon> {{ t('task.start') }}
        </el-button>
        <el-button 
          v-if="activeTask?.status === 'running'" 
          type="warning" 
          size="small" 
          round 
          @click="$emit('stop-task')"
          :loading="stoppingTask"
        >
          <el-icon class="mr-1"><VideoPause /></el-icon> {{ t('task.pause') }}
        </el-button>
      </template>

      <!-- Stop Button for Chat Sessions -->
      <el-button 
        v-if="!isBackgroundTask && agentStatus === 'running'" 
        type="danger" 
        size="small" 
        round 
        @click="$emit('stop-task')"
      >
        <el-icon class="mr-1"><VideoPause /></el-icon> {{ t('common.stop') }}
      </el-button>

      <!-- Language Switcher -->
      <el-dropdown @command="(lang: string) => $emit('change-locale', lang)">
        <span class="text-xs text-gray-400 hover:text-white cursor-pointer flex items-center">
          {{ locale.toUpperCase() }} <el-icon class="ml-1"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="en">English</el-dropdown-item>
            <el-dropdown-item command="zh">中文</el-dropdown-item>
            <el-dropdown-item command="ja">日本語</el-dropdown-item>
            <el-dropdown-item command="ko">한국어</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Menu, Monitor, ChatLineRound, ArrowDown, Plus, Edit, Delete,
  Loading, Lock, VideoPlay, VideoPause
} from '@element-plus/icons-vue'

const props = defineProps<{
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
}>()

const emit = defineEmits<{
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
}>()

const { t } = useI18n()
</script>

