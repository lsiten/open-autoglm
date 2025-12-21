import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

export function useScreenStream(
  apiBaseUrl: string,
  activeDeviceId: Ref<string>
) {
  const { t } = useI18n()
  const api = axios.create({ baseURL: apiBaseUrl })
  const latestScreenshot = ref('')
  const isLandscape = ref(false)
  const fps = ref(0)
  const isStreaming = ref(false)
  const lastFrameTs = ref(0)
  const clickEffects = ref<Array<{ id: number; x: number; y: number }>>([])
  
  let frameCount = 0
  let lastFpsTime = Date.now()
  let activeRequests = 0
  const MAX_CONCURRENT_REQUESTS = 1
  const THROTTLE_MS = 200
  let lastFetchStartTime = 0
  let fetchController: AbortController | null = null
  
  // Mouse interaction state
  let isDragging = false
  let startX = 0
  let startY = 0
  let startTime = 0

  const forceRefreshFrame = () => {
    if (fetchController) {
      fetchController.abort()
    }
    lastFetchStartTime = 0
    setTimeout(() => tryFetchFrame(), 50)
  }

  const tryFetchFrame = async () => {
    const now = Date.now()
    if (now - lastFetchStartTime < THROTTLE_MS && activeRequests === 0) {
      return
    }

    if (activeRequests >= MAX_CONCURRENT_REQUESTS) return
    activeRequests++
    lastFetchStartTime = Date.now()
    
    fetchController = new AbortController()
    
    try {
      const response = await fetch(`${apiBaseUrl}/control/stream/latest`, {
        headers: { 'Cache-Control': 'no-cache' },
        signal: fetchController.signal
      })
      
      if (response.ok) {
        const tsHeader = response.headers.get('X-Timestamp')
        const currentTs = tsHeader ? parseInt(tsHeader, 10) : Date.now()
        
        if (currentTs > lastFrameTs.value) {
          lastFrameTs.value = currentTs
          
          const blob = await response.blob()
          const url = URL.createObjectURL(blob)
          
          if (latestScreenshot.value && latestScreenshot.value.startsWith('blob:')) {
            URL.revokeObjectURL(latestScreenshot.value)
          }
          
          latestScreenshot.value = url
          
          frameCount++
          const now = Date.now()
          if (now - lastFpsTime >= 1000) {
            fps.value = Math.round(frameCount * 1000 / (now - lastFpsTime))
            frameCount = 0
            lastFpsTime = now
          }
          
          const img = new Image()
          img.onload = () => { 
            isLandscape.value = img.width > img.height
            
            if (isStreaming.value && activeDeviceId.value) {
              const elapsed = Date.now() - lastFetchStartTime
              const delay = Math.max(0, THROTTLE_MS - elapsed)
              setTimeout(() => tryFetchFrame(), delay)
            }
          }
          img.onerror = () => {
            console.error(t('debug.frame_load_failed'))
            if (isStreaming.value && activeDeviceId.value) {
              setTimeout(() => tryFetchFrame(), 200)
            }
          }
          img.src = url
        } else {
          if (isStreaming.value && activeDeviceId.value) {
            const elapsed = Date.now() - lastFetchStartTime
            const delay = Math.max(0, THROTTLE_MS - elapsed)
            setTimeout(() => tryFetchFrame(), Math.max(10, delay)) 
          }
        }
      } else if (response.status === 204) {
        if (isStreaming.value && activeDeviceId.value) {
          const elapsed = Date.now() - lastFetchStartTime
          const delay = Math.max(0, THROTTLE_MS - elapsed)
          setTimeout(() => tryFetchFrame(), Math.max(10, delay))
        }
      } else {
        if (isStreaming.value) {
          if (response.status === 423) {
            console.log('Device locked, waiting...')
            setTimeout(() => tryFetchFrame(), 2000)
          } else {
            setTimeout(() => tryFetchFrame(), 200)
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return
      if (isStreaming.value) {
        setTimeout(() => tryFetchFrame(), 200)
      }
    } finally {
      activeRequests--
      fetchController = null
    }
  }

  const startStreamLoop = async () => {
    isStreaming.value = true
    
    if (activeRequests === 0) {
      tryFetchFrame()
    }

    while (isStreaming.value && activeDeviceId.value) {
      if (activeRequests < MAX_CONCURRENT_REQUESTS) {
        tryFetchFrame()
      }
      await new Promise(resolve => setTimeout(resolve, 500))
    }
  }

  const getCoords = (event: MouseEvent) => {
    const target = event.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    const width = rect.width
    const height = rect.height
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    return {
      x: Math.max(0, Math.min(1, x / width)),
      y: Math.max(0, Math.min(1, y / height))
    }
  }

  const handleMouseDown = (event: MouseEvent) => {
    if (!activeDeviceId.value) return
    isDragging = true
    const coords = getCoords(event)
    startX = coords.x
    startY = coords.y
    startTime = Date.now()
  }

  const handleMouseMove = (_event: MouseEvent) => { }

  const handleMouseUp = async (event: MouseEvent) => {
    if (!isDragging) return
    isDragging = false
    const coords = getCoords(event)
    const endX = coords.x
    const endY = coords.y
    const duration = Date.now() - startTime
    const dx = endX - startX
    const dy = endY - startY
    const dist = Math.sqrt(dx*dx + dy*dy)
    
    if (dist < 0.02) {
      const clickId = Date.now()
      const target = event.currentTarget as HTMLElement
      const rect = target.getBoundingClientRect()
      const clientX = event.clientX - rect.left
      const clientY = event.clientY - rect.top
      clickEffects.value.push({ id: clickId, x: clientX, y: clientY })
      setTimeout(() => {
        clickEffects.value = clickEffects.value.filter(c => c.id !== clickId)
      }, 500)
      try {
        await api.post('/control/tap', { x: endX, y: endY })
        forceRefreshFrame()
      } catch (e) { console.error('Tap failed', e) }
    } else {
      try {
        await api.post('/control/swipe', { x1: startX, y1: startY, x2: endX, y2: endY, duration: duration })
        forceRefreshFrame()
      } catch (e) { console.error('Swipe failed', e) }
    }
  }

  const goHome = async () => { 
    try { 
      await api.post('/control/home')
      forceRefreshFrame() 
    } catch (e) { 
      console.error(e) 
    } 
  }
  
  const goBack = async () => { 
    try { 
      await api.post('/control/back')
      forceRefreshFrame() 
    } catch (e) { 
      console.error(e) 
    } 
  }
  
  const goRecent = async () => { 
    try { 
      await api.post('/control/recent')
      forceRefreshFrame() 
    } catch (e) { 
      console.error(e) 
    } 
  }

  return {
    latestScreenshot,
    isLandscape,
    fps,
    isStreaming,
    clickEffects,
    startStreamLoop,
    forceRefreshFrame,
    getCoords,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    goHome,
    goBack,
    goRecent
  }
}

