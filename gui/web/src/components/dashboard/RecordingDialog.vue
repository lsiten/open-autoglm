<template>
  <RecordingDebugDialog
    v-model="showDebugDialog"
    :recording-id="recordingId"
    :on-reset="props.onReset"
    :on-execute-action="props.onExecuteAction"
    :on-replace-action="props.onReplaceAction"
    :on-preview="props.onPreview"
  />
  
  <el-dialog
    v-model="visible"
    :title="t('recording.save_recording')"
    width="600px"
    class="custom-dialog"
    align-center
  >
    <el-form label-position="top">
      <el-form-item :label="t('recording.name')" required>
        <el-input
          v-model="name"
          :placeholder="t('recording.name_placeholder')"
          maxlength="50"
          show-word-limit
        />
      </el-form-item>

      <el-form-item :label="t('recording.keywords')">
        <el-input
          v-model="keywordsText"
          :placeholder="t('recording.keywords_placeholder')"
          type="textarea"
          :rows="2"
        />
        <div class="text-xs text-gray-500 mt-1">
          {{ t('recording.keywords_hint') }}
        </div>
      </el-form-item>

      <el-form-item :label="t('recording.description')">
        <el-input
          v-model="description"
          :placeholder="t('recording.description_placeholder')"
          type="textarea"
          :rows="3"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <el-form-item>
        <div class="flex items-center justify-between">
          <div class="text-sm text-gray-400">
            {{ t('recording.action_count') }}: <span class="text-blue-400">{{ actionCount }}</span>
          </div>
          <div class="flex gap-2">
            <el-button size="small" @click="handlePreview">
              <el-icon class="mr-1"><View /></el-icon>
              {{ t('recording.preview') }}
            </el-button>
            <el-button size="small" type="warning" @click="handleDebug" :disabled="actionCount === 0">
              <el-icon class="mr-1"><VideoPlay /></el-icon>
              {{ t('recording.debug') }}
            </el-button>
          </div>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel">
          {{ t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          @click="handleSave"
          :disabled="!name.trim()"
        >
          {{ t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>

  <!-- Preview Dialog -->
  <el-dialog
    v-model="showPreview"
    :title="t('recording.preview_actions')"
    width="700px"
    class="custom-dialog"
    align-center
  >
    <div v-loading="previewLoading">
      <!-- Initial State Info -->
      <div v-if="previewInitialState && Object.keys(previewInitialState).length > 0" 
           class="mb-4 p-3 border border-gray-700 rounded-lg bg-gray-800/50">
        <div class="text-sm font-medium text-gray-300 mb-2">{{ t('recording.initial_state') }}</div>
        <div class="text-xs text-gray-400 space-y-1">
          <div v-if="previewInitialState.current_app">
            <span class="text-gray-500">{{ t('recording.current_app') }}:</span>
            <span class="text-blue-400 ml-2">{{ previewInitialState.current_app }}</span>
          </div>
          <div v-if="previewInitialState.screen_width && previewInitialState.screen_height">
            <span class="text-gray-500">{{ t('recording.screen_size') }}:</span>
            <span class="text-blue-400 ml-2">{{ previewInitialState.screen_width }} × {{ previewInitialState.screen_height }}</span>
          </div>
          <div v-if="previewInitialState.device_type">
            <span class="text-gray-500">{{ t('recording.device_type') }}:</span>
            <span class="text-blue-400 ml-2">{{ previewInitialState.device_type.toUpperCase() }}</span>
          </div>
        </div>
      </div>

      <!-- Actions List -->
      <div class="max-h-[500px] overflow-y-auto custom-scrollbar">
        <div v-if="previewActions.length === 0" class="text-center py-8 text-gray-500">
          {{ t('recording.no_actions') }}
        </div>
        <div v-else>
        <div
          v-for="(action, index) in previewActions"
          :key="index"
          class="p-3 mb-2 border border-gray-700 rounded-lg bg-gray-800/50"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <div class="flex items-center gap-2 mb-2">
                <el-tag size="small" type="primary">{{ action.action_type }}</el-tag>
                <span class="text-xs text-gray-400">
                  {{ t('recording.action_time') }}: {{ formatTime(action.timestamp) }}s
                </span>
              </div>
              <div class="text-sm text-gray-300">
                <div class="font-medium mb-1">{{ t('recording.action_params') }}:</div>
                <pre class="text-xs bg-gray-900 p-2 rounded overflow-x-auto">{{ formatParams(action.params) }}</pre>
              </div>
            </div>
            <div class="text-xs text-gray-500 ml-4">
              #{{ index + 1 }}
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="showPreview = false">
        {{ t('recording.close_preview') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { View, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import RecordingDebugDialog from './RecordingDebugDialog.vue'

const props = defineProps<{
  modelValue: boolean
  actionCount: number
  recordingId: string | null
  onPreview?: (recordingId: string) => Promise<any>
  onDebug?: (recordingId: string) => Promise<boolean>
  onReset?: (recordingId: string) => Promise<{ success: boolean; message: string }>
  onExecuteAction?: (recordingId: string, actionIndex: number) => Promise<{ success: boolean; message: string }>
  onReplaceAction?: (recordingId: string, actionIndex: number, newAction: any) => Promise<{ success: boolean; action?: any; message?: string }>
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'save': [name: string, keywords: string[], description?: string]
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const name = ref('')
const keywordsText = ref('')
const description = ref('')
const showPreview = ref(false)
const showDebugDialog = ref(false)
const previewLoading = ref(false)
const previewActions = ref<any[]>([])
const previewInitialState = ref<any>({})

watch(visible, (newVal) => {
  if (newVal) {
    // Reset form when dialog opens
    name.value = ''
    keywordsText.value = ''
    description.value = ''
    showPreview.value = false
    previewActions.value = []
    previewInitialState.value = {}
  }
})

const handleSave = () => {
  if (!name.value.trim()) {
    return
  }

  // Parse keywords from comma-separated string
  const keywords = keywordsText.value
    .split(',')
    .map(k => k.trim())
    .filter(k => k.length > 0)

  emit('save', name.value.trim(), keywords, description.value.trim() || undefined)
  visible.value = false
}

const handleCancel = () => {
  visible.value = false
}

const handlePreview = async () => {
  if (!props.recordingId || !props.onPreview) {
    ElMessage.warning('Recording ID is required for preview')
    return
  }

  showPreview.value = true
  previewLoading.value = true
  previewActions.value = []

  try {
    const data = await props.onPreview(props.recordingId)
    if (data) {
      previewActions.value = data.actions || []
      previewInitialState.value = data.initial_state || {}
    } else {
      previewActions.value = []
      previewInitialState.value = {}
    }
  } catch (e: any) {
    console.error('Failed to preview recording', e)
    ElMessage.error(e.response?.data?.detail || 'Failed to load preview')
    showPreview.value = false
  } finally {
    previewLoading.value = false
  }
}

const handleDebug = () => {
  if (!props.recordingId) {
    ElMessage.warning('Recording ID is required for debug')
    return
  }
  // Open debug dialog instead of executing directly
  showDebugDialog.value = true
}

const formatTime = (seconds: number) => {
  return seconds.toFixed(2)
}

const formatParams = (params: any) => {
  return JSON.stringify(params, null, 2)
}
</script>

