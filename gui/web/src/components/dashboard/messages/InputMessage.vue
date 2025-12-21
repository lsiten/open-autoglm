<template>
  <div class="mt-2 w-full max-w-sm bg-[#1c2128] border border-amber-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
    <div class="px-4 py-3 border-b border-gray-700/50 bg-amber-900/10 flex items-center gap-2">
      <el-icon class="text-amber-400"><EditPen /></el-icon>
      <span class="text-xs font-bold text-amber-100">{{ message.title || t('chat.input_required') }}</span>
    </div>
    <div class="p-4 space-y-3">
      <p class="text-sm text-gray-300">{{ message.content }}</p>
      <div v-if="!message.submitted" class="flex gap-2">
        <el-input v-model="message.inputValue" :placeholder="message.placeholder || t('chat.enter_value')" size="small" @keyup.enter="$emit('input', { msg: message })" />
        <el-button type="primary" size="small" @click="$emit('input', { msg: message })">{{ t('common.submit') }}</el-button>
      </div>
      <div v-else class="text-xs text-gray-500 italic flex items-center justify-end gap-1">
        <el-icon><Check /></el-icon> {{ t('chat.input_submitted') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { EditPen, Check } from '@element-plus/icons-vue'

defineProps<{
  message: any
}>()

defineEmits<{
  input: [data: { msg: any }]
}>()

const { t } = useI18n()
</script>

