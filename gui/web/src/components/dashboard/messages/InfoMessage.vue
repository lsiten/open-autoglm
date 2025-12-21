<template>
  <div class="mb-2 w-full max-w-xl">
    <div class="bg-blue-500/10 border-l-4 border-blue-500 rounded-r-lg overflow-hidden">
      <div 
        class="px-4 py-3 border-b border-blue-500/20 flex items-center justify-between cursor-pointer hover:bg-blue-500/5 transition-colors"
        @click="$emit('toggle')"
      >
        <div class="flex items-center gap-2">
          <el-icon class="text-blue-400" :size="14"><InfoFilled /></el-icon>
          <span class="text-xs font-medium text-blue-300 uppercase tracking-wide">{{ t('chat.info') || 'Info' }}</span>
        </div>
        <el-icon class="text-blue-400/60 text-xs transition-transform" :class="{ 'rotate-180': !collapsed }">
          <ArrowDown />
        </el-icon>
      </div>
      <div v-show="!collapsed" class="px-4 py-3">
        <div class="text-sm text-blue-200 font-medium mb-1">{{ message.content }}</div>
        <div v-if="message.screenshot" class="mt-2">
          <img 
            :src="message.screenshot" 
            alt="Screenshot" 
            class="max-w-[72px] h-auto rounded-lg border border-blue-500/30 shadow-lg cursor-pointer hover:opacity-80 transition-opacity"
            @click="$emit('preview-image', message.screenshot)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { InfoFilled, ArrowDown } from '@element-plus/icons-vue'

defineProps<{
  message: any
  collapsed: boolean
}>()

defineEmits<{
  toggle: []
  'preview-image': [url: string]
}>()

const { t } = useI18n()
</script>

