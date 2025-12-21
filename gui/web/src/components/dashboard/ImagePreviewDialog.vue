<template>
  <el-dialog 
    v-model="visible" 
    :title="`${t('chat.screenshot')} (${imageIndex + 1} / ${images.length})`"
    width="90vw"
    class="custom-dialog"
    align-center
    @close="handleClose"
  >
    <div class="relative flex items-center justify-center min-h-[60vh] bg-black/50 rounded-lg">
      <img 
        :src="currentImageUrl" 
        alt="Screenshot" 
        class="max-w-full max-h-[80vh] object-contain rounded-lg"
      />
      
      <!-- Navigation Buttons -->
      <el-button 
        v-if="images.length > 1"
        circle 
        class="absolute left-4 z-10 !bg-black/50 !border-white/20 hover:!bg-black/70"
        @click="showPreviousImage"
        :disabled="imageIndex === 0"
      >
        <el-icon><ArrowLeft /></el-icon>
      </el-button>
      <el-button 
        v-if="images.length > 1"
        circle 
        class="absolute right-4 z-10 !bg-black/50 !border-white/20 hover:!bg-black/70"
        @click="showNextImage"
        :disabled="imageIndex === images.length - 1"
      >
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  modelValue: boolean
  images: string[]
  initialIndex?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useI18n()
const imageIndex = ref(props.initialIndex ?? 0)

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const currentImageUrl = computed(() => {
  if (props.images.length === 0) return ''
  const index = imageIndex.value >= 0 && imageIndex.value < props.images.length 
    ? imageIndex.value 
    : 0
  return props.images[index] || ''
})

// Watch for initialIndex changes and update imageIndex
watch(() => props.initialIndex, (newIndex) => {
  if (newIndex !== undefined && newIndex >= 0 && newIndex < props.images.length) {
    imageIndex.value = newIndex
  }
}, { immediate: true })

// Watch for dialog visibility to reset index when opened
watch(() => props.modelValue, (isVisible) => {
  if (isVisible && props.initialIndex !== undefined) {
    // When dialog opens, ensure imageIndex is set to initialIndex
    if (props.initialIndex >= 0 && props.initialIndex < props.images.length) {
      imageIndex.value = props.initialIndex
    }
  }
})

watch(() => props.images, () => {
  if (imageIndex.value >= props.images.length) {
    imageIndex.value = Math.max(0, props.images.length - 1)
  }
})

const showPreviousImage = () => {
  if (imageIndex.value > 0) {
    imageIndex.value--
  }
}

const showNextImage = () => {
  if (imageIndex.value < props.images.length - 1) {
    imageIndex.value++
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!visible.value) return
  
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    showPreviousImage()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    showNextImage()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    visible.value = false
  }
}

const handleClose = () => {
  imageIndex.value = 0
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

