<template>
  <el-dialog 
    v-model="visible" 
    :title="t('wizard.title')" 
    width="500px" 
    class="custom-dialog" 
    align-center 
    :show-close="false"
  >
    <div class="py-4">
      <!-- Step 1: Select Type -->
      <div v-if="wizardStep === 1" class="space-y-4">
        <h3 class="text-gray-300 text-sm font-bold mb-4">{{ t('wizard.step_type') }}</h3>
        <div class="grid grid-cols-3 gap-3">
          <div 
            class="border border-gray-700 rounded-xl p-4 hover:border-blue-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
            :class="{ '!border-blue-500 bg-blue-900/10': wizardType === 'usb' }"
            @click="wizardType = 'usb'"
          >
            <el-icon class="text-3xl text-blue-400"><Connection /></el-icon>
            <span class="text-xs font-medium text-center">{{ t('wizard.type_usb') }}</span>
          </div>
          <div 
            class="border border-gray-700 rounded-xl p-4 hover:border-green-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
            :class="{ '!border-green-500 bg-green-900/10': wizardType === 'wifi' }"
            @click="wizardType = 'wifi'"
          >
            <el-icon class="text-3xl text-green-400"><Wifi /></el-icon>
            <span class="text-xs font-medium text-center">{{ t('wizard.type_wifi') }}</span>
          </div>
          <div 
            class="border border-gray-700 rounded-xl p-4 hover:border-purple-500 cursor-pointer transition-colors flex flex-col items-center gap-3 bg-[#0d1117]"
            :class="{ '!border-purple-500 bg-purple-900/10': wizardType === 'webrtc' }"
            @click="wizardType = 'webrtc'"
          >
            <el-icon class="text-3xl text-purple-400"><VideoCamera /></el-icon>
            <span class="text-xs font-medium text-center">{{ t('wizard.type_webrtc') }}</span>
          </div>
        </div>
      </div>

      <!-- Step 2: USB Instructions -->
      <div v-if="wizardStep === 2 && wizardType === 'usb'" class="space-y-4 animate-fade-in">
        <div class="p-4 bg-blue-900/20 border border-blue-800 rounded-lg">
          <h4 class="font-bold text-blue-400 mb-2">{{ t('wizard.step_usb') }}</h4>
          <ol class="list-decimal list-inside text-sm text-gray-300 space-y-2">
            <li>{{ t('wizard.usb_instr_1') }}</li>
            <li>{{ t('wizard.usb_instr_2') }}</li>
          </ol>
        </div>
        <div class="flex justify-center py-4">
          <el-button type="primary" :loading="checkingUsb" @click="$emit('check-usb')">
            {{ t('wizard.usb_check') }}
          </el-button>
        </div>
        <div v-if="usbStatus" class="text-center text-sm font-bold" :class="usbStatus === 'found' ? 'text-green-400' : 'text-red-400'">
          {{ usbStatus === 'found' ? t('wizard.usb_found') : t('wizard.usb_not_found') }}
        </div>
      </div>

      <!-- Step 2: WiFi Setup -->
      <div v-if="wizardStep === 2 && wizardType === 'wifi'" class="space-y-6 animate-fade-in">
        <div class="border border-gray-700 rounded-lg p-4 bg-[#0d1117]">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold text-gray-200 text-sm">{{ t('wizard.wifi_mode_title') }}</h4>
            <el-tag size="small" type="info">{{ t('chat.step_1') }}</el-tag>
          </div>
          <p class="text-xs text-gray-500 mb-3">{{ t('wizard.wifi_mode_desc') }}</p>
          <el-button size="small" :loading="enablingWifi" @click="$emit('enable-wifi')">
            {{ t('wizard.wifi_mode_btn') }}
          </el-button>
        </div>
        <div class="border border-gray-700 rounded-lg p-4 bg-[#0d1117]">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold text-gray-200 text-sm">{{ t('wizard.wifi_ip_title') }}</h4>
            <el-tag size="small" type="success">{{ t('chat.step_2') }}</el-tag>
          </div>
          <p class="text-xs text-gray-500 mb-3">{{ t('wizard.wifi_ip_desc') }}</p>
          <div class="flex gap-2">
            <el-input v-model="wifiIp" :placeholder="t('wizard.wifi_ip_placeholder')" size="small" />
            <el-button type="success" size="small" :loading="connectingWifi" @click="$emit('connect-wifi', wifiIp)" :disabled="!wifiIp">
              {{ t('wizard.btn_connect') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- Step 2: WebRTC Setup -->
      <div v-if="wizardStep === 2 && wizardType === 'webrtc'" class="space-y-4 animate-fade-in">
        <div class="border border-gray-700 rounded-lg p-6 bg-[#0d1117] flex flex-col items-center gap-4">
          <div v-if="!webrtcUrl" class="text-center">
            <el-icon class="is-loading text-blue-500 text-2xl mb-2"><Loading /></el-icon>
            <p class="text-xs text-gray-500">{{ t('chat.generating_session') }}</p>
          </div>
          <template v-else>
            <div class="bg-white p-2 rounded-lg">
              <qrcode-vue :value="webrtcUrl" :size="200" level="H" />
            </div>
            <div class="text-center">
              <p class="text-sm font-bold text-gray-200 mb-1">{{ t('wizard.scan_to_connect') }}</p>
              <p class="text-xs text-gray-500 max-w-xs mx-auto mb-2">{{ t('wizard.webrtc_desc') }}</p>
              <div class="bg-gray-800 p-2 rounded text-[10px] text-gray-400 font-mono break-all select-all">
                {{ webrtcUrl }}
              </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-blue-400 animate-pulse">
              <el-icon><Connection /></el-icon>
              <span>{{ t('wizard.waiting_device') }}</span>
            </div>
          </template>
        </div>
      </div>

      <!-- Step 3: Success -->
      <div v-if="wizardStep === 3" class="text-center py-8 animate-fade-in">
        <div class="w-16 h-16 bg-green-500/20 text-green-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-green-500/50">
          <el-icon :size="32"><Check /></el-icon>
        </div>
        <h3 class="text-xl font-bold text-white">{{ t('wizard.success') }}</h3>
      </div>
    </div>
    
    <!-- Footer Navigation -->
    <template #footer>
      <div class="flex justify-between items-center border-t border-gray-700/50 pt-4">
        <el-button v-if="wizardStep > 1" @click="$emit('prev-step')" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('common.back') }}
        </el-button>
        <div v-else></div>
        <div class="flex gap-2">
          <el-button v-if="wizardStep === 1 && wizardType" @click="$emit('next-step')" type="primary" class="!bg-blue-600 !border-none">
            {{ t('common.next') }}
          </el-button>
          <el-button v-if="wizardStep === 2 && wizardType === 'usb' && usbStatus === 'found'" @click="$emit('next-step')" type="primary" class="!bg-blue-600 !border-none">
            {{ t('common.next') }}
          </el-button>
          <el-button v-if="wizardStep === 2 && wizardType === 'wifi' && wifiConnected" @click="$emit('next-step')" type="primary" class="!bg-blue-600 !border-none">
            {{ t('common.next') }}
          </el-button>
          <el-button v-if="wizardStep === 2 && wizardType === 'webrtc' && webrtcConnected" @click="$emit('next-step')" type="primary" class="!bg-blue-600 !border-none">
            {{ t('common.next') }}
          </el-button>
          <el-button v-if="wizardStep === 3" @click="handleClose" type="primary" class="!bg-blue-600 !border-none">
            {{ t('common.got_it') }}
          </el-button>
          <el-button @click="handleClose" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
            {{ t('common.cancel') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import QrcodeVue from 'qrcode.vue'
import {
  Connection, VideoCamera, Loading, Check
} from '@element-plus/icons-vue'
// Element Plus doesn't have Wifi icon, using Connection as WiFi icon alternative
// Since icons are globally registered in main.ts, we can use Connection for WiFi
const Wifi = Connection

const props = defineProps<{
  modelValue: boolean
  wizardStep: number
  wizardType: 'usb' | 'wifi' | 'webrtc' | ''
  checkingUsb: boolean
  usbStatus: 'found' | 'not_found' | ''
  enablingWifi: boolean
  connectingWifi: boolean
  wifiIp: string
  wifiConnected: boolean
  webrtcUrl: string
  webrtcConnected: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'next-step': []
  'prev-step': []
  'check-usb': []
  'enable-wifi': []
  'connect-wifi': [ip: string]
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const wifiIp = ref(props.wifiIp)

watch(() => props.wifiIp, (newVal) => {
  wifiIp.value = newVal
})

const handleClose = () => {
  visible.value = false
  emit('prev-step') // Reset to step 1
}
</script>

