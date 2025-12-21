import { ref, type Ref, nextTick } from 'vue'
import axios from 'axios'

export function useInputEnhancement(
  apiBaseUrl: string,
  activeDeviceId: Ref<string>,
  input: Ref<string>,
  inputRef: Ref<any>
) {
  const api = axios.create({ baseURL: apiBaseUrl })
  const availableApps = ref<Array<{name: string, package?: string, type: string}>>([])
  const showAppSuggestions = ref(false)
  const appSuggestionQuery = ref('')
  const attachments = ref<any[]>([])
  const fileInput = ref<HTMLInputElement | null>(null)

  const fetchDeviceApps = async (deviceId: string) => {
    try {
      const res = await api.get(`/devices/${deviceId}/apps`)
      availableApps.value = res.data.apps
    } catch (e) {
      console.error('Failed to fetch device apps', e)
      availableApps.value = []
    }
  }

  const onInputChange = (val: string) => {
    const lastAt = val.lastIndexOf('@')
    if (lastAt !== -1) {
      const query = val.slice(lastAt + 1)
      if (!query.includes(' ')) {
        if (activeDeviceId.value) {
          if (availableApps.value.length === 0 || availableApps.value.some(a => a.type === 'static')) {
            fetchDeviceApps(activeDeviceId.value)
          }
        }
        showAppSuggestions.value = true
        appSuggestionQuery.value = query.toLowerCase()
        return
      }
    }
    showAppSuggestions.value = false
  }

  const selectApp = (appName: string) => {
    const lastAt = input.value.lastIndexOf('@')
    if (lastAt !== -1) {
      input.value = input.value.slice(0, lastAt) + appName + ' '
    }
    showAppSuggestions.value = false
    nextTick(() => {
      if (inputRef.value) inputRef.value.focus()
    })
  }

  const triggerAppSelect = () => {
    if (showAppSuggestions.value) {
      showAppSuggestions.value = false
      return
    }
    const val = input.value
    if (!val.trim().endsWith('@')) {
      input.value += (val && !val.endsWith(' ') ? ' ' : '') + '@'
    }
    nextTick(() => {
      if (inputRef.value) {
        inputRef.value.focus()
      }
      onInputChange(input.value)
    })
  }

  const triggerUpload = (type: string) => {
    if (fileInput.value) {
      fileInput.value.accept = type === 'image' ? 'image/*' : 
                               type === 'video' ? 'video/*' :
                               type === 'audio' ? 'audio/*' : '*/*'
      fileInput.value.click()
    }
  }

  const handleFileSelect = (event: Event) => {
    const target = event.target as HTMLInputElement
    if (target.files && target.files.length > 0) {
      const file = target.files[0]
      attachments.value.push({
        name: file.name,
        type: file.type.split('/')[0],
        file: file,
        url: URL.createObjectURL(file)
      })
    }
    target.value = ''
  }

  const removeAttachment = (index: number) => {
    attachments.value.splice(index, 1)
  }

  return {
    availableApps,
    showAppSuggestions,
    appSuggestionQuery,
    attachments,
    fileInput,
    fetchDeviceApps,
    onInputChange,
    selectApp,
    triggerAppSelect,
    triggerUpload,
    handleFileSelect,
    removeAttachment
  }
}

