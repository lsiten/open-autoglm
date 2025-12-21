import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

export function usePermissions(apiBaseUrl: string, activeDeviceId: Ref<string>) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const showPermissions = ref(false)
  const devicePermissions = ref({
    install_app: false,
    payment: false,
    wechat_reply: false,
    send_sms: false,
    make_call: false
  })

  const openPermissions = async () => {
    if (!activeDeviceId.value) return
    try {
      const res = await api.get(`/devices/${activeDeviceId.value}/permissions`)
      devicePermissions.value = res.data
      showPermissions.value = true
    } catch (e) {
      console.error('Failed to load permissions', e)
      devicePermissions.value = {
        install_app: false,
        payment: false,
        wechat_reply: false,
        send_sms: false,
        make_call: false
      }
      showPermissions.value = true
    }
  }

  const savePermissions = async () => {
    if (!activeDeviceId.value) return
    try {
      await api.post(`/devices/${activeDeviceId.value}/permissions`, devicePermissions.value)
      showPermissions.value = false
      ElMessage.success(t('settings.saved'))
    } catch (e) {
      console.error('Failed to save permissions', e)
      ElMessage.error(t('error.failed_save_permissions'))
    }
  }

  return {
    showPermissions,
    devicePermissions,
    openPermissions,
    savePermissions
  }
}

