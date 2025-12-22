<template>
  <el-dialog
    v-model="visible"
    :title="t('recording.recordings')"
    width="700px"
    class="custom-dialog"
    align-center
  >
    <div class="mb-4 flex justify-between items-center">
      <el-input
        v-model="searchKeyword"
        :placeholder="t('recording.search_placeholder')"
        clearable
        style="width: 300px"
        @input="handleSearch"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button type="primary" @click="handleExecuteSelected" :disabled="!selectedRecording">
        <el-icon class="mr-1"><VideoPlay /></el-icon>
        {{ t('recording.execute') }}
      </el-button>
    </div>

    <div v-loading="loading" class="max-h-[500px] overflow-y-auto custom-scrollbar">
      <div
        v-for="recording in filteredRecordings"
        :key="recording.id"
        class="p-4 mb-2 border border-gray-700 rounded-lg hover:border-blue-500 cursor-pointer transition-colors"
        :class="{ 'border-blue-500 bg-blue-900/10': selectedRecording?.id === recording.id }"
        @click="selectedRecording = recording"
      >
        <div class="flex justify-between items-start">
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-white font-medium">{{ recording.name }}</h3>
              <el-tag size="small" type="info">{{ recording.action_count }} {{ t('recording.actions') }}</el-tag>
            </div>
            
            <div v-if="recording.keywords && recording.keywords.length > 0" class="flex flex-wrap gap-1 mb-2">
              <el-tag
                v-for="keyword in recording.keywords"
                :key="keyword"
                size="small"
                type="primary"
              >
                {{ keyword }}
              </el-tag>
            </div>
            
            <div v-if="recording.description" class="text-sm text-gray-400 mb-2">
              {{ recording.description }}
            </div>
            
            <div class="text-xs text-gray-500">
              {{ t('recording.device') }}: {{ recording.device_id }}
              <span class="mx-2">•</span>
              {{ t('recording.created') }}: {{ formatDate(recording.created_at) }}
            </div>
          </div>
          
          <div class="flex gap-2 ml-4">
            <el-button
              circle
              text
              type="primary"
              @click.stop="handleExecute(recording)"
            >
              <el-icon><VideoPlay /></el-icon>
            </el-button>
            <el-button
              circle
              text
              type="danger"
              @click.stop="handleDelete(recording)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
      
      <div v-if="filteredRecordings.length === 0" class="text-center py-8 text-gray-500">
        {{ loading ? t('common.loading') : t('recording.no_recordings') }}
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'
import { Search, VideoPlay, Delete } from '@element-plus/icons-vue'
import type { Recording } from '../../composables/useRecording'

const props = defineProps<{
  modelValue: boolean
  recordings: Recording[]
  loading: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'execute': [recording: Recording]
  'delete': [recordingId: string]
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const selectedRecording = ref<Recording | null>(null)
const searchKeyword = ref('')

const filteredRecordings = computed(() => {
  if (!searchKeyword.value) {
    return props.recordings
  }
  
  const keyword = searchKeyword.value.toLowerCase()
  return props.recordings.filter(r => {
    return (
      r.name.toLowerCase().includes(keyword) ||
      r.keywords.some(k => k.toLowerCase().includes(keyword)) ||
      (r.description && r.description.toLowerCase().includes(keyword))
    )
  })
})

const handleSearch = () => {
  selectedRecording.value = null
}

const handleExecute = (recording: Recording) => {
  emit('execute', recording)
}

const handleExecuteSelected = () => {
  if (selectedRecording.value) {
    handleExecute(selectedRecording.value)
  }
}

const handleDelete = async (recording: Recording) => {
  try {
    await ElMessageBox.confirm(
      t('recording.delete_confirm', { name: recording.name }),
      t('common.confirm'),
      {
        confirmButtonText: t('common.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )
    emit('delete', recording.id)
  } catch {
    // User cancelled
  }
}

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString)
    return date.toLocaleString()
  } catch {
    return dateString
  }
}

watch(visible, (newVal) => {
  if (newVal) {
    selectedRecording.value = null
    searchKeyword.value = ''
  }
})
</script>

