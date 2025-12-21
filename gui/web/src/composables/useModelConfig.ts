import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import axios from 'axios'

export function useModelConfig(apiBaseUrl: string) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const showConfig = ref(false)
  const selectedProvider = ref('vllm')
  const config = ref({
    baseUrl: 'http://localhost:8080/v1',
    model: 'autoglm-phone-9b',
    apiKey: 'EMPTY'
  })

  const updateProviderConfig = (val: string) => {
    switch (val) {
      case 'vllm':
        config.value.baseUrl = 'http://localhost:8080/v1'
        config.value.model = 'autoglm-phone-9b'
        config.value.apiKey = 'EMPTY'
        break
      case 'ollama':
        config.value.baseUrl = 'http://localhost:11434/v1'
        config.value.model = 'autoglm-phone-9b'
        config.value.apiKey = 'ollama'
        break
      case 'bailian':
        config.value.baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        config.value.model = 'qwen-plus'
        config.value.apiKey = ''
        break
      case 'gemini':
        config.value.baseUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/'
        config.value.model = 'gemini-1.5-flash'
        config.value.apiKey = ''
        break
      case 'claude':
        config.value.baseUrl = 'https://api.anthropic.com/v1'
        config.value.model = 'claude-3-haiku-20240307'
        config.value.apiKey = ''
        break
    }
  }

  const syncConfigToBackend = async () => {
    try {
      await api.post('/agent/config', {
        base_url: config.value.baseUrl,
        model: config.value.model,
        api_key: config.value.apiKey
      })
      console.log("Config synced to backend")
    } catch (e) {
      console.error("Failed to sync config", e)
    }
  }

  const saveConfig = async () => {
    const configToSave = { 
      ...config.value, 
      selectedProvider: selectedProvider.value 
    }
    await db.saveConfig(configToSave)
    await syncConfigToBackend()
    ElMessage.success(t('success.config_saved'))
    showConfig.value = false
  }

  return {
    showConfig,
    selectedProvider,
    config,
    updateProviderConfig,
    syncConfigToBackend,
    saveConfig
  }
}

