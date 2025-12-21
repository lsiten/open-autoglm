<template>
  <el-dialog 
    v-model="visible" 
    :title="isEdit ? t('common.rename') : t('task.new_task_title')" 
    :width="isEdit ? '400px' : '450px'" 
    class="custom-dialog" 
    align-center
  >
    <!-- Edit Mode: Simple rename -->
    <template v-if="isEdit">
      <el-input 
        v-model="editName" 
        :placeholder="t('common.enter_new_name')" 
        @keyup.enter="handleSave"
      />
    </template>
    
    <!-- Create Mode: Full form -->
    <template v-else>
      <el-form label-position="top" class="mt-2">
        <el-form-item :label="t('task.type')">
          <el-radio-group v-model="taskData.type" size="small">
            <el-radio-button label="chat">{{ t('task.session') }}</el-radio-button>
            <el-radio-button label="background">{{ t('task.task') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('task.name')">
          <el-input v-model="taskData.name" :placeholder="t('task.name_placeholder')" />
        </el-form-item>
        <template v-if="taskData.type === 'background'">
          <el-form-item :label="t('task.role')">
            <el-input v-model="taskData.role" type="textarea" :rows="2" :placeholder="t('task.role_placeholder')" />
          </el-form-item>
          <el-form-item :label="t('task.details')">
            <el-input v-model="taskData.details" type="textarea" :rows="3" :placeholder="t('task.details_placeholder')" />
          </el-form-item>
        </template>
      </el-form>
    </template>
    
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="handleSave" class="!bg-blue-600 !border-none">
          {{ isEdit ? t('common.save') : t('common.create') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  modelValue: boolean
  task?: any
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'save': [data: any]
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const isEdit = computed(() => !!props.task)
const editName = ref('')
const taskData = ref({
  type: 'chat' as 'chat' | 'background',
  name: '',
  role: '',
  details: ''
})

watch(visible, (newVal) => {
  if (newVal) {
    if (isEdit.value && props.task) {
      editName.value = props.task.name || ''
    } else {
      editName.value = ''
      taskData.value = {
        type: 'chat',
        name: '',
        role: '',
        details: ''
      }
    }
  }
})

const handleSave = () => {
  if (isEdit.value) {
    emit('save', { name: editName.value.trim() })
  } else {
    emit('save', { ...taskData.value })
  }
  visible.value = false
}

const handleCancel = () => {
  visible.value = false
}
</script>

