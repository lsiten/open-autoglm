<template>
  <el-dialog
    v-model="visible"
    :title="t('recording.debug_mode')"
    width="900px"
    class="custom-dialog"
    align-center
    :close-on-click-modal="false"
  >
    <div v-loading="loading">
      <!-- Initial State Info -->
      <div v-if="initialState && Object.keys(initialState).length > 0" 
           class="mb-4 p-3 border border-gray-700 rounded-lg bg-gray-800/50">
        <div class="text-sm font-medium text-gray-300 mb-2">{{ t('recording.initial_state') }}</div>
        <div class="text-xs text-gray-400 space-y-1">
          <div v-if="initialState.current_app">
            <span class="text-gray-500">{{ t('recording.current_app') }}:</span>
            <span class="text-blue-400 ml-2">{{ initialState.current_app }}</span>
          </div>
          <div v-if="initialState.screen_width && initialState.screen_height">
            <span class="text-gray-500">{{ t('recording.screen_size') }}:</span>
            <span class="text-blue-400 ml-2">{{ initialState.screen_width }} × {{ initialState.screen_height }}</span>
          </div>
        </div>
      </div>

      <!-- Actions List -->
      <div class="max-h-[500px] overflow-y-auto custom-scrollbar mb-4">
        <div v-if="actions.length === 0" class="text-center py-8 text-gray-500">
          {{ t('recording.no_actions') }}
        </div>
        <div v-else>
          <div
            v-for="(action, index) in actions"
            :key="index"
            :class="[
              'p-3 mb-2 border rounded-lg transition-all',
              currentActionIndex === index 
                ? 'border-blue-500 bg-blue-900/20' 
                : executedActions.has(index)
                  ? 'border-green-700 bg-green-900/10'
                  : 'border-gray-700 bg-gray-800/50'
            ]"
          >
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <el-tag size="small" :type="getActionTagType(action.action_type)">
                    {{ action.action_type }}
                  </el-tag>
                  <span class="text-xs text-gray-400">
                    {{ t('recording.action_time') }}: {{ formatTime(action.timestamp) }}s
                  </span>
                  <span v-if="executedActions.has(index)" class="text-xs text-green-400">
                    ✓ {{ t('recording.executed') }}
                  </span>
                </div>
                <div class="text-sm text-gray-300">
                  <div class="font-medium mb-1">{{ t('recording.action_params') }}:</div>
                  <pre class="text-xs bg-gray-900 p-2 rounded overflow-x-auto">{{ formatParams(action.params) }}</pre>
                </div>
              </div>
              <div class="flex flex-col gap-2 ml-4">
                <div class="text-xs text-gray-500 text-right">
                  #{{ index + 1 }}
                </div>
                <div class="flex flex-col gap-1">
                  <el-button
                    size="small"
                    type="primary"
                    :loading="executingAction === index"
                    :disabled="isOperationInProgress || (currentActionIndex !== null && currentActionIndex < index)"
                    @click="handleExecuteAction(index)"
                  >
                    <el-icon v-if="executingAction !== index" class="mr-1"><VideoPlay /></el-icon>
                    {{ t('recording.execute') }}
                  </el-button>
                  <el-button
                    size="small"
                    type="warning"
                    :disabled="isOperationInProgress || isReRecording"
                    @click="handleReRecord(index)"
                  >
                    <el-icon class="mr-1"><Edit /></el-icon>
                    {{ t('recording.rerecord') }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Control Buttons -->
      <div class="flex justify-between items-center pt-4 border-t border-gray-700">
        <div class="flex gap-2">
          <el-button 
            :loading="resetting"
            :disabled="isOperationInProgress"
            @click="handleReset"
          >
            <el-icon v-if="!resetting" class="mr-1"><Refresh /></el-icon>
            {{ t('recording.reset_to_initial') }}
          </el-button>
          <el-button 
            :loading="executingAction !== null && currentActionIndex !== null"
            :disabled="isOperationInProgress || currentActionIndex === null || currentActionIndex >= actions.length - 1"
            @click="handleExecuteNext"
          >
            <el-icon v-if="executingAction === null || currentActionIndex === null" class="mr-1"><Right /></el-icon>
            {{ t('recording.execute_next') }}
          </el-button>
          <el-button 
            :loading="executingAll"
            :disabled="isOperationInProgress || actions.length === 0"
            @click="handleExecuteAll"
          >
            <el-icon v-if="!executingAll" class="mr-1"><VideoPlay /></el-icon>
            {{ t('recording.execute_all') }}
          </el-button>
        </div>
        <el-button @click="visible = false">
          {{ t('common.cancel') }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { VideoPlay, Edit, Refresh, Right } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  recordingId: string | null
  onReset?: (recordingId: string) => Promise<{ success: boolean; message: string }>
  onExecuteAction?: (recordingId: string, actionIndex: number) => Promise<{ success: boolean; message: string }>
  onReplaceAction?: (recordingId: string, actionIndex: number, newAction: any) => Promise<{ success: boolean; action?: any; message?: string }>
  onPreview?: (recordingId: string) => Promise<any>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const executing = ref(false)
const resetting = ref(false)
const executingAction = ref<number | null>(null) // Track which action is being executed
const executingAll = ref(false)
const isReRecording = ref(false)
const actions = ref<any[]>([])
const initialState = ref<any>({})
const currentActionIndex = ref<number | null>(null)
const executedActions = ref<Set<number>>(new Set())

// Computed property to check if any operation is in progress
const isOperationInProgress = computed(() => {
  return executing.value || resetting.value || executingAll.value || executingAction.value !== null
})

watch(visible, async (newVal) => {
  if (newVal && props.recordingId) {
    await loadRecordingData()
    // Auto-reset to initial state when dialog opens
    if (props.onReset) {
      await handleReset()
    }
  } else {
    // Reset state when dialog closes
    currentActionIndex.value = null
    executedActions.value.clear()
  }
})

const loadRecordingData = async () => {
  if (!props.recordingId || !props.onPreview) return
  
  loading.value = true
  try {
    const data = await props.onPreview(props.recordingId)
    if (data) {
      actions.value = data.actions || []
      initialState.value = data.initial_state || {}
    } else {
      actions.value = []
      initialState.value = {}
    }
  } catch (e: any) {
    console.error('Failed to load recording data', e)
    ElMessage.error(e.response?.data?.detail || 'Failed to load recording')
  } finally {
    loading.value = false
  }
}

const handleReset = async () => {
  if (!props.recordingId || !props.onReset || isOperationInProgress.value) return
  
  resetting.value = true
  try {
    const result = await props.onReset(props.recordingId)
    if (result.success) {
      ElMessage.success(result.message || t('recording.reset_success'))
      currentActionIndex.value = null
      executedActions.value.clear()
    } else {
      ElMessage.error(result.message || t('recording.reset_failed'))
    }
  } catch (e: any) {
    console.error('Failed to reset', e)
    ElMessage.error(t('recording.reset_failed'))
  } finally {
    resetting.value = false
  }
}

const handleExecuteAction = async (index: number) => {
  if (!props.recordingId || !props.onExecuteAction || isOperationInProgress.value) return
  
  executingAction.value = index
  currentActionIndex.value = index
  try {
    const result = await props.onExecuteAction(props.recordingId, index)
    if (result.success) {
      executedActions.value.add(index)
      currentActionIndex.value = index + 1 <= actions.value.length - 1 ? index + 1 : null
      ElMessage.success(result.message || t('recording.action_executed'))
    } else {
      ElMessage.error(result.message || t('recording.action_execute_failed'))
    }
  } catch (e: any) {
    console.error('Failed to execute action', e)
    ElMessage.error(t('recording.action_execute_failed'))
  } finally {
    executingAction.value = null
  }
}

const handleExecuteNext = async () => {
  if (isOperationInProgress.value) return
  
  if (currentActionIndex.value === null) {
    currentActionIndex.value = 0
  }
  if (currentActionIndex.value < actions.value.length) {
    await handleExecuteAction(currentActionIndex.value)
  }
}

const handleExecuteAll = async () => {
  if (!props.recordingId || !props.onExecuteAction || !props.onReset || isOperationInProgress.value) return
  
  executingAll.value = true
  
  try {
    // First, reset to initial state
    resetting.value = true
    if (props.onReset) {
      const resetResult = await props.onReset(props.recordingId)
      if (!resetResult.success) {
        ElMessage.error(resetResult.message || t('recording.reset_failed'))
        return
      }
      // Clear executed actions and reset current index
      currentActionIndex.value = null
      executedActions.value.clear()
      ElMessage.success(resetResult.message || t('recording.reset_success'))
    }
    resetting.value = false
    
    // Small delay after reset to ensure device is ready
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // Then execute all actions
    currentActionIndex.value = 0
    
    for (let i = 0; i < actions.value.length; i++) {
      currentActionIndex.value = i
      executingAction.value = i
      const result = await props.onExecuteAction(props.recordingId, i)
      executingAction.value = null
      
      if (result.success) {
        executedActions.value.add(i)
        // Small delay between actions
        await new Promise(resolve => setTimeout(resolve, 300))
      } else {
        ElMessage.error(`${t('recording.action_execute_failed')} (#${i + 1})`)
        break
      }
    }
    
    currentActionIndex.value = null
    ElMessage.success(t('recording.all_actions_executed'))
  } catch (e: any) {
    console.error('Failed to execute all actions', e)
    ElMessage.error(t('recording.action_execute_failed'))
  } finally {
    executingAll.value = false
    resetting.value = false
    executingAction.value = null
  }
}

const handleReRecord = async (index: number) => {
  if (!props.recordingId) return
  
  // TODO: Implement re-recording logic
  // This would involve:
  // 1. Starting a temporary recording
  // 2. Waiting for user to perform the action
  // 3. Stopping the recording
  // 4. Replacing the action at index with the new recorded action
  ElMessage.info(t('recording.rerecord_not_implemented'))
}

const formatTime = (seconds: number) => {
  return seconds.toFixed(2)
}

const formatParams = (params: any) => {
  return JSON.stringify(params, null, 2)
}

const getActionTagType = (actionType: string) => {
  const typeMap: Record<string, string> = {
    'tap': 'primary',
    'swipe': 'success',
    'type': 'info',
    'back': 'warning',
    'home': 'warning',
    'recent': 'warning',
    'wait': 'default'
  }
  return typeMap[actionType] || 'default'
}
</script>

