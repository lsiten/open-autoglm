import { type Ref } from 'vue'
import { detectPlatform } from '../utils/platformDetector'

export function useAppMatchingUI(
  appMatchingConfig: Ref<{
    system_app_mappings: Record<string, Array<{package: string, platform?: string}>>
  }>
) {
  const addMapping = () => {
    const newKey = `新关键词_${Object.keys(appMatchingConfig.value.system_app_mappings).length + 1}`
    appMatchingConfig.value.system_app_mappings[newKey] = []
  }

  const removeMapping = (keyword: string) => {
    delete appMatchingConfig.value.system_app_mappings[keyword]
  }

  const updateMappingKey = (oldIndex: number, oldKey: string, newKey: string) => {
    if (newKey && newKey !== oldKey) {
      const packages = appMatchingConfig.value.system_app_mappings[oldKey]
      delete appMatchingConfig.value.system_app_mappings[oldKey]
      appMatchingConfig.value.system_app_mappings[newKey] = packages
    }
  }

  const addPackage = (keyword: string) => {
    if (!appMatchingConfig.value.system_app_mappings[keyword]) {
      appMatchingConfig.value.system_app_mappings[keyword] = []
    }
    appMatchingConfig.value.system_app_mappings[keyword].push({ package: '', platform: '' })
  }

  const removePackage = (keyword: string, index: number) => {
    appMatchingConfig.value.system_app_mappings[keyword].splice(index, 1)
  }

  const updatePackagePlatform = (keyword: string, index: number) => {
    const pkgItem = appMatchingConfig.value.system_app_mappings[keyword][index]
    if (pkgItem.package && !pkgItem.platform) {
      pkgItem.platform = detectPlatform(pkgItem.package)
    }
  }

  return {
    addMapping,
    removeMapping,
    updateMappingKey,
    addPackage,
    removePackage,
    updatePackagePlatform
  }
}

