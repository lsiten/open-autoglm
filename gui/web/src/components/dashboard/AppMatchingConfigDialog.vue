<template>
  <el-dialog 
    v-model="visible" 
    :title="t('settings.app_matching_title')" 
    width="900px" 
    class="custom-dialog" 
    align-center
  >
    <el-tabs v-model="activeTab">
      <el-tab-pane :label="t('settings.system_app_mappings')" name="mappings">
        <div class="mt-4">
          <div class="text-sm text-gray-400 mb-4">{{ t('settings.system_app_mappings_desc') }}</div>
          <div class="max-h-[60vh] overflow-y-auto pr-2 space-y-4 custom-scrollbar">
            <div v-for="(packages, keyword) in config.system_app_mappings" :key="keyword" class="border border-gray-700 rounded-lg p-4 bg-[#0d1117]">
              <div class="flex items-center justify-between mb-3">
                <el-input 
                  v-model="localKeyword[keyword]" 
                  :placeholder="t('settings.keyword_placeholder')"
                  size="small"
                  class="flex-1 mr-2"
                />
                <el-button type="danger" size="small" circle @click="removeMapping(keyword)">
                  <el-icon><Close /></el-icon>
                </el-button>
              </div>
              <div class="space-y-2">
                <div v-for="(pkgItem, pkgIndex) in packages" :key="pkgIndex" class="flex items-start gap-2">
                  <div class="flex-1">
                    <div class="text-xs text-gray-500 mb-1">{{ t('settings.package_name') }}</div>
                    <el-input 
                      v-model="pkgItem.package" 
                      :placeholder="t('settings.package_name_placeholder')"
                      size="small"
                      @input="updatePackagePlatform(keyword, pkgIndex)"
                    />
                  </div>
                  <div class="w-32">
                    <div class="text-xs text-gray-500 mb-1">{{ t('settings.platform') }}</div>
                    <el-select 
                      v-model="pkgItem.platform" 
                      :placeholder="t('settings.platform_placeholder')"
                      size="small"
                      filterable
                      allow-create
                      default-first-option
                    >
                      <el-option 
                        v-for="platform in availablePlatforms" 
                        :key="platform" 
                        :label="platform" 
                        :value="platform"
                      />
                    </el-select>
                  </div>
                  <el-button type="danger" size="small" circle @click="removePackage(keyword, pkgIndex)" class="mt-6">
                    <el-icon><Close /></el-icon>
                  </el-button>
                </div>
                <el-button size="small" @click="addPackage(keyword)">{{ t('settings.add_package') }}</el-button>
              </div>
            </div>
            <el-button @click="addMapping" type="primary">{{ t('settings.add_mapping') }}</el-button>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane :label="t('settings.llm_prompt_template')" name="prompt">
        <div class="mt-4">
          <div class="text-sm text-gray-400 mb-4">{{ t('settings.llm_prompt_template_desc') }}</div>
          <el-input
            v-model="config.llm_prompt_template"
            type="textarea"
            :rows="20"
            :placeholder="t('settings.llm_prompt_template_placeholder')"
            class="font-mono text-xs"
          />
          <div class="text-xs text-gray-500 mt-2">
            {{ t('settings.prompt_variables') }}: {user_input}, {apps_text}, {system_hints_text}
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
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
import { Close } from '@element-plus/icons-vue'

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
const activeTab = ref('mappings')
const config = ref<{
  system_app_mappings: Record<string, Array<{package: string, platform?: string}>>
  llm_prompt_template: string
}>({
  system_app_mappings: {},
  llm_prompt_template: ''
})
const localKeyword = ref<Record<string, string>>({})

const availablePlatforms = ['华为', '小米', 'OPPO', 'vivo', '三星', 'Android', '腾讯', '360', '百度', '豌豆荚', '应用汇', '其他']

const api = axios.create({ baseURL: props.apiBaseUrl })

