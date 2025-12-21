import { ref, type Ref } from 'vue'

export function useImagePreview(chatHistory: Ref<any[]>) {
  const imagePreviewVisible = ref(false)
  const imagePreviewUrl = ref('')
  const imagePreviewIndex = ref(0)
  const sessionImages = ref<string[]>([])

  const openImagePreview = (imageUrl: string) => {
    // Collect all images from current session
    const images: string[] = []
    chatHistory.value.forEach((msg: any) => {
      if (msg.screenshot) {
        images.push(msg.screenshot)
      }
    })
    
    if (images.length === 0) {
      return
    }
    
    sessionImages.value = images
    const index = images.indexOf(imageUrl)
    imagePreviewIndex.value = index >= 0 ? index : 0
    imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    imagePreviewVisible.value = true
  }

  const showPreviousImage = () => {
    if (imagePreviewIndex.value > 0) {
      imagePreviewIndex.value--
      imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    }
  }

  const showNextImage = () => {
    if (imagePreviewIndex.value < sessionImages.value.length - 1) {
      imagePreviewIndex.value++
      imagePreviewUrl.value = sessionImages.value[imagePreviewIndex.value]
    }
  }

  const handleImagePreviewKeydown = (e: KeyboardEvent) => {
    if (!imagePreviewVisible.value) return
    
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      showPreviousImage()
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      showNextImage()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      imagePreviewVisible.value = false
    }
  }

  return {
    imagePreviewVisible,
    imagePreviewUrl,
    imagePreviewIndex,
    sessionImages,
    openImagePreview,
    showPreviousImage,
    showNextImage,
    handleImagePreviewKeydown
  }
}

