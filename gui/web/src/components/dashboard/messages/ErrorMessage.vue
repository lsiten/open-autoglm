<template>
  <div class="mb-2 w-full max-w-xl">
    <div class="bg-red-500/10 border-l-4 border-red-500 rounded-r-lg overflow-hidden">
      <div class="px-4 py-3 flex items-start gap-3">
        <div class="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <el-icon class="text-red-400" :size="14"><CircleCloseFilled /></el-icon>
        </div>
        <div class="flex-1">
          <div class="text-sm text-red-300 font-semibold mb-1">{{ t('chat.task_failed') || '任务无法完成' }}</div>
          <div class="text-sm text-red-200 leading-relaxed">{{ message.content || message.message || message.reason }}</div>
          <div v-if="message.screenshot" class="mt-3">
            <img 
              :src="message.screenshot" 
              alt="Screenshot" 
              class="max-w-[72px] h-auto rounded-lg border border-red-500/30 shadow-lg cursor-pointer hover:opacity-80 transition-opacity"
              @click="$emit('preview-image', message.screenshot)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { CircleCloseFilled } from '@element-plus/icons-vue'

defineProps<{
  message: any
}>()

defineEmits<{
  'preview-image': [url: string]
}>()

const { t } = useI18n()
</script>