const detectPlatform = (packageName: string): string => {
  const pkg = packageName.toLowerCase()
  if (pkg.includes('huawei')) return '华为'
  if (pkg.includes('miui') || pkg.includes('xiaomi')) return '小米'
  if (pkg.includes('oppo') || pkg.includes('coloros')) return 'OPPO'
  if (pkg.includes('vivo') || pkg.includes('funtouch')) return 'vivo'
  if (pkg.includes('samsung')) return '三星'
  if (pkg.includes('tencent')) return '腾讯'
  if (pkg.includes('qihoo')) return '360'
  if (pkg.includes('baidu')) return '百度'
  if (pkg.includes('wandoujia')) return '豌豆荚'
  if (pkg.includes('yingyonghui')) return '应用汇'
  if (pkg.startsWith('com.android.') && !pkg.includes('huawei') && !pkg.includes('miui')) return 'Android'
  return '其他'
}

watch(visible, async (newVal) => {
  if (newVal) {
    await loadConfig()
  }
})

const loadConfig = async () => {
  try {
    const res = await api.get('/agent/app-matching-config')
    const data = res.data
    const mappings = data.system_app_mappings || {}
    
    // Convert old format (string[]) to new format (Array<{package, platform}>)
    const convertedMappings: Record<string, Array<{package: string, platform?: string}>> = {}
    for (const [keyword, packages] of Object.entries(mappings)) {
      if (Array.isArray(packages)) {
        convertedMappings[keyword] = packages.map((pkg: any) => {
          if (typeof pkg === 'string') {
            return { package: pkg, platform: detectPlatform(pkg) }
          }
          return { package: pkg.package || '', platform: pkg.platform || detectPlatform(pkg.package || '') }
        })
      }
    }
    
    config.value = {
      system_app_mappings: convertedMappings,
      llm_prompt_template: data.llm_prompt_template || ''
    }
    // Initialize localKeyword
    localKeyword.value = {}
    for (const keyword in config.value.system_app_mappings) {
      localKeyword.value[keyword] = keyword
    }
  } catch (e) {
    console.error('Failed to load app matching config', e)
    ElMessage.error(t('error.failed_load_config'))
  }
}

const handleSave = async () => {
  try {
    // Update keywords from localKeyword
    const updatedMappings: Record<string, any[]> = {}
    for (const oldKeyword in config.value.system_app_mappings) {
      const newKeyword = localKeyword.value[oldKeyword] || oldKeyword
      updatedMappings[newKeyword] = config.value.system_app_mappings[oldKeyword]
    }
    config.value.system_app_mappings = updatedMappings
    
    await api.post('/agent/app-matching-config', config.value)
    ElMessage.success(t('settings.saved'))
    visible.value = false
  } catch (e) {
    console.error('Failed to save app matching config', e)
    ElMessage.error(t('error.failed_save_config'))
  }
}

const handleReset = async () => {
  try {
    await api.post('/agent/app-matching-config/reset')
    await loadConfig()
    ElMessage.success(t('success.config_reset'))
  } catch (e) {
    console.error('Failed to reset app matching config', e)
    ElMessage.error(t('error.failed_reset_config'))
  }
}

const handleCancel = () => {
  visible.value = false
}

const addMapping = () => {
  const newKey = `keyword_${Date.now()}`
  config.value.system_app_mappings[newKey] = [{ package: '', platform: '其他' }]
  localKeyword.value[newKey] = newKey
}

const removeMapping = (keyword: string) => {
  delete config.value.system_app_mappings[keyword]
  delete localKeyword.value[keyword]
}

const addPackage = (keyword: string) => {
  config.value.system_app_mappings[keyword].push({ package: '', platform: '其他' })
}

const removePackage = (keyword: string, index: number) => {
  config.value.system_app_mappings[keyword].splice(index, 1)
}

const updatePackagePlatform = (keyword: string, index: number) => {
  const pkg = config.value.system_app_mappings[keyword][index]
  if (pkg.package && !pkg.platform) {
    pkg.platform = detectPlatform(pkg.package)
  }
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #30363d;
  border-radius: 3px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #58a6ff;
}
</style>

