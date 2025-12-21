import { type Ref } from 'vue'
import { db } from '../utils/db'

export function useMessageHandler(
  chatHistory: Ref<any[]>,
  activeTaskId: Ref<string | null>,
  isBackgroundTask: Ref<boolean>,
  scrollToBottom: () => void
) {
  const convertLogsToChat = (logs: any[]) => {
    const history: any[] = []
    let lastMsg: any = null
    
    // Sort logs by timestamp
    logs.sort((a, b) => a.timestamp - b.timestamp)
    
    for (const log of logs) {
      // Prepare screenshot data if present
      const screenshotData = log.screenshot ? `data:image/jpeg;base64,${log.screenshot}` : null
      
      if (log.level === 'thought') {
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
          lastMsg.thought += log.message
          // Update screenshot if provided
          if (screenshotData && !lastMsg.screenshot) {
            lastMsg.screenshot = screenshotData
          }
        } else {
          lastMsg = { 
            role: 'agent', 
            thought: log.message, 
            isThinking: true,
            screenshot: screenshotData
          }
          history.push(lastMsg)
        }
      } else if (log.level === 'success') {
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
          lastMsg.isThinking = false
          lastMsg.content = log.message
          // Update screenshot if provided
          if (screenshotData && !lastMsg.screenshot) {
            lastMsg.screenshot = screenshotData
          }
        } else {
          history.push({ 
            role: 'agent', 
            content: log.message,
            screenshot: screenshotData
          })
        }
        lastMsg = null
      } else if (log.level === 'info') {
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
          lastMsg.thought += '\n[INFO] ' + log.message
          // Update screenshot if provided
          if (screenshotData && !lastMsg.screenshot) {
            lastMsg.screenshot = screenshotData
          }
        } else {
          // Create a new info message if no thinking message exists
          history.push({ 
            role: 'agent', 
            content: log.message,
            screenshot: screenshotData,
            isInfo: true  // Mark as info message for styling
          })
          lastMsg = null
        }
      } else if (log.level === 'action') {
        // Action/Answer should always be a separate message, not merged with think
        // Close any thinking message first
        if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
          lastMsg.isThinking = false
        }
        // Create a new independent answer/action message
        history.push({ 
          role: 'agent', 
          action: log.message,
          screenshot: screenshotData,
          isAnswer: true  // Mark as answer message
        })
        lastMsg = null
      } else if (log.level === 'error') {
        history.push({ 
          role: 'agent', 
          content: log.message,
          screenshot: screenshotData,
          isFailed: true,  // Mark as failed message for red styling
          isError: true,
          reason: log.message  // Store the failure reason
        })
        lastMsg = null
      }
    }
    return history
  }
  const handleLog = (data: any) => {
    const lastMsg = chatHistory.value[chatHistory.value.length - 1]
    const isBackground = isBackgroundTask.value
    
    const screenshotData = data.screenshot ? `data:image/jpeg;base64,${data.screenshot}` : null
    
    if (data.level === 'thought') {
      if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
        lastMsg.thought += data.message
        if (screenshotData && !lastMsg.screenshot) {
          lastMsg.screenshot = screenshotData
        }
        if (!isBackground && lastMsg.id) {
          const update: any = { thought: lastMsg.thought }
          if (screenshotData) update.screenshot = screenshotData
          db.updateMessage(lastMsg.id, update)
        }
      } else {
        const newMsg: any = { 
          role: 'agent', 
          thought: data.message, 
          isThinking: true, 
          sessionId: activeTaskId.value,
          screenshot: screenshotData
        }
        chatHistory.value.push(newMsg)
        if (!isBackground) db.addMessage(newMsg).then(id => newMsg.id = id)
      }
    } else if (data.level === 'success') {
      if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
        lastMsg.isThinking = false
        lastMsg.content = data.message
        if (screenshotData && !lastMsg.screenshot) {
          lastMsg.screenshot = screenshotData
        }
        if (!isBackground && lastMsg.id) {
          const update: any = { isThinking: false, content: lastMsg.content }
          if (screenshotData) update.screenshot = screenshotData
          db.updateMessage(lastMsg.id, update)
        }
      } else {
        const newMsg: any = { 
          role: 'agent', 
          content: data.message, 
          sessionId: activeTaskId.value,
          screenshot: screenshotData
        }
        chatHistory.value.push(newMsg)
        if (!isBackground) db.addMessage(newMsg).then(id => newMsg.id = id)
      }
    } else if (data.level === 'info') {
      if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
        lastMsg.thought += (lastMsg.thought ? '\n' : '') + '[INFO] ' + data.message
        if (screenshotData && !lastMsg.screenshot) {
          lastMsg.screenshot = screenshotData
        }
        if (!isBackground && lastMsg.id) {
          const update: any = { thought: lastMsg.thought }
          if (screenshotData) update.screenshot = screenshotData
          db.updateMessage(lastMsg.id, update)
        }
      } else {
        const newMsg: any = { 
          role: 'agent', 
          content: data.message, 
          sessionId: activeTaskId.value,
          screenshot: screenshotData,
          isInfo: true
        }
        chatHistory.value.push(newMsg)
        if (!isBackground) db.addMessage(newMsg).then(id => newMsg.id = id)
      }
    } else if (data.level === 'action') {
      if (lastMsg && lastMsg.role === 'agent' && lastMsg.isThinking) {
        lastMsg.isThinking = false
        if (!isBackground && lastMsg.id) {
          db.updateMessage(lastMsg.id, { isThinking: false })
        }
      }
      const newMsg: any = { 
        role: 'agent', 
        action: data.message, 
        sessionId: activeTaskId.value,
        screenshot: screenshotData,
        isAnswer: true
      }
      chatHistory.value.push(newMsg)
      if (!isBackground) db.addMessage(newMsg).then(id => newMsg.id = id)
    } else if (data.level === 'error') {
      const errorMsg: any = { 
        role: 'agent', 
        content: data.message, 
        sessionId: activeTaskId.value,
        screenshot: screenshotData,
        isFailed: true,
        isError: true,
        reason: data.message
      }
      chatHistory.value.push(errorMsg)
      if (!isBackground) db.addMessage(errorMsg).then(id => errorMsg.id = id)

      if (lastMsg && lastMsg.isThinking) {
        lastMsg.isThinking = false
        if (!isBackground && lastMsg.id) db.updateMessage(lastMsg.id, { isThinking: false })
      }
    }
    
    scrollToBottom()
  }

  return {
    handleLog,
    convertLogsToChat
  }
}

