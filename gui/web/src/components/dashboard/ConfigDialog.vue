<template>
  <el-dialog 
    v-model="visible" 
    :title="t('settings.title')" 
    width="500px" 
    class="custom-dialog" 
    align-center
  >
    <el-form label-position="top">
      <el-form-item :label="t('settings.select_provider')">
        <el-select v-model="selectedProvider" @change="updateProviderConfig">
          <el-option :label="t('settings.provider_vllm')" value="vllm" />
          <el-option :label="t('settings.provider_ollama')" value="ollama" />
          <el-option :label="t('settings.provider_bailian')" value="bailian" />
          <el-option :label="t('settings.provider_gemini')" value="gemini" />
          <el-option :label="t('settings.provider_claude')" value="claude" />
          <el-option :label="t('settings.provider_custom')" value="custom" />
        </el-select>
      </el-form-item>
      
      <el-form-item :label="t('settings.base_url')">
        <el-input v-model="config.baseUrl" placeholder="e.g. http://localhost:8000/v1" />
      </el-form-item>
      <el-form-item :label="t('settings.model_name')">
        <el-input v-model="config.model" placeholder="e.g. autoglm-phone-9b" />
      </el-form-item>
      <el-form-item :label="t('settings.api_key')">
        <el-input v-model="config.apiKey" type="password" show-password placeholder="sk-..." />
        <div class="text-xs text-gray-500 mt-1" v-if="selectedProvider === 'vllm'">
          {{ t('settings.local_tip') }}
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="handleSave" class="!bg-blue-600 !border-none">
          {{ t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps<{
  modelValue: boolean
  config: {
    baseUrl: string
    model: string
    apiKey: string
  }
  selectedProvider?: string
  apiBaseUrl: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'update:config': [config: any]
  'update:provider': [provider: string]
  'save': []
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const config = ref({ ...props.config })
const selectedProvider = ref(props.selectedProvider || 'vllm')

watch(() => props.config, (newConfig) => {
  config.value = { ...newConfig }
}, { deep: true })

watch(() => props.selectedProvider, (newVal) => {
  if (newVal) {
    selectedProvider.value = newVal
  }
})

const updateProviderConfig = (val: string) => {
  selectedProvider.value = val
  const providerConfigs: Record<string, any> = {
    vllm: { baseUrl: 'http://localhost:8000/v1', model: 'autoglm-phone-9b', apiKey: 'EMPTY' },
    ollama: { baseUrl: 'http://localhost:11434/v1', model: 'llama2', apiKey: '' },
    bailian: { baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus', apiKey: '' },
    gemini: { baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/', model: 'gemini-1.5-flash', apiKey: '' },
    claude: { baseUrl: 'https://api.anthropic.com/v1', model: 'claude-3-haiku-20240307', apiKey: '' },
    custom: { baseUrl: '', model: '', apiKey: '' }
  }
  
  if (providerConfigs[val]) {
    Object.assign(config.value, providerConfigs[val])
    emit('update:config', { ...config.value })
    emit('update:provider', val)
  }
}

const handleSave = () => {
  emit('save')
  visible.value = false
}

const handleCancel = () => {
  visible.value = false
}
</script>

