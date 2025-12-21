import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { db } from '../utils/db'
import axios from 'axios'

export function useTaskEdit(apiBaseUrl: string) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const showEditTaskDialog = ref(false)
  const editTaskNameValue = ref('')
  const taskToEdit = ref<any>(null)

  const startEditTask = (task: any) => {
    taskToEdit.value = task
    editTaskNameValue.value = task.name
    showEditTaskDialog.value = true
  }

  const saveTaskName = async () => {
    if (!taskToEdit.value || !editTaskNameValue.value.trim()) return
    const newName = editTaskNameValue.value.trim()
    
    if (taskToEdit.value.type === 'chat') {
      await db.updateSession(taskToEdit.value.id, { name: newName })
      taskToEdit.value.name = newName
    } else {
      try {
        await api.put(`/tasks/${taskToEdit.value.id}`, { name: newName })
        taskToEdit.value.name = newName
      } catch (e) {
        ElMessage.error(t('error.failed_rename_task'))
      }
    }
    showEditTaskDialog.value = false
    ElMessage.success(t('success.renamed'))
  }

  return {
    showEditTaskDialog,
    editTaskNameValue,
    taskToEdit,
    startEditTask,
    saveTaskName
  }
}

