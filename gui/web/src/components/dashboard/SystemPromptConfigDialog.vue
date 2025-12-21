<template>
  <el-dialog 
    v-model="visible" 
    :title="t('settings.system_prompt_title')" 
    width="1000px" 
    class="custom-dialog" 
    align-center
  >
    <div class="space-y-4">
      <div class="text-sm text-gray-400 mb-4">{{ t('settings.system_prompt_desc') }}</div>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="中文" name="cn">
          <el-input
            v-model="config.cn"
            type="textarea"
            :rows="25"
            :placeholder="t('settings.system_prompt_placeholder')"
            class="font-mono text-xs"
          />
          <div class="text-xs text-gray-500 mt-2">
            {{ t('settings.system_prompt_variables') }}: {date} - {{ t('settings.system_prompt_variables_desc') }}
          </div>
        </el-tab-pane>
        <el-tab-pane label="English" name="en">
          <el-input
            v-model="config.en"
            type="textarea"
            :rows="25"
            :placeholder="t('settings.system_prompt_placeholder')"
            class="font-mono text-xs"
          />
          <div class="text-xs text-gray-500 mt-2">
            {{ t('settings.system_prompt_variables') }}: {date} - {{ t('settings.system_prompt_variables_desc') }}
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer>
      <div class="flex justify-end gap-2">
        <el-button @click="handleCancel" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('common.cancel') }}
        </el-button>
        <el-button @click="handleReset" class="!bg-transparent !border-gray-600 !text-gray-300 hover:!text-white">
          {{ t('settings.reset_to_default') }}
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
const activeTab = ref('cn')
const config = ref({
  cn: '',
  en: ''
})

const api = axios.create({ baseURL: props.apiBaseUrl })

watch(visible, async (newVal) => {
  if (newVal) {
    await loadConfig()
  }
})

const loadConfig = async () => {
  try {
    const [cnRes, enRes] = await Promise.all([
      api.get('/agent/system-prompt?lang=cn'),
      api.get('/agent/system-prompt?lang=en')
    ])
    config.value = {
      cn: cnRes.data.prompt || '',
      en: enRes.data.prompt || ''
    }
  } catch (e) {
    console.error('Failed to load system prompt config', e)
    ElMessage.error(t('error.failed_load_config'))
  }
}

const handleSave = async () => {
  try {
    const lang = activeTab.value
    await api.post('/agent/system-prompt', {
      prompt: config.value[lang as 'cn' | 'en'],
      lang
    })
    ElMessage.success(t('settings.saved'))
    visible.value = false
  } catch (e) {
    console.error('Failed to save system prompt config', e)
    ElMessage.error(t('error.failed_save_config'))
  }
}

const handleReset = async () => {
  try {
    const lang = activeTab.value
    await api.post(`/agent/system-prompt/reset?lang=${lang}`)
    await loadConfig()
    ElMessage.success(t('success.config_reset'))
  } catch (e) {
    console.error('Failed to reset system prompt config', e)
    ElMessage.error(t('error.failed_reset_config'))
  }
}

const handleCancel = () => {
  visible.value = false
}
</script>


