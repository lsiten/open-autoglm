import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'

export function useWebSocket(
  wsBaseUrl: string,
  activeTaskId: Ref<string | null>,
  chatHistory: Ref<any[]>,
  taskStatuses: Ref<Record<string, string>>,
  isBackgroundTask: Ref<boolean>,
  onScreenshot?: (data: string) => void,
  onStatusUpdate?: (taskId: string, status: string) => void,
  onInteraction?: (data: any) => void,
  onLog?: (data: any) => void,
  onOpen?: () => void
) {
  const { t } = useI18n()
  const wsConnected = ref(false)
  const wsError = ref('')

  const connectWS = () => {
    console.log(`[Debug] Connecting WS to: ${wsBaseUrl}`)
    wsError.value = ''
    const ws = new WebSocket(wsBaseUrl)
    
    ws.onopen = () => { 
      console.log('[Debug] WS Connected')
      wsConnected.value = true 
      wsError.value = ''
      if (onOpen) onOpen()
    }
    
    ws.onclose = (e) => { 
      console.log('[Debug] WS Closed:', e.code, e.reason)
      wsConnected.value = false
      if (!wsError.value) wsError.value = `Disconnected (Code: ${e.code})`
      setTimeout(connectWS, 3000) 
    }
    
    ws.onerror = (e) => { 
      console.error('[Debug] WS Error:', e)
      wsError.value = t('error.connection_blocked')
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      handleWSMessage(data)
    }
  }

  const handleWSMessage = (data: any) => {
    if (data.type === 'log') {
      if (activeTaskId.value && data.taskId && data.taskId !== activeTaskId.value) {
        return
      }
      if (isBackgroundTask.value && data.taskId === activeTaskId.value) {
        if (onLog) onLog(data)
      } else {
        if (onLog) onLog(data)
      }
    } else if (data.type === 'screenshot') {
      if (onScreenshot) {
        onScreenshot(data.data)
      }
    } else if (data.type === 'status') {
      if (data.taskId) {
        taskStatuses.value[data.taskId] = data.data.state
        if (onStatusUpdate) {
          onStatusUpdate(data.taskId, data.data.state)
        }
      }
    } else if (data.type === 'interaction') {
      if (onInteraction) {
        onInteraction(data)
      }
    }
  }

  return {
    wsConnected,
    wsError,
    connectWS
  }
}

