<template>
  <div class="mt-2 w-full max-w-sm bg-[#1c2128] border border-blue-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
    <div class="px-4 py-3 border-b border-gray-700/50 bg-blue-900/10 flex items-center gap-2">
      <el-icon class="text-blue-400"><QuestionFilled /></el-icon>
      <span class="text-xs font-bold text-blue-100">{{ message.title || t('chat.confirmation_required') }}</span>
    </div>
    <div class="p-4 space-y-4">
      <p class="text-sm text-gray-300">{{ message.content }}</p>
      <div v-if="!message.submitted" class="flex gap-3 justify-end">
        <el-button 
          v-for="opt in (message.options || [{label: 'Cancel', value: 'Cancel', type: 'info'}, {label: 'Confirm', value: 'Confirm', type: 'primary'}])" 
          :key="opt.label"
          :type="opt.type || 'default'" 
          size="small"
          @click="$emit('action', { msg: message, option: opt })"
        >
          {{ opt.label }}
        </el-button>
      </div>
      <div v-else class="text-xs text-gray-500 text-right italic flex items-center justify-end gap-1">
        <el-icon><Check /></el-icon> {{ t('chat.selected') }} {{ message.selectedValue }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { QuestionFilled, Check } from '@element-plus/icons-vue'

defineProps<{
  message: any
}>()

defineEmits<{
  action: [data: { msg: any, option: any }]
}>()

const { t } = useI18n()
</script>

