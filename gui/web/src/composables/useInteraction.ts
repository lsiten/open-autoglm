import { type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import axios from 'axios'

export function useInteraction(apiBaseUrl: string, activeTaskId: Ref<string | null>) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })

  const handleCardAction = async (msg: any, option: any) => {
    msg.submitted = true
    msg.selectedValue = option.label
    if (msg.id) {
      await db.updateMessage(msg.id, { submitted: true, selectedValue: option.label })
    }
    
    if (activeTaskId.value) {
      try {
        await api.post(`/tasks/${activeTaskId.value}/interaction`, {
          response: option.value
        })
      } catch (e) {
        console.error('Failed to send interaction response', e)
        ElMessage.error(t('error.failed_send_interaction'))
      }
    }
  }

  const handleCardInput = async (msg: any) => {
    if (!msg.inputValue) return
    msg.submitted = true
    if (msg.id) {
      await db.updateMessage(msg.id, { submitted: true, inputValue: msg.inputValue })
    }
    
    if (activeTaskId.value) {
      try {
        await api.post(`/tasks/${activeTaskId.value}/interaction`, {
          response: msg.inputValue
        })
      } catch (e) {
        console.error('Failed to send interaction response', e)
        ElMessage.error(t('error.failed_send_interaction'))
      }
    }
  }

  const handleCardAnnotation = async (data: { msg: any, annotation: { x: number, y: number, description: string } }) => {
    const { msg, annotation } = data
    msg.submitted = true
    msg.annotation = annotation
    if (msg.id) {
      await db.updateMessage(msg.id, { submitted: true, annotation })
    }
    
    if (activeTaskId.value) {
      try {
        await api.post(`/tasks/${activeTaskId.value}/interaction`, {
          response: JSON.stringify({
            type: 'click_annotation',
            x: annotation.x,
            y: annotation.y,
            description: annotation.description
          })
        })
      } catch (e) {
        console.error('Failed to send annotation response', e)
        ElMessage.error(t('error.failed_send_interaction'))
      }
    }
  }

  return {
    handleCardAction,
    handleCardInput,
    handleCardAnnotation
  }
}

