import { ref, type Ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

export function useConnectionWizard(
  apiBaseUrl: string,
  fetchDevices: () => Promise<void>,
  devices: Ref<any[]>
) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const wizardStep = ref(1)
  const wizardType = ref<'usb' | 'wifi' | 'webrtc' | ''>('')
  const checkingUsb = ref(false)
  const usbStatus = ref<'found' | 'not_found' | ''>('')
  const enablingWifi = ref(false)
  const connectingWifi = ref(false)
  const wifiIp = ref('')
  const webrtcUrl = ref('')

  const checkUsbConnection = async () => {
    checkingUsb.value = true
    usbStatus.value = ''
    try {
      await fetchDevices()
      if (devices.value.length > 0) {
        usbStatus.value = 'found'
        setTimeout(() => wizardStep.value = 3, 1000)
      } else {
        usbStatus.value = 'not_found'
      }
    } catch (e) {
      usbStatus.value = 'not_found'
    } finally {
      checkingUsb.value = false
    }
  }

  const enableWifiMode = async () => {
    enablingWifi.value = true
    try {
      const res = await api.post('/devices/wifi/enable')
      ElMessage.success(t('success.wifi_enabled'))
      if (res.data.ip) {
        wifiIp.value = res.data.ip
      }
    } catch (err: any) {
      ElMessage.error(err.response?.data?.detail || t('error.failed_enable_wifi'))
    } finally {
      enablingWifi.value = false
    }
  }

  const connectWifi = async () => {
    connectingWifi.value = true
    try {
      await api.post('/devices/connect', { address: wifiIp.value, type: 'adb' })
      ElMessage.success(t('success.connected_wifi'))
      wizardStep.value = 3
      fetchDevices()
    } catch (err: any) {
      ElMessage.error(err.response?.data?.detail || t('error.connection_failed'))
    } finally {
      connectingWifi.value = false
    }
  }

  const connectWebRTC = async () => {
    try {
      const res = await api.post('/devices/webrtc/init')
      webrtcUrl.value = res.data.url
      const poll = setInterval(async () => {
        if (wizardStep.value !== 2 || wizardType.value !== 'webrtc') {
          clearInterval(poll)
          return
        }
        try {
          const res = await api.get('/devices/')
          devices.value = res.data
          const found = devices.value.find((d: any) => d.type === 'webrtc' && d.status !== 'offline')
          if (found) {
            ElMessage.success(t('success.webrtc_connected'))
            wizardStep.value = 3
            clearInterval(poll)
          }
        } catch (e) { }
      }, 2000)
    } catch (err: any) {
      console.error(err)
      ElMessage.error(t('error.failed_init_webrtc'))
    }
  }

  watch([wizardStep, wizardType], ([newStep, newType]) => {
    if (newStep === 2 && newType === 'webrtc') {
      connectWebRTC()
    }
  })

  const handleWizardNext = () => {
    if (wizardStep.value < 3) {
      wizardStep.value++
    }
  }

  const handleWizardPrev = () => {
    if (wizardStep.value > 1) {
      wizardStep.value--
    } else {
      wizardStep.value = 1
      wizardType.value = ''
      usbStatus.value = ''
      wifiIp.value = ''
      webrtcUrl.value = ''
    }
  }

  const finishWizard = () => {
    wizardStep.value = 1
    wizardType.value = ''
    usbStatus.value = ''
    wifiIp.value = ''
    webrtcUrl.value = ''
  }

  return {
    wizardStep,
    wizardType,
    checkingUsb,
    usbStatus,
    enablingWifi,
    connectingWifi,
    wifiIp,
    webrtcUrl,
    checkUsbConnection,
    enableWifiMode,
    connectWifi,
    handleWizardNext,
    handleWizardPrev,
    finishWizard
  }
}

