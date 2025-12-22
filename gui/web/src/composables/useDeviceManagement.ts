import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import axios from 'axios'

export function useDeviceManagement(
  apiBaseUrl: string,
  activeDeviceId: Ref<string>,
  deviceAliases: Ref<Record<string, string>>
) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const devices = ref<any[]>([])
  const loadingDevices = ref(false)
  const apiConnected = ref(true)  // Track HTTP API connection status

  const checkApiHealth = async (): Promise<boolean> => {
    try {
      const res = await api.get('/system/health', { timeout: 3000 })
      return res.data?.status === 'ok'
    } catch (err) {
      return false
    }
  }

  const fetchDevices = async () => {
    loadingDevices.value = true
    try {
      // First check API health
      const isHealthy = await checkApiHealth()
      apiConnected.value = isHealthy
      
      if (!isHealthy) {
        console.warn('[DeviceManagement] API health check failed')
        // Don't show error message immediately, just mark as disconnected
        return
      }
      
      const res = await api.get('/devices/')
      devices.value = res.data.map((d: any) => ({
        ...d,
        displayName: deviceAliases.value[d.id] || d.model,
        brand: d.brand || null
      }))
      console.log('Fetched devices:', devices.value)
      apiConnected.value = true
      
      if (devices.value.length > 0) {
        const current = devices.value.find((d: any) => d.id === activeDeviceId.value)
        if (!current || current.status === 'offline') {
          activeDeviceId.value = ''
          const next = devices.value.find((d: any) => d.status !== 'offline')
          if (next) {
            selectDevice(next)
          }
        }
      } else {
        activeDeviceId.value = ''
      }
    } catch (err: any) {
      apiConnected.value = false
      console.error('[DeviceManagement] Failed to fetch devices:', err)
      // Only show error if it's not a network error (which might be temporary)
      if (err.code !== 'ECONNREFUSED' && err.code !== 'ERR_NETWORK') {
        ElMessage.error(t('error.failed_connect_backend'))
      }
    } finally {
      loadingDevices.value = false
    }
  }

  const selectDevice = async (device: any) => {
    if (device.status === 'offline') {
      ElMessage.warning(t('error.cannot_select_offline'))
      return
    }
    try {
      await api.post('/devices/select', { device_id: device.id, type: device.type })
      activeDeviceId.value = device.id
    } catch (err) {
      ElMessage.error(t('error.failed_select_device'))
    }
  }

  const deleteDevice = async (device: any) => {
    try {
      await api.delete(`/devices/${device.id}`)
      devices.value = devices.value.filter(d => d.id !== device.id)
      if (activeDeviceId.value === device.id) {
        activeDeviceId.value = ''
      }
      ElMessage.success(t('success.device_removed'))
    } catch (err) {
      ElMessage.error(t('error.failed_remove_device'))
    }
  }

  const handleDeviceRenamed = async (device: any, newName: string) => {
    await db.saveDeviceAlias(device.id, newName)
    deviceAliases.value[device.id] = newName
    const idx = devices.value.findIndex(d => d.id === device.id)
    if (idx !== -1) {
      devices.value[idx].displayName = newName
    }
  }

  return {
    devices,
    loadingDevices,
    apiConnected,
    fetchDevices,
    selectDevice,
    deleteDevice,
    handleDeviceRenamed,
    checkApiHealth
  }
}

