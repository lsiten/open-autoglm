import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

export interface Recording {
  id: string
  name: string
  keywords: string[]
  device_id: string
  device_type: string
  action_count: number
  created_at: string
  updated_at: string
  description?: string
}

export function useRecording(apiBaseUrl: string, activeDeviceId: Ref<string>) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  
  const isRecording = ref(false)
  const recordingId = ref<string | null>(null)
  const actionCount = ref(0)
  const recordings = ref<Recording[]>([])
  const loading = ref(false)
  const startingRecording = ref(false)

  const startRecording = async (showToast: boolean = true) => {
    if (!activeDeviceId.value) {
      if (showToast) {
        ElMessage.warning(t('recording.select_device_first'))
      }
      return false
    }

    startingRecording.value = true
    try {
      // Get device type
      const device = await api.get(`/devices/${activeDeviceId.value}`)
      const deviceType = device.data.type || 'adb'
      
      const response = await api.post('/recordings/start', {
        device_id: activeDeviceId.value,
        device_type: deviceType
      })
      
      isRecording.value = true
      recordingId.value = response.data.recording_id
      actionCount.value = 0
      // Only show toast when user manually starts recording
      if (showToast) {
        ElMessage.success(t('recording.started'))
      }
      return true
    } catch (e: any) {
      console.error('Failed to start recording', e)
      if (showToast) {
        ElMessage.error(e.response?.data?.detail || t('recording.start_failed'))
      }
      return false
    } finally {
      startingRecording.value = false
    }
  }

  const stopRecording = async () => {
    if (!activeDeviceId.value || !isRecording.value) {
      return null
    }

    try {
      const response = await api.post(`/recordings/stop/${activeDeviceId.value}`)
      isRecording.value = false
      const id = response.data.recording_id
      recordingId.value = id
      return id
    } catch (e: any) {
      console.error('Failed to stop recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.stop_failed'))
      return null
    }
  }

  const saveRecording = async (name: string, keywords: string[], description?: string) => {
    if (!recordingId.value) {
      ElMessage.error(t('recording.no_recording_to_save'))
      return false
    }

    try {
      await api.post('/recordings/save', {
        recording_id: recordingId.value,
        name,
        keywords,
        description
      })
      
      ElMessage.success(t('recording.saved'))
      recordingId.value = null
      actionCount.value = 0
      await fetchRecordings()
      return true
    } catch (e: any) {
      console.error('Failed to save recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.save_failed'))
      return false
    }
  }

  const fetchRecordings = async (deviceId?: string, keyword?: string) => {
    loading.value = true
    try {
      const params: any = {}
      if (deviceId) params.device_id = deviceId
      if (keyword) params.keyword = keyword
      
      const response = await api.get('/recordings/list', { params })
      recordings.value = response.data.recordings || []
    } catch (e: any) {
      console.error('Failed to fetch recordings', e)
      ElMessage.error(e.response?.data?.detail || t('recording.fetch_failed'))
    } finally {
      loading.value = false
    }
  }

  const deleteRecording = async (recordingId: string) => {
    try {
      await api.delete(`/recordings/${recordingId}`)
      ElMessage.success(t('recording.deleted'))
      await fetchRecordings()
      return true
    } catch (e: any) {
      console.error('Failed to delete recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.delete_failed'))
      return false
    }
  }

  const executeRecording = async (recordingId: string, targetDeviceId?: string) => {
    try {
      await api.post(`/recordings/${recordingId}/execute`, {
        device_id: targetDeviceId || activeDeviceId.value
      })
      ElMessage.success(t('recording.executed'))
      return true
    } catch (e: any) {
      console.error('Failed to execute recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.execute_failed'))
      return false
    }
  }

  const getRecordingStatus = async (autoRestart: boolean = false) => {
    if (!activeDeviceId.value) {
      isRecording.value = false
      return
    }

    try {
      const response = await api.get(`/recordings/status/${activeDeviceId.value}`)
      const wasRecording = isRecording.value
      isRecording.value = response.data.is_recording
      recordingId.value = response.data.recording_id
      actionCount.value = response.data.action_count || 0
      
      // If we thought we were recording but backend says we're not, and autoRestart is enabled
      // This can happen if backend restarted or state was lost
      if (wasRecording && !response.data.is_recording && autoRestart) {
        console.log('[Recording] State lost, auto-restarting recording...')
        await startRecording(false) // Restart without showing toast
      }
    } catch (e) {
      console.error('Failed to get recording status', e)
    }
  }

  const previewRecording = async (recordingId: string) => {
    try {
      const response = await api.get(`/recordings/preview/${recordingId}`)
      return response.data
    } catch (e: any) {
      console.error('Failed to preview recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.preview_failed'))
      return null
    }
  }

  const debugRecording = async (recordingId: string) => {
    try {
      await api.post(`/recordings/${recordingId}/execute`, {
        device_id: activeDeviceId.value
      })
      ElMessage.success(t('recording.debug_executed'))
      return true
    } catch (e: any) {
      console.error('Failed to debug recording', e)
      ElMessage.error(e.response?.data?.detail || t('recording.debug_failed'))
      return false
    }
  }

  const resetRecordingState = async (recordingId: string) => {
    try {
      const response = await api.post(`/recordings/${recordingId}/reset`, {
        device_id: activeDeviceId.value
      })
      return { success: true, message: response.data.message }
    } catch (e: any) {
      console.error('Failed to reset recording state', e)
      return { success: false, message: e.response?.data?.detail || t('recording.reset_failed') }
    }
  }

  const executeSingleAction = async (recordingId: string, actionIndex: number) => {
    try {
      const response = await api.post(`/recordings/${recordingId}/execute-action`, {
        action_index: actionIndex,
        device_id: activeDeviceId.value
      })
      return { success: true, message: response.data.message }
    } catch (e: any) {
      console.error('Failed to execute single action', e)
      return { success: false, message: e.response?.data?.detail || t('recording.execute_action_failed') }
    }
  }

  const replaceAction = async (recordingId: string, actionIndex: number, newAction: any) => {
    try {
      const response = await api.post(`/recordings/${recordingId}/replace-action`, {
        action_index: actionIndex,
        new_action: newAction,
        device_id: activeDeviceId.value
      })
      return { success: true, action: response.data.action }
    } catch (e: any) {
      console.error('Failed to replace action', e)
      return { success: false, message: e.response?.data?.detail || t('recording.replace_action_failed') }
    }
  }

  return {
    isRecording,
    recordingId,
    actionCount,
    recordings,
    loading,
    startingRecording,
    startRecording,
    stopRecording,
    saveRecording,
    fetchRecordings,
    deleteRecording,
    executeRecording,
    getRecordingStatus,
    previewRecording,
    debugRecording,
    resetRecordingState,
    executeSingleAction,
    replaceAction
  }
}

