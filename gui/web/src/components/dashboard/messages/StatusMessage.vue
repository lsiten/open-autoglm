<template>
  <div class="mt-2 w-full max-w-sm bg-[#1c2128] border border-purple-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
    <div class="px-4 py-3 border-b border-gray-700/50 bg-purple-900/10 flex items-center gap-2">
      <el-icon class="text-purple-400" :class="{ 'is-loading': isProgressing }">
        <Loading v-if="isProgressing" />
        <Check v-else-if="isCompleted" />
        <Warning v-else-if="isFailed" />
        <InfoFilled v-else />
      </el-icon>
      <span class="text-xs font-bold text-purple-100">{{ statusTitle }}</span>
    </div>
    <div class="p-4 space-y-3">
      <p class="text-sm text-gray-300">{{ displayMessage }}</p>
      <div v-if="message.progress !== null && message.progress !== undefined" class="space-y-1">
        <div class="flex justify-between text-xs text-gray-400">
          <span>{{ t('chat.progress') }}</span>
          <span>{{ Math.round(message.progress * 100) }}%</span>
        </div>
        <el-progress 
          :percentage="Math.round(message.progress * 100)" 
          :status="progressStatus"
          :stroke-width="6"
          class="custom-progress"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loading, Check, Warning, InfoFilled } from '@element-plus/icons-vue'

const props = defineProps<{
  message: any
}>()

const { t } = useI18n()

const statusType = computed(() => props.message.statusType || '')
const isProgressing = computed(() => statusType.value === 'installation_progress' || statusType.value === 'installation_detected')
const isCompleted = computed(() => statusType.value === 'installation_completed')
const isFailed = computed(() => statusType.value === 'installation_failed' || statusType.value === 'installation_timeout')

const statusTitle = computed(() => {
  const titles: Record<string, string> = {
    'installation_detected': t('status.installation_detected', '检测到安装任务'),
    'installation_progress': t('status.installation_progress', '安装进度'),
    'installation_completed': t('status.installation_completed', '安装完成'),
    'installation_failed': t('status.installation_failed', '安装失败'),
    'installation_timeout': t('status.installation_timeout', '安装超时')
  }
  return titles[statusType.value] || t('status.task_status', '任务状态')
})

const displayMessage = computed(() => {
  if (props.message.message && props.message.message.trim()) {
    return props.message.message
  }
  if (props.message.status && props.message.status.trim()) {
    return props.message.status
  }
  return ''
})

// Check if message has valid data to display
const hasValidData = computed(() => {
  return (statusType.value && statusType.value.trim()) && 
         (displayMessage.value || props.message.progress !== undefined)
})

const progressStatus = computed(() => {
  if (isCompleted.value) return 'success'
  if (isFailed.value) return 'exception'
  return null
})
</script>

<style scoped>
.custom-progress :deep(.el-progress-bar__outer) {
  background-color: rgba(255, 255, 255, 0.1);
}

.custom-progress :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #a855f7 0%, #8b5cf6 100%);
}
</style>

