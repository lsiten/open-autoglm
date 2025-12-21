<template>
  <div class="mb-2 w-full max-w-xl">
    <div class="bg-indigo-500/10 border-l-4 border-indigo-500 rounded-r-lg overflow-hidden">
      <div class="px-4 py-3">
        <div class="flex items-center gap-2 mb-2">
          <el-icon class="text-indigo-400"><Picture /></el-icon>
          <span class="text-xs font-medium text-indigo-300 uppercase tracking-wide">{{ t('chat.screenshot') }}</span>
        </div>
        <img 
          :src="screenshot" 
          alt="Screenshot" 
          class="max-w-[72px] h-auto rounded-lg border border-indigo-500/30 shadow-lg cursor-pointer hover:opacity-80 transition-opacity"
          @click="$emit('preview-image', screenshot)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Picture } from '@element-plus/icons-vue'

defineProps<{
  screenshot: string
}>()

defineEmits<{
  'preview-image': [url: string]
}>()

const { t } = useI18n()
</script>

