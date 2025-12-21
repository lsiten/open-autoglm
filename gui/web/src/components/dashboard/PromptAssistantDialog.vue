<template>
  <el-dialog 
    v-model="visible" 
    :title="t('settings.prompt_assistant_title')" 
    width="800px" 
    class="custom-dialog" 
    align-center
  >
    <div class="space-y-4">
      <div class="text-sm text-gray-400 mb-4">{{ t('settings.prompt_assistant_desc') }}</div>
      
      <!-- User Request Input -->
      <div class="space-y-2">
        <label class="text-sm text-gray-300">{{ t('settings.prompt_assistant_request_label') }}</label>
        <el-input
          v-model="userRequest"
          type="textarea"
          :rows="4"
          :placeholder="t('settings.prompt_assistant_request_placeholder')"
          class="font-mono text-xs"
        />
      </div>

      <!-- Optimized Prompt Display -->
      <div v-if="optimizedPrompt" class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="text-sm text-gray-300">{{ t('settings.prompt_assistant_result_label') }}</label>
          <el-button 
            size="small" 
            link 
            @click="copyOptimizedPrompt"
            class="!text-blue-400 hover:!text-blue-300"
          >
            <el-icon class="mr-1"><DocumentCopy /></el-icon>
            {{ t('common.copy') }}
          </el-button>
        </div>
        <el-input
          v-model="optimizedPrompt"
          type="textarea"
          :rows="20"
          readonly
          class="font-mono text-xs"
        />
        <div class="text-xs text-gray-500">
          {{ t('settings.prompt_assistant_result_hint') }}
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="flex items-center justify-center py-8">
        <el-icon class="is-loading text-blue-400 text-2xl"><Loading /></el-icon>
        <span class="ml-3 text-gray-400">{{ t('settings.prompt_assistant_optimizing') }}</span>
      </div>

      <!-- Error Message -->
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
      />
    </div>
    
    <template #footer>
      <div class="flex justify-between items-center">
        <el-button 
          @click="handleCancel" 
          class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white"
        >
          {{ t('common.cancel') }}
        </el-button>
        <div class="flex gap-2">
          <el-button 
            @click="handleOptimize" 
            type="primary"
            :loading="loading"
            :disabled="!userRequest.trim()"
            class="!bg-blue-600 !border-none"
          >
            {{ t('settings.prompt_assistant_optimize') }}
          </el-button>
          <el-button 
            v-if="optimizedPrompt"
            @click="handleApply" 
            type="success"
            class="!bg-green-600 !border-none"
          >
            {{ t('settings.prompt_assistant_apply') }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { DocumentCopy, Loading } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps<{
  modelValue: boolean
  apiBaseUrl: string
  currentPrompt: string
  lang: string
  deviceId?: string | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'apply': [optimizedPrompt: string]
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const userRequest = ref('')
const optimizedPrompt = ref('')
const loading = ref(false)
const error = ref('')

watch(visible, (newVal) => {
  if (newVal) {
    userRequest.value = ''
    optimizedPrompt.value = ''
    error.value = ''
  }
})

const handleOptimize = async () => {
  if (!userRequest.value.trim()) {
    ElMessage.warning(t('settings.prompt_assistant_request_required'))
    return
  }

  loading.value = true
  error.value = ''
  optimizedPrompt.value = ''

  try {
    const requestData: any = {
      current_prompt: props.currentPrompt,
      user_request: userRequest.value.trim(),
      lang: props.lang
    }
    
    if (props.deviceId) {
      requestData.device_id = props.deviceId
    }

    const api = axios.create({ baseURL: props.apiBaseUrl })
    const response = await api.post('/agent/system-prompt/optimize', requestData)
    
    if (response.data && response.data.optimized_prompt) {
      optimizedPrompt.value = response.data.optimized_prompt
      ElMessage.success(t('settings.prompt_assistant_success'))
    } else {
      throw new Error(t('settings.prompt_assistant_error_no_result'))
    }
  } catch (e: any) {
    console.error('Failed to optimize prompt', e)
    error.value = e.response?.data?.detail || e.message || t('settings.prompt_assistant_error')
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

const handleApply = () => {
  if (optimizedPrompt.value) {
    emit('apply', optimizedPrompt.value)
    visible.value = false
  }
}

const handleCancel = () => {
  visible.value = false
}

const copyOptimizedPrompt = async () => {
  try {
    await navigator.clipboard.writeText(optimizedPrompt.value)
    ElMessage.success(t('common.copied'))
  } catch (e) {
    ElMessage.error(t('error.failed_copy'))
  }
}
</script>

<style scoped>
:deep(.el-textarea__inner) {
  background-color: #161b22;
  border: 1px solid #30363d;
  color: #e6edf3;
  font-family: 'Courier New', monospace;
}

:deep(.el-textarea__inner:focus) {
  border-color: #58a6ff;
  box-shadow: 0 0 0 1px #58a6ff;
}
</style>

