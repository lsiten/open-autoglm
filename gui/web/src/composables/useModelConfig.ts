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
    // Preserve existing API key if it's already set (not empty and not default)
    const existingApiKey = config.value.apiKey
    const shouldPreserveApiKey = existingApiKey && existingApiKey !== 'EMPTY' && existingApiKey.trim() !== ''
    
    switch (val) {
      case 'vllm':
        config.value.baseUrl = 'http://localhost:8080/v1'
        config.value.model = 'autoglm-phone-9b'
        // Only set to EMPTY if no existing key, otherwise preserve
        if (!shouldPreserveApiKey) {
        config.value.apiKey = 'EMPTY'
        }
        break
      case 'ollama':
        config.value.baseUrl = 'http://localhost:11434/v1'
        config.value.model = 'autoglm-phone-9b'
        // Only set default if no existing key, otherwise preserve
        if (!shouldPreserveApiKey) {
        config.value.apiKey = 'ollama'
        }
        break
      case 'bailian':
        config.value.baseUrl = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
        config.value.model = 'qwen-plus'
        // Only clear if no existing key, otherwise preserve
        if (!shouldPreserveApiKey) {
        config.value.apiKey = ''
        }
        break
      case 'gemini':
        config.value.baseUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/'
        // Default to Gemini 1.5 Flash (stable and widely available)
        // Gemini 3 may not be available in all regions yet
        config.value.model = 'gemini-1.5-flash'
        // Preserve existing API key for Gemini (important!)
        // Only clear if explicitly switching from another provider and no key exists
        if (!shouldPreserveApiKey) {
        config.value.apiKey = ''
        }
        break
      case 'claude':
        config.value.baseUrl = 'https://api.anthropic.com/v1'
        config.value.model = 'claude-3-haiku-20240307'
        // Only clear if no existing key, otherwise preserve
        if (!shouldPreserveApiKey) {
        config.value.apiKey = ''
        }
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
      baseUrl: config.value.baseUrl,
      model: config.value.model,
      apiKey: config.value.apiKey,  // Explicitly save API key
      selectedProvider: selectedProvider.value 
    }
    console.log('Saving config:', configToSave)
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

