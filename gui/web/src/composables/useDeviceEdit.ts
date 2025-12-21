import { ref, type Ref } from 'vue'
import { db } from '../utils/db'

export function useDeviceEdit(
  devices: Ref<any[]>,
  deviceAliases: Ref<Record<string, string>>
) {
  const editingDeviceId = ref('')
  const editName = ref('')

  const startEdit = (device: any) => {
    editingDeviceId.value = device.id
    editName.value = device.displayName || device.model || device.id
  }

  const cancelEdit = () => {
    editingDeviceId.value = ''
    editName.value = ''
  }

  const saveDeviceName = async (device: any) => {
    if (editName.value.trim()) {
      const newName = editName.value.trim()
      await db.saveDeviceAlias(device.id, newName)
      deviceAliases.value[device.id] = newName
      const idx = devices.value.findIndex(d => d.id === device.id)
      if (idx !== -1) {
        devices.value[idx].displayName = newName
      }
    }
    cancelEdit()
  }

  return {
    editingDeviceId,
    editName,
    startEdit,
    cancelEdit,
    saveDeviceName
  }
}

