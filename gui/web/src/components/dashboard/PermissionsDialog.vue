<template>
  <el-dialog 
    v-model="visible" 
    :title="t('permissions.title')" 
    width="500px" 
    class="custom-dialog" 
    align-center
  >
    <el-form label-position="top">
      <el-form-item>
        <el-checkbox v-model="permissions.install_app">
          {{ t('permissions.install_app') }}
        </el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="permissions.payment">
          {{ t('permissions.payment') }}
        </el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="permissions.wechat_reply">
          {{ t('permissions.wechat_reply') }}
        </el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="permissions.send_sms">
          {{ t('permissions.send_sms') }}
        </el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="permissions.make_call">
          {{ t('permissions.make_call') }}
        </el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="handleSave" class="!bg-blue-600 !border-none">
          {{ t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps<{
  modelValue: boolean
  deviceId: string
  apiBaseUrl: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const permissions = ref({
  install_app: false,
  payment: false,
  wechat_reply: false,
  send_sms: false,
  make_call: false
})

const api = axios.create({ baseURL: props.apiBaseUrl })

watch(visible, async (newVal) => {
  if (newVal && props.deviceId) {
    await loadPermissions()
  }
})

const loadPermissions = async () => {
  try {
    const res = await api.get(`/devices/${props.deviceId}/permissions`)
    permissions.value = res.data
  } catch (e) {
    console.error('Failed to load permissions', e)
    permissions.value = {
      install_app: false,
      payment: false,
      wechat_reply: false,
      send_sms: false,
      make_call: false
    }
  }
}

const handleSave = async () => {
  if (!props.deviceId) return
  try {
    await api.post(`/devices/${props.deviceId}/permissions`, permissions.value)
    ElMessage.success(t('settings.saved'))
    visible.value = false
  } catch (e) {
    console.error('Failed to save permissions', e)
    ElMessage.error(t('error.failed_save_permissions'))
  }
}

const handleCancel = () => {
  visible.value = false
}
</script>

