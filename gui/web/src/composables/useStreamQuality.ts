import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

export function useStreamQuality(apiBaseUrl: string) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const streamQuality = ref('auto')

  const updateStreamQuality = async (key: string, silent = false) => {
    streamQuality.value = key
    let q = 60
    let w = 480
    
    switch (key) {
      case '1080p': q = 85; w = 1080; break
      case '720p': q = 80; w = 720; break
      case '480p': q = 70; w = 480; break
      case '360p': q = 60; w = 360; break
      case 'auto': q = 85; w = 1080; break  // Higher default quality (was 50/360)
    }
    
    try {
      await api.post('/control/stream/settings', { quality: q, max_width: w })
      if (!silent) {
        const label = t('mirror.quality_' + key)
        ElMessage.success(t('success.quality_set', { quality: label }))
      }
    } catch (e) {
      // Silent fail
    }
  }

  return {
    streamQuality,
    updateStreamQuality
  }
}

