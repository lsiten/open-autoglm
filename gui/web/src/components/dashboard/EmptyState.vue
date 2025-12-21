<template>
  <div v-if="type === 'no-devices'" class="h-full flex flex-col items-center justify-center animate-fade-in">
    <div class="max-w-2xl w-full bg-[#161b22] border border-gray-800 rounded-2xl p-8 shadow-2xl">
      <div class="text-center mb-8">
        <div class="w-16 h-16 bg-blue-900/30 text-blue-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-blue-500/30">
          <el-icon :size="32"><Iphone /></el-icon>
        </div>
        <h2 class="text-2xl font-bold text-white mb-2">{{ t('guide.title') }}</h2>
        <p class="text-gray-400">{{ t('guide.subtitle') }}</p>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- USB Method -->
        <div class="bg-[#0d1117] border border-gray-700/50 rounded-xl p-5 hover:border-blue-500/50 transition-colors">
          <div class="flex items-center gap-2 mb-3 text-blue-400">
            <el-icon><Connection /></el-icon>
            <h3 class="font-bold">{{ t('guide.usb_option') }}</h3>
          </div>
          <ol class="list-decimal list-inside text-sm text-gray-400 space-y-2 marker:text-gray-600">
            <li>{{ t('guide.usb_steps.step1') }}</li>
            <li v-html="t('guide.usb_steps.step2')"></li>
            <li>{{ t('guide.usb_steps.step3') }}</li>
            <li>{{ t('guide.usb_steps.step4') }}</li>
          </ol>
        </div>

        <!-- WiFi Method -->
        <div class="bg-[#0d1117] border border-gray-700/50 rounded-xl p-5 hover:border-green-500/50 transition-colors">
          <div class="flex items-center gap-2 mb-3 text-green-400">
            <el-icon><Connection /></el-icon>
            <h3 class="font-bold">{{ t('guide.wifi_option') }}</h3>
          </div>
          <div class="text-sm text-gray-400 space-y-3">
            <p>{{ t('guide.wifi_text') }}</p>
            <div class="bg-black/50 p-2 rounded border border-gray-800 font-mono text-xs">
              <div class="text-gray-500 mb-1">{{ t('guide.wifi_step1') }}</div>
              <div class="text-green-300">adb tcpip 5555</div>
              <div class="text-gray-500 my-1">{{ t('guide.wifi_step2') }}</div>
              <div class="text-green-300">adb connect PHONE_IP:5555</div>
            </div>
            <p class="text-xs text-gray-500">{{ t('guide.wifi_tip') }}</p>
          </div>
        </div>
      </div>

      <div class="mt-8 pt-6 border-t border-gray-800 flex justify-between items-center text-xs text-gray-500">
        <div class="flex gap-4">
          <span>• {{ t('chat.harmony_os_tip') }}</span>
          <span>• {{ t('chat.ios_tip') }}</span>
        </div>
        <el-button link type="primary" size="small" @click="$emit('refresh')">
          <el-icon class="mr-1"><Refresh /></el-icon> {{ t('guide.refresh_list') }}
        </el-button>
      </div>
    </div>
  </div>

  <div v-else-if="type === 'empty-chat'" class="h-full flex flex-col items-center justify-center text-gray-600 opacity-50 select-none">
    <el-icon :size="64" class="mb-4"><ChatDotRound /></el-icon>
    <p class="text-lg font-medium">{{ t('chat.ready_title') }}</p>
    <p class="text-sm">{{ deviceId ? t('chat.ready_subtitle', { device: deviceId }) : t('chat.ready_subtitle_no_device') }}</p>
  </div>

  <div v-else-if="type === 'empty-logs'" class="h-full flex flex-col items-center justify-center text-gray-600 opacity-50 select-none">
    <el-icon :size="64" class="mb-4"><Monitor /></el-icon>
    <p class="text-lg font-medium">{{ t('task.no_logs') }}</p>
    <p class="text-sm">{{ t('task.start_task_to_see_logs') }}</p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Iphone, Connection, Refresh, ChatDotRound, Monitor } from '@element-plus/icons-vue'

defineProps<{
  type: 'no-devices' | 'empty-chat' | 'empty-logs'
  deviceId?: string
}>()

defineEmits<{
  refresh: []
}>()

const { t } = useI18n()
</script>

