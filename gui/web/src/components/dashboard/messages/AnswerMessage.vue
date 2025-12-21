<template>
  <div class="mb-2 w-full max-w-xl">
    <div class="bg-green-500/10 border-l-4 border-green-500 rounded-r-lg overflow-hidden">
      <div class="px-4 py-3">
        <div v-if="message.action" class="flex items-start gap-3">
          <div class="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center shrink-0 mt-0.5">
            <el-icon class="text-green-400" :size="14"><Pointer /></el-icon>
          </div>
          <div class="flex-1">
            <div class="text-[10px] text-green-400 uppercase font-bold mb-1">{{ t('chat.action_executed') }}</div>
            <div class="text-sm text-green-200 font-mono" v-html="formatAnswer(message.action)"></div>
          </div>
        </div>
        <div v-else-if="message.content" class="text-sm text-green-200 leading-relaxed" v-html="formatAnswer(message.content)"></div>
        <div v-if="message.screenshot && (message.action || message.content)" class="mt-3">
          <img 
            :src="message.screenshot" 
            alt="Screenshot" 
            class="max-w-[72px] h-auto rounded-lg border border-green-500/30 shadow-lg cursor-pointer hover:opacity-80 transition-opacity"
            @click="$emit('preview-image', message.screenshot)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Pointer } from '@element-plus/icons-vue'
import { formatAnswer } from '../../../utils/messageFormatter'

defineProps<{
  message: any
}>()

defineEmits<{
  'preview-image': [url: string]
}>()

const { t } = useI18n()
</script>

