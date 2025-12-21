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

  const fetchDevices = async () => {
    loadingDevices.value = true
    try {
      const res = await api.get('/devices/')
      devices.value = res.data.map((d: any) => ({
        ...d,
        displayName: deviceAliases.value[d.id] || d.model,
        brand: d.brand || null
      }))
      console.log('Fetched devices:', devices.value)
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
    } catch (err) {
      ElMessage.error(t('error.failed_connect_backend'))
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
    fetchDevices,
    selectDevice,
    deleteDevice,
    handleDeviceRenamed
  }
}

