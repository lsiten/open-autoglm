import { ref, type Ref, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import { v4 as uuidv4 } from 'uuid'
import axios from 'axios'

export function useTaskManagement(
  apiBaseUrl: string,
  activeDeviceId: Ref<string>,
  activeTaskId: Ref<string | null>,
  sessions: Ref<any[]>,
  backgroundTasks: Ref<any[]>,
  chatHistory: Ref<any[]>,
  taskStatuses: Ref<Record<string, string>>,
  allApps: Ref<Array<{name: string, package?: string, type: string}>>,
  isBackgroundTask: Ref<boolean>,
  activeTask: Ref<any>,
  convertLogsToChat: (logs: any[]) => any[],
  scrollToBottom: () => void,
  fetchDeviceApps: (deviceId: string) => Promise<void>
) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const startingTask = ref(false)
  const stoppingTask = ref(false)
  const hasMoreMessages = ref(true)
  const isLoadingMore = ref(false)
  const MESSAGES_PER_PAGE = 20
  const taskLogRefreshInterval = ref<NodeJS.Timeout | null>(null)

  const fetchData = async () => {
    if (!activeDeviceId.value) return
    
    const allSessions = await db.getSessions()
    sessions.value = allSessions
      .filter((s: any) => s.deviceId === activeDeviceId.value)
      .sort((a: any, b: any) => (b.createdAt || 0) - (a.createdAt || 0))
    
    try {
      const res = await api.get(`/tasks/${activeDeviceId.value}`)
      backgroundTasks.value = res.data.filter((t: any) => t.type === 'background')
      for (const task of backgroundTasks.value) {
        if (task.status) {
          taskStatuses.value[task.id] = task.status
        }
      }
    } catch (e) {
      console.error('Failed to fetch tasks', e)
      backgroundTasks.value = []
    }

    if (!activeTaskId.value) {
      let emptySession = null
      for (const session of sessions.value) {
        const msgs = await db.getMessages(session.id)
        if (msgs.length === 0) {
          emptySession = session
          break
        }
      }
      if (emptySession) {
        selectTask(emptySession)
      } else {
        await createDefaultSession()
      }
    }
  }

  const createDefaultSession = async () => {
    const id = uuidv4()
    const session = {
      id,
      name: `${t('debug.session_prefix')}${sessions.value.length + 1}`,
      type: 'chat',
      deviceId: activeDeviceId.value,
      createdAt: Date.now()
    }
    await db.addSession(session)
    sessions.value.unshift(session)
    selectTask(session)
  }

  const createTask = async (taskData: any) => {
    if (!activeDeviceId.value) return

    if (taskData.type === 'chat') {
      const id = uuidv4()
      const session = {
        id,
        name: taskData.name || `${t('debug.session_prefix')}${sessions.value.length + 1}`,
        type: 'chat',
        deviceId: activeDeviceId.value,
        createdAt: Date.now()
      }
      await db.addSession(session)
      sessions.value.unshift(session)
      selectTask(session)
    } else {
      try {
        const res = await api.post('/tasks/', {
          device_id: activeDeviceId.value,
          ...taskData
        })
        await fetchData()
        selectTask(res.data.task)
      } catch (e: any) {
        ElMessage.error(e.response?.data?.detail || t('error.failed_create_task'))
      }
    }
  }

  const refreshTaskLogs = async () => {
    if (!activeTaskId.value || !isBackgroundTask.value) return
    try {
      const res = await api.get(`/tasks/detail/${activeTaskId.value}`)
      const details = res.data.task
      chatHistory.value = convertLogsToChat(details.logs)
      if (details.details) {
        const hasDetails = chatHistory.value.some((msg: any) => msg.role === 'user' && msg.content === details.details)
        if (!hasDetails) {
          chatHistory.value.unshift({ role: 'user', content: details.details })
        }
      }
      scrollToBottom()
    } catch (e) {
      console.error('Failed to refresh task logs', e)
    }
  }

  const selectTask = async (task: any) => {
    if (taskLogRefreshInterval.value) {
      clearInterval(taskLogRefreshInterval.value)
      taskLogRefreshInterval.value = null
    }
    
    activeTaskId.value = task.id
    chatHistory.value = []
    hasMoreMessages.value = true
    
    if (!taskStatuses.value[task.id]) {
      if (task.type === 'background' && task.status) {
        taskStatuses.value[task.id] = task.status
      } else {
        taskStatuses.value[task.id] = 'idle'
      }
    }
    
    if (task.type === 'chat') {
      await loadMessages(task.id)
    } else {
      await refreshTaskLogs()
      taskLogRefreshInterval.value = setInterval(() => {
        if (isBackgroundTask.value && activeTaskId.value === task.id) {
          refreshTaskLogs()
        }
      }, 5000)
    }
    scrollToBottom()
  }

  const loadMessages = async (sessionId: string, beforeId?: number) => {
    try {
      const msgs = await db.getMessages(sessionId, MESSAGES_PER_PAGE, beforeId)
      if (msgs.length < MESSAGES_PER_PAGE) {
        hasMoreMessages.value = false
      }
      
      // Filter out empty messages
      const filteredMsgs = msgs.filter((msg: any) => {
        // User messages always have content, so keep them
        if (msg.role === 'user') {
          return true
        }
        
        // Agent messages: filter out completely empty ones
        const hasThought = msg.thought && msg.thought.trim()
        const hasContent = msg.content && msg.content.trim()
        const hasAction = msg.action && (
          typeof msg.action === 'string' ? msg.action.trim() : 
          typeof msg.action === 'object' ? Object.keys(msg.action).length > 0 : 
          false
        )
        const hasType = msg.type // interaction messages
        const hasSpecialFlags = msg.isInfo || msg.isFailed || msg.isError
        const hasScreenshot = msg.screenshot
        const isThinking = msg.isThinking === true
        
        // For status messages, check if they have valid status data
        const hasValidStatus = hasType === 'status' && (
          (msg.statusType && (msg.statusType.trim ? msg.statusType.trim() : msg.statusType)) &&
          ((msg.status && msg.status.trim()) || (msg.message && msg.message.trim()) || msg.progress !== undefined || msg.progress !== null)
        )
        
        // For other type messages (not status), keep them
        const hasOtherType = hasType && hasType !== 'status'
        
        return hasThought || hasContent || hasAction || hasValidStatus || hasOtherType || hasSpecialFlags || hasScreenshot || isThinking
      })
      
      if (beforeId) {
        chatHistory.value = [...filteredMsgs, ...chatHistory.value]
      } else {
        chatHistory.value = filteredMsgs
      }
    } catch (e) {
      console.error('Failed to load messages', e)
    }
  }

  const handleChatScroll = async (e: Event) => {
    const target = e.target as HTMLElement
    if (target.scrollTop === 0 && hasMoreMessages.value && !isLoadingMore.value && activeTaskId.value) {
      isLoadingMore.value = true
      const oldestId = chatHistory.value[0]?.id
      const oldScrollHeight = target.scrollHeight
      
      if (oldestId) {
        await loadMessages(activeTaskId.value, oldestId)
        nextTick(() => {
          const newScrollHeight = target.scrollHeight
          const diff = newScrollHeight - oldScrollHeight
          if (diff > 0) {
            target.scrollTop = diff
          }
        })
      }
      isLoadingMore.value = false
    }
  }

  const deleteTask = async (task: any) => {
    if (task.type === 'chat') {
      await db.deleteSession(task.id)
      sessions.value = sessions.value.filter(s => s.id !== task.id)
      delete taskStatuses.value[task.id]
      if (activeTaskId.value === task.id) {
        activeTaskId.value = null
        chatHistory.value = []
      }
      ElMessage.success(t('success.session_deleted'))
    } else {
      try {
        await api.delete(`/tasks/${task.id}`)
        backgroundTasks.value = backgroundTasks.value.filter(t => t.id !== task.id)
        delete taskStatuses.value[task.id]
        if (activeTaskId.value === task.id) {
          activeTaskId.value = null
          chatHistory.value = []
        }
        ElMessage.success(t('success.task_deleted'))
      } catch (e) {
        ElMessage.error(t('error.failed_delete_task'))
      }
    }
  }

  const sendMessage = async (input: Ref<string>, sending: Ref<boolean>) => {
    if (!input.value || !activeDeviceId.value || !activeTaskId.value) return
    
    if (isBackgroundTask.value) {
      ElMessage.warning(t('task.cannot_send_message_to_background_task'))
      return
    }

    if (input.value === '/debug-confirm') {
      input.value = ''
      const msg: any = {
        role: 'agent',
        type: 'confirm',
        title: t('debug.permission_request'),
        content: t('debug.install_app_request'),
        options: [
          { label: t('common.deny'), value: 'No', type: 'danger' },
          { label: t('common.allow'), value: 'Yes', type: 'success' }
        ],
        sessionId: activeTaskId.value,
        submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
    }
    if (input.value === '/debug-input') {
      input.value = ''
      const msg: any = {
        role: 'agent',
        type: 'input',
        title: t('debug.sms_verification'),
        content: t('debug.enter_verification_code'),
        placeholder: '123456',
        sessionId: activeTaskId.value,
        submitted: false
      }
      chatHistory.value.push(msg)
      db.addMessage(msg).then(id => msg.id = id)
      scrollToBottom()
      return
    }
    
    const prompt = input.value
    input.value = ''
    sending.value = true
    
    const currentTask = activeTask.value
    if (currentTask && currentTask.type === 'chat' && currentTask.name.startsWith(t('debug.session_prefix'))) {
      const newName = prompt.length > 20 ? prompt.substring(0, 20) + '...' : prompt
      await db.updateSession(currentTask.id, { name: newName })
      currentTask.name = newName
    }

    const userMsg = { role: 'user', content: prompt, sessionId: activeTaskId.value }
    const id1 = await db.addMessage(userMsg)
    chatHistory.value.push({ ...userMsg, id: id1 })
    
    // Don't create empty thinking message - wait for backend to send first thought token
    // The first thought token will create the thinking message automatically
    
    scrollToBottom()

    try {
      try {
        await api.get(`/tasks/detail/${activeTaskId.value}`)
        await api.put(`/tasks/${activeTaskId.value}`, {
          name: currentTask?.name || t('debug.chat_sync'),
          details: prompt
        })
      } catch (e) {
        await api.post('/tasks/', {
          id: activeTaskId.value,
          device_id: activeDeviceId.value,
          type: 'chat',
          name: currentTask?.name || t('debug.chat_sync'),
          details: prompt
        })
      }

      if (allApps.value.length === 0 && activeDeviceId.value) {
        await fetchDeviceApps(activeDeviceId.value)
      }

      await api.post(`/tasks/${activeTaskId.value}/start`, { 
        prompt,
        installed_apps: allApps.value.map(a => ({ name: a.name, package: a.package }))
      })
      if (activeTaskId.value) {
        taskStatuses.value[activeTaskId.value] = 'running'
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || t('error.failed_start_task')
      ElMessage.error(errorMsg)
      chatHistory.value.pop()
      const errM = { role: 'agent', content: `${t('common.error_prefix')}${errorMsg}`, sessionId: activeTaskId.value }
      chatHistory.value.push(errM)
      db.addMessage(errM)
    } finally {
      sending.value = false
    }
  }

  const startBackgroundTask = async () => {
    if (!activeTaskId.value || !activeDeviceId.value) return
    
    startingTask.value = true
    try {
      if (allApps.value.length === 0 && activeDeviceId.value) {
        await fetchDeviceApps(activeDeviceId.value)
      }
      
      await api.post(`/tasks/${activeTaskId.value}/start`, {
        installed_apps: allApps.value.map(a => ({ name: a.name, package: a.package }))
      })
      if (activeTaskId.value) {
        taskStatuses.value[activeTaskId.value] = 'running'
      }
      await fetchData()
      ElMessage.success(t('success.task_started'))
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || t('error.failed_start_task')
      ElMessage.error(errorMsg)
    } finally {
      startingTask.value = false
    }
  }

  const stopTask = async () => {
    stoppingTask.value = true
    try {
      if (activeTaskId.value) {
        await api.post(`/tasks/${activeTaskId.value}/stop`)
        taskStatuses.value[activeTaskId.value] = 'idle'
      } else {
        await api.post('/agent/stop')
        taskStatuses.value = {}
      }
      if (isBackgroundTask.value) {
        await fetchData()
      }
      ElMessage.warning(t('success.task_stopped'))
    } catch (err: any) {
      ElMessage.error(err.response?.data?.detail || t('error.failed_stop_task'))
    } finally {
      stoppingTask.value = false
    }
  }

  return {
    startingTask,
    stoppingTask,
    hasMoreMessages,
    isLoadingMore,
    taskLogRefreshInterval,
    fetchData,
    createTask,
    selectTask,
    deleteTask,
    loadMessages,
    handleChatScroll,
    refreshTaskLogs,
    sendMessage,
    startBackgroundTask,
    stopTask
  }
}

