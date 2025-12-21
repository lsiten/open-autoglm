<template>
  <el-dialog 
    v-model="visible" 
    :title="props.deviceId ? `${t('settings.system_prompt_title')} (${t('common.device_specific')})` : t('settings.system_prompt_title')" 
    width="1000px" 
    class="custom-dialog" 
    align-center
  >
    <div class="space-y-4">
      <div class="text-sm text-gray-400 mb-4">{{ t('settings.system_prompt_desc') }}</div>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="中文" name="cn">
          <el-input
            v-model="config.cn"
            type="textarea"
            :rows="25"
            :placeholder="t('settings.system_prompt_placeholder')"
            class="font-mono text-xs"
          />
          <div class="text-xs text-gray-500 mt-2">
            {{ t('settings.system_prompt_variables') }}: {date} - {{ t('settings.system_prompt_variables_desc') }}
          </div>
        </el-tab-pane>
        <el-tab-pane label="English" name="en">
          <el-input
            v-model="config.en"
            type="textarea"
            :rows="25"
            :placeholder="t('settings.system_prompt_placeholder')"
            class="font-mono text-xs"
          />
          <div class="text-xs text-gray-500 mt-2">
            {{ t('settings.system_prompt_variables') }}: {date} - {{ t('settings.system_prompt_variables_desc') }}
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer>
      <div class="flex justify-between items-center">
        <el-button 
          @click="showAssistant = true" 
          class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white"
        >
          <el-icon class="mr-1"><MagicStick /></el-icon>
          {{ t('settings.prompt_assistant') }}
        </el-button>
        <div class="flex gap-2">
          <el-button @click="handleCancel" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
            {{ t('common.cancel') }}
          </el-button>
          <el-button @click="handleReset" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
            {{ t('settings.reset_to_default') }}
          </el-button>
          <el-button type="primary" @click="handleSave" class="!bg-blue-600 !border-none">
            {{ t('common.save') }}
          </el-button>
        </div>
      </div>
    </template>

    <!-- Prompt Assistant Dialog -->
    <PromptAssistantDialog
      v-model="showAssistant"
      :api-base-url="apiBaseUrl"
      :current-prompt="config[activeTab as 'cn' | 'en']"
      :lang="activeTab"
      :device-id="deviceId"
      @apply="handleAssistantApply"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'
import PromptAssistantDialog from './PromptAssistantDialog.vue'

const props = defineProps<{
  modelValue: boolean
  apiBaseUrl: string
  deviceId?: string | null  // Optional device ID. If provided, configures device-specific prompt; otherwise global prompt.
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})
const activeTab = ref('cn')
const config = ref({
  cn: '',
  en: ''
})
const showAssistant = ref(false)

const api = axios.create({ baseURL: props.apiBaseUrl })

watch(visible, async (newVal) => {
  if (newVal) {
    await loadConfig()
  }
})

const loadConfig = async () => {
  try {
    const deviceParam = props.deviceId ? `&device_id=${props.deviceId}` : ''
    const [cnRes, enRes] = await Promise.all([
      api.get(`/agent/system-prompt?lang=cn${deviceParam}`),
      api.get(`/agent/system-prompt?lang=en${deviceParam}`)
    ])
    config.value = {
      cn: cnRes.data.prompt || '',
      en: enRes.data.prompt || ''
    }
  } catch (e) {
    console.error('Failed to load system prompt config', e)
    ElMessage.error(t('error.failed_load_config'))
  }
}

const handleSave = async () => {
  try {
    const lang = activeTab.value
    const requestData: any = {
      prompt: config.value[lang as 'cn' | 'en'],
      lang
    }
    // If deviceId is provided, include it to save device-specific prompt
    if (props.deviceId) {
      requestData.device_id = props.deviceId
    }
    await api.post('/agent/system-prompt', requestData)
    ElMessage.success(t('settings.saved'))
    visible.value = false
  } catch (e) {
    console.error('Failed to save system prompt config', e)
    ElMessage.error(t('error.failed_save_config'))
  }
}

const handleReset = async () => {
  try {
    const lang = activeTab.value
    const deviceParam = props.deviceId ? `&device_id=${props.deviceId}` : ''
    await api.post(`/agent/system-prompt/reset?lang=${lang}${deviceParam}`)
    await loadConfig()
    ElMessage.success(t('success.config_reset'))
  } catch (e) {
    console.error('Failed to reset system prompt config', e)
    ElMessage.error(t('error.failed_reset_config'))
  }
}

const handleCancel = () => {
  visible.value = false
}

const handleAssistantApply = (optimizedPrompt: string) => {
  const lang = activeTab.value as 'cn' | 'en'
  config.value[lang] = optimizedPrompt
  ElMessage.success(t('settings.prompt_assistant_applied'))
}
</script>


