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
  const wifiConnected = ref(false)
  const webrtcUrl = ref('')
  const webrtcConnected = ref(false)

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
    if (!wifiIp.value || !wifiIp.value.trim()) {
      ElMessage.error('请输入设备的IP地址')
      return
    }

    // Validate IP address format (basic check)
    const ipPattern = /^(\d{1,3}\.){3}\d{1,3}(:\d+)?$/
    if (!ipPattern.test(wifiIp.value.trim())) {
      ElMessage.error('IP地址格式不正确，请输入类似 192.168.1.5 或 192.168.1.5:5555 的格式')
      return
    }

    connectingWifi.value = true
    wifiConnected.value = false
    try {
      await api.post('/devices/connect', { address: wifiIp.value.trim(), type: 'adb' })
      
      // Wait a bit and verify the device is actually connected
      await new Promise(resolve => setTimeout(resolve, 1000))
      await fetchDevices()
      
      // Check if the device appears in the list
      const connectedDevice = devices.value.find((d: any) => {
        const deviceAddress = d.id.includes(':') ? d.id : `${d.id}:5555`
        const inputAddress = wifiIp.value.trim()
        const inputAddressWithPort = inputAddress.includes(':') ? inputAddress : `${inputAddress}:5555`
        return deviceAddress === inputAddressWithPort || d.id === inputAddress
      })
      
      if (connectedDevice && connectedDevice.status !== 'offline') {
        ElMessage.success(t('success.connected_wifi'))
        wifiConnected.value = true
      } else {
        ElMessage.warning('设备已连接，但可能尚未就绪，请稍候再试')
        wifiConnected.value = false
      }
    } catch (err: any) {
      // Extract detailed error message from backend
      let errorMsg = t('error.connection_failed')
      if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail
      } else if (err.response?.data?.message) {
        errorMsg = err.response.data.message
      } else if (err.message) {
        errorMsg = err.message
      }
      
      // Provide helpful suggestions based on common errors
      if (errorMsg.includes('timeout') || errorMsg.includes('Connection timeout')) {
        errorMsg = `连接超时: ${errorMsg}。请检查：\n1. 设备IP地址是否正确\n2. 设备是否已开启无线调试\n3. 设备和电脑是否在同一WiFi网络`
      } else if (errorMsg.includes('refused') || errorMsg.includes('unreachable')) {
        errorMsg = `无法连接到设备: ${errorMsg}。请检查：\n1. IP地址是否正确\n2. 设备是否已开启无线调试（adb tcpip 5555）\n3. 防火墙是否阻止了连接`
      }
      
      ElMessage.error(errorMsg)
      wifiConnected.value = false
    } finally {
      connectingWifi.value = false
    }
  }

  const connectWebRTC = async () => {
    webrtcConnected.value = false
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
            webrtcConnected.value = true
            ElMessage.success(t('success.webrtc_connected'))
            clearInterval(poll)
            // Don't auto-advance, let user click "Next" button
          }
        } catch (e) { }
      }, 2000)
    } catch (err: any) {
      console.error(err)
      ElMessage.error(t('error.failed_init_webrtc'))
      webrtcConnected.value = false
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
      wifiConnected.value = false
      webrtcUrl.value = ''
      webrtcConnected.value = false
    }
  }

  const finishWizard = () => {
    wizardStep.value = 1
    wizardType.value = ''
    usbStatus.value = ''
    wifiIp.value = ''
    wifiConnected.value = false
    webrtcUrl.value = ''
    webrtcConnected.value = false
  }

  return {
    wizardStep,
    wizardType,
    checkingUsb,
    usbStatus,
    enablingWifi,
    connectingWifi,
    wifiIp,
    wifiConnected,
    webrtcUrl,
    webrtcConnected,
    checkUsbConnection,
    enableWifiMode,
    connectWifi,
    handleWizardNext,
    handleWizardPrev,
    finishWizard
  }
}

