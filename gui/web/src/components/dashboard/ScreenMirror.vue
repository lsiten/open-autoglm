<template>
  <div v-if="activeDeviceId" class="w-[400px] min-w-[350px] bg-[#000] border-l border-gray-800 flex flex-col relative shrink-0 z-20">
    <div class="h-16 border-b border-gray-800/50 flex items-center justify-between px-4 bg-[#0d1117] shrink-0">
      <span class="text-xs font-bold text-gray-500 uppercase tracking-wider">{{ t('mirror.title') }}</span>
      <div class="flex items-center gap-2">
        <!-- Stream Quality Selector -->
        <el-dropdown @command="$emit('update-quality', $event)" trigger="click">
          <span class="el-dropdown-link text-[10px] font-mono text-gray-400 hover:text-white cursor-pointer bg-gray-800 border border-gray-700 px-2 py-0.5 rounded flex items-center gap-1">
            {{ t('mirror.quality_' + streamQuality) }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu class="custom-dropdown">
              <el-dropdown-item v-for="opt in qualityOptions" :key="opt.key" :command="opt.key" :class="{'!text-blue-400': streamQuality === opt.key}">
                {{ t('mirror.quality_' + opt.key) }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-tag size="small" effect="dark" class="!bg-gray-800 !border-gray-700 text-gray-400 font-mono text-[10px]">{{ fps }} {{ t('chat.fps') }}</el-tag>
      </div>
    </div>
    
    <div class="flex-1 flex items-center justify-center p-4 sm:p-6 bg-[url('/grid.svg')] bg-repeat opacity-100 overflow-hidden">
      <!-- Phone Frame -->
      <div class="relative w-full bg-gray-900 rounded-[2.5rem] ring-8 ring-gray-800 shadow-2xl overflow-hidden select-none transition-all duration-500"
           :class="isLandscape ? 'max-w-[600px] aspect-[19.5/9]' : 'max-w-[320px] aspect-[9/19.5]'">
        <div v-if="!isLandscape" class="absolute top-0 left-1/2 -translate-x-1/2 w-32 h-6 bg-black rounded-b-xl z-20"></div>
        
        <!-- Screen Content -->
        <div class="w-full h-full relative group cursor-crosshair" 
             @mousedown="$emit('mouse-down', $event)"
             @mousemove="$emit('mouse-move', $event)"
             @mouseup="$emit('mouse-up', $event)"
             @mouseleave="$emit('mouse-up', $event)">
          <img v-if="latestScreenshot" :src="latestScreenshot" class="w-full h-full object-fill pointer-events-none select-none" draggable="false" />
          
          <!-- Loading State -->
          <div v-else class="w-full h-full flex flex-col items-center justify-center text-gray-600 gap-3 bg-[#050505]">
            <div class="relative">
              <div class="w-12 h-12 border-2 border-gray-700 rounded-full animate-spin border-t-blue-500"></div>
              <el-icon class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-gray-600"><VideoCamera /></el-icon>
            </div>
            <span class="text-xs font-mono text-center px-4" v-html="t('mirror.waiting_signal').replace(' ', '<br>')"></span>
          </div>

          <!-- Click Ripple Effect -->
          <div v-for="click in clickEffects" :key="click.id" 
               class="absolute rounded-full border-2 border-blue-400 bg-blue-400/30 animate-ping pointer-events-none"
               :style="{ left: click.x + 'px', top: click.y + 'px', width: '20px', height: '20px', transform: 'translate(-50%, -50%)' }">
          </div>
        </div>
      </div>
    </div>
    
    <!-- Quick Actions Footer -->
    <div class="h-16 border-t border-gray-800 bg-[#0d1117] flex items-center justify-around px-4 shrink-0">
      <el-tooltip :content="t('mirror.home')" placement="top">
        <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="$emit('go-home')">
          <el-icon><House /></el-icon>
        </el-button>
      </el-tooltip>
      <el-tooltip :content="t('mirror.back')" placement="top">
        <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="$emit('go-back')">
          <el-icon><Back /></el-icon>
        </el-button>
      </el-tooltip>
      <el-tooltip :content="t('mirror.recent_apps')" placement="top">
        <el-button circle class="!bg-gray-800 !border-gray-700 hover:!bg-gray-700 hover:!text-white" @click="$emit('go-recent')">
          <el-icon><Menu /></el-icon>
        </el-button>
      </el-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowDown, VideoCamera, House, Back, Menu } from '@element-plus/icons-vue'

defineProps<{
  activeDeviceId: string
  latestScreenshot: string
  isLandscape: boolean
  streamQuality: string
  fps: number
  clickEffects: any[]
  qualityOptions: Array<{ key: string }>
}>()

defineEmits<{
  'update-quality': [key: string]
  'mouse-down': [event: MouseEvent]
  'mouse-move': [event: MouseEvent]
  'mouse-up': [event: MouseEvent]
  'go-home': []
  'go-back': []
  'go-recent': []
}>()

const { t } = useI18n()
</script>

