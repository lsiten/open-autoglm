<template>
  <div class="mb-2 w-full max-w-xl">
    <div class="bg-amber-500/10 border-l-4 border-amber-500 rounded-r-lg overflow-hidden">
      <div 
        class="px-4 py-3 border-b border-amber-500/20 flex items-center justify-between cursor-pointer hover:bg-amber-500/5 transition-colors"
        @click="$emit('toggle')"
      >
        <div class="flex items-center gap-2">
          <el-icon class="text-amber-400" :class="{ 'is-loading': message.isThinking }">
            <Loading v-if="message.isThinking" />
            <Cpu v-else />
          </el-icon>
          <span class="text-xs font-medium text-amber-300 uppercase tracking-wide">{{ t('chat.reasoning_chain') }}</span>
        </div>
        <el-icon class="text-amber-400/60 text-xs transition-transform" :class="{ 'rotate-180': !collapsed }">
          <ArrowDown />
        </el-icon>
      </div>
      <div v-show="!collapsed" class="p-4 text-sm text-amber-100 leading-relaxed max-h-64 overflow-y-auto custom-scrollbar">
        <div v-if="message.thought && message.thought.trim()" v-html="formatThink(message.thought)"></div>
        <div v-else-if="message.isThinking || !message.thought" class="text-amber-300/60 italic">
          {{ t('chat.thinking') || '思考中...' }}
        </div>
      </div>
      <div v-if="message.screenshot && !collapsed" class="px-4 pb-3">
        <img 
          :src="message.screenshot" 
          alt="Screenshot" 
          class="max-w-[72px] h-auto rounded-lg border border-amber-500/30 shadow-lg cursor-pointer hover:opacity-80 transition-opacity"
          @click="$emit('preview-image', message.screenshot)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Loading, Cpu, ArrowDown } from '@element-plus/icons-vue'
import { formatThink } from '../../../utils/messageFormatter'

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

