<template>
  <div class="mt-2 w-full max-w-2xl bg-[#1c2128] border border-purple-500/30 rounded-xl overflow-hidden shadow-lg animate-fade-in">
    <div class="px-4 py-3 border-b border-gray-700/50 bg-purple-900/10 flex items-center gap-2">
      <el-icon class="text-purple-400"><Pointer /></el-icon>
      <span class="text-xs font-bold text-purple-100">{{ message.title || t('chat.click_annotation_required') }}</span>
    </div>
    <div class="p-4 space-y-4">
      <p class="text-sm text-gray-300">{{ message.content }}</p>
      
      <!-- Screenshot with annotation canvas -->
      <div v-if="!message.submitted" class="relative border border-gray-700 rounded-lg overflow-hidden bg-black">
        <img 
          ref="screenshotImg"
          :src="message.screenshot || latestScreenshot" 
          alt="Screenshot"
          class="w-full h-auto max-h-96 object-contain"
          @load="onImageLoad"
        />
        <canvas 
          ref="annotationCanvas"
          class="absolute top-0 left-0 cursor-crosshair"
          @mousedown="startDrawing"
          @mousemove="draw"
          @mouseup="stopDrawing"
          @mouseleave="stopDrawing"
        />
      </div>
      
      <!-- Annotation result display -->
      <div v-if="message.submitted && message.annotation" class="space-y-2">
        <div class="text-xs text-gray-400">
          <span class="font-semibold">{{ t('chat.annotated_position') }}:</span>
          <span class="ml-2">({{ message.annotation.x }}, {{ message.annotation.y }})</span>
        </div>
        <div v-if="message.annotation.description" class="text-xs text-gray-400">
          <span class="font-semibold">{{ t('chat.operation_description') }}:</span>
          <span class="ml-2">{{ message.annotation.description }}</span>
        </div>
      </div>
      
      <!-- Operation description input -->
      <div v-if="!message.submitted" class="space-y-2">
        <el-input
          v-model="description"
          :placeholder="t('chat.enter_operation_description')"
          type="textarea"
          :rows="2"
          size="small"
          class="text-sm"
        />
        <p class="text-xs text-gray-500">{{ t('chat.click_annotation_hint') }}</p>
      </div>
      
      <!-- Action buttons -->
      <div v-if="!message.submitted" class="flex gap-3 justify-end">
        <el-button 
          size="small"
          @click="clearAnnotation"
        >
          {{ t('common.clear') }}
        </el-button>
        <el-button 
          type="primary" 
          size="small"
          :disabled="!hasAnnotation"
          @click="submitAnnotation"
        >
          {{ t('common.submit') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { Pointer } from '@element-plus/icons-vue'

const props = defineProps<{
  message: any
  latestScreenshot?: string
}>()

const emit = defineEmits<{
  annotation: [data: { msg: any, annotation: { x: number, y: number, description: string } }]
}>()

const { t } = useI18n()

const screenshotImg = ref<HTMLImageElement | null>(null)
const annotationCanvas = ref<HTMLCanvasElement | null>(null)
const description = ref('')
const isDrawing = ref(false)
const annotations = ref<Array<{x: number, y: number}>>([])

const hasAnnotation = computed(() => annotations.value.length > 0)

let canvasCtx: CanvasRenderingContext2D | null = null
let imgWidth = 0
let imgHeight = 0
let canvasWidth = 0
let canvasHeight = 0

const onImageLoad = () => {
  if (!screenshotImg.value || !annotationCanvas.value) return
  
  const img = screenshotImg.value
  imgWidth = img.naturalWidth
  imgHeight = img.naturalHeight
  canvasWidth = img.clientWidth
  canvasHeight = img.clientHeight
  
  annotationCanvas.value.width = canvasWidth
  annotationCanvas.value.height = canvasHeight
  
  canvasCtx = annotationCanvas.value.getContext('2d')
  if (canvasCtx) {
    canvasCtx.strokeStyle = '#ff00ff'
    canvasCtx.lineWidth = 3
    canvasCtx.fillStyle = 'rgba(255, 0, 255, 0.3)'
  }
  
  redrawAnnotations()
}

const redrawAnnotations = () => {
  if (!canvasCtx || !annotationCanvas.value) return
  
  canvasCtx.clearRect(0, 0, canvasWidth, canvasHeight)
  
  annotations.value.forEach((point, index) => {
    const x = (point.x / imgWidth) * canvasWidth
    const y = (point.y / imgHeight) * canvasHeight
    
    // Draw circle
    canvasCtx!.beginPath()
    canvasCtx!.arc(x, y, 15, 0, 2 * Math.PI)
    canvasCtx!.fill()
    canvasCtx!.stroke()
    
    // Draw number
    canvasCtx!.fillStyle = '#ffffff'
    canvasCtx!.font = 'bold 12px Arial'
    canvasCtx!.textAlign = 'center'
    canvasCtx!.textBaseline = 'middle'
    canvasCtx!.fillText((index + 1).toString(), x, y)
    canvasCtx!.fillStyle = 'rgba(255, 0, 255, 0.3)'
  })
}

const startDrawing = (e: MouseEvent) => {
  if (!screenshotImg.value || !annotationCanvas.value || !canvasCtx) return
  
  isDrawing = true
  const rect = annotationCanvas.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  
  // Convert canvas coordinates to image coordinates
  const imgX = (x / canvasWidth) * imgWidth
  const imgY = (y / canvasHeight) * imgHeight
  
  annotations.value.push({ x: Math.round(imgX), y: Math.round(imgY) })
  redrawAnnotations()
}

const draw = (e: MouseEvent) => {
  // Not needed for click annotation, but required for mousemove
}

const stopDrawing = () => {
  isDrawing = false
}

const clearAnnotation = () => {
  annotations.value = []
  description.value = ''
  if (canvasCtx && annotationCanvas.value) {
    canvasCtx.clearRect(0, 0, canvasWidth, canvasHeight)
  }
}

const submitAnnotation = () => {
  if (annotations.value.length === 0) return
  
  // Use the first annotation point (or could use the last one)
  const annotation = annotations.value[0]
  
  emit('annotation', {
    msg: props.message,
    annotation: {
      x: annotation.x,
      y: annotation.y,
      description: description.value.trim()
    }
  })
}

watch(() => props.message.screenshot, () => {
  nextTick(() => {
    if (screenshotImg.value?.complete) {
      onImageLoad()
    }
  })
})

onMounted(() => {
  nextTick(() => {
    if (screenshotImg.value?.complete) {
      onImageLoad()
    }
  })
})
</script>

