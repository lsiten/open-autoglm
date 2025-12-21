import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import axios from 'axios'
import { detectPlatform } from '../utils/platformDetector'

export function useConfigManagement(apiBaseUrl: string) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const showAppMatchingConfig = ref(false)
  const appMatchingConfig = ref<{
    system_app_mappings: Record<string, Array<{package: string, platform?: string}>>,
    llm_prompt_template: string
  }>({
    system_app_mappings: {},
    llm_prompt_template: ''
  })

  const showSystemPromptConfig = ref(false)
  const systemPromptConfig = ref({
    cn: '',
    en: ''
  })

  const loadAppMatchingConfig = async () => {
    try {
      const res = await api.get('/agent/app-matching-config')
      const mappings = res.data.system_app_mappings || {}
      const convertedMappings: Record<string, Array<{package: string, platform?: string}>> = {}
      for (const [keyword, packages] of Object.entries(mappings)) {
        if (Array.isArray(packages)) {
          convertedMappings[keyword] = packages.map((pkg: any) => {
            if (typeof pkg === 'string') {
              return { package: pkg, platform: detectPlatform(pkg) }
            }
            return { package: pkg.package || '', platform: pkg.platform || detectPlatform(pkg.package || '') }
          })
        }
      }
      appMatchingConfig.value = {
        system_app_mappings: convertedMappings,
        llm_prompt_template: res.data.llm_prompt_template || ''
      }
    } catch (e) {
      console.error('Failed to load app matching config', e)
      ElMessage.error(t('error.failed_load_config'))
    }
  }

  const saveAppMatchingConfig = async () => {
    try {
      const configToSave = {
        system_app_mappings: appMatchingConfig.value.system_app_mappings,
        llm_prompt_template: appMatchingConfig.value.llm_prompt_template
      }
      await api.post('/agent/app-matching-config', configToSave)
      ElMessage.success(t('success.config_saved'))
      showAppMatchingConfig.value = false
    } catch (e) {
      console.error('Failed to save app matching config', e)
      ElMessage.error(t('error.failed_save_config'))
    }
  }

  const resetAppMatchingConfig = async () => {
    try {
      const res = await api.get('/agent/app-matching-config')
      ElMessage.info(t('settings.reset_not_implemented'))
    } catch (e) {
      console.error('Failed to reset config', e)
    }
  }

  const loadSystemPromptConfig = async () => {
    try {
      const resCn = await api.get('/agent/system-prompt?lang=cn')
      const resEn = await api.get('/agent/system-prompt?lang=en')
      systemPromptConfig.value = {
        cn: resCn.data.prompt || '',
        en: resEn.data.prompt || ''
      }
    } catch (e) {
      console.error('Failed to load system prompt config', e)
      ElMessage.error(t('error.failed_load_config'))
    }
  }

  const saveSystemPromptConfig = async () => {
    try {
      await api.post('/agent/system-prompt', {
        prompt: systemPromptConfig.value.cn,
        lang: 'cn'
      })
      await api.post('/agent/system-prompt', {
        prompt: systemPromptConfig.value.en,
        lang: 'en'
      })
      ElMessage.success(t('success.config_saved'))
      showSystemPromptConfig.value = false
    } catch (e) {
      console.error('Failed to save system prompt config', e)
      ElMessage.error(t('error.failed_save_config'))
    }
  }

  const resetSystemPromptConfig = async () => {
    try {
      await api.post('/agent/system-prompt/reset?lang=cn')
      await api.post('/agent/system-prompt/reset?lang=en')
      await loadSystemPromptConfig()
      ElMessage.success(t('success.config_reset'))
    } catch (e) {
      console.error('Failed to reset system prompt config', e)
      ElMessage.error(t('error.failed_reset_config'))
    }
  }

  return {
    showAppMatchingConfig,
    appMatchingConfig,
    showSystemPromptConfig,
    systemPromptConfig,
    loadAppMatchingConfig,
    saveAppMatchingConfig,
    resetAppMatchingConfig,
    loadSystemPromptConfig,
    saveSystemPromptConfig,
    resetSystemPromptConfig
  }
}

