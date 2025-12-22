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
  const useMjpegStream = ref(true)  // Use MJPEG stream for smoother updates
  const mjpegStreamUrl = ref('')
  
  let frameCount = 0
  let lastFpsTime = Date.now()
  let activeRequests = 0
  const MAX_CONCURRENT_REQUESTS = 1
  const THROTTLE_MS = 0  // No throttle - request immediately for maximum responsiveness
  let lastFetchStartTime = 0
  let fetchController: AbortController | null = null
  
  // Performance monitoring
  let requestStartTime = 0
  let frameReceiveTime = 0
  
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
    // Remove throttle check for maximum responsiveness
    // Only check if there's already an active request
    if (activeRequests >= MAX_CONCURRENT_REQUESTS) return
    activeRequests++
    requestStartTime = Date.now()
    lastFetchStartTime = requestStartTime
    
    fetchController = new AbortController()
    
    try {
      const response = await fetch(`${apiBaseUrl}/control/stream/latest`, {
        headers: { 
          'Cache-Control': 'no-cache',
          'Accept-Encoding': 'gzip'  // Request gzip compression
        },
        signal: fetchController.signal
      })
      
      if (response.ok) {
        const tsHeader = response.headers.get('X-Timestamp')
        const currentTs = tsHeader ? parseInt(tsHeader, 10) : Date.now()
        
        if (currentTs > lastFrameTs.value) {
          lastFrameTs.value = currentTs
          frameReceiveTime = Date.now()
          
          const blob = await response.blob()
          const url = URL.createObjectURL(blob)
          
          if (latestScreenshot.value && latestScreenshot.value.startsWith('blob:')) {
            URL.revokeObjectURL(latestScreenshot.value)
          }
          
          latestScreenshot.value = url
          
          // Count FPS only for actual new frames (timestamp changed)
          frameCount++
          const now = Date.now()
          const timeElapsed = now - lastFpsTime
          if (timeElapsed >= 1000) {
            // Calculate FPS: frames received in the last second
            fps.value = Math.round((frameCount * 1000) / timeElapsed)
            frameCount = 0
            lastFpsTime = now
          }
          
          // Landscape detection is handled by ScreenMirror component via @load event
          // No need to detect here to avoid conflicts
          
          // Immediately request next frame without waiting for image load
          // This ensures continuous streaming
          if (isStreaming.value && activeDeviceId.value) {
            // Request immediately for maximum responsiveness
            // Use requestAnimationFrame for smoother updates
            requestAnimationFrame(() => {
              if (isStreaming.value && activeDeviceId.value) {
                tryFetchFrame()
              }
            })
          }
        } else {
          // Timestamp not updated - frame unchanged, but still retry quickly
          // Use shorter delay to maintain smooth updates
          if (isStreaming.value && activeDeviceId.value) {
            requestAnimationFrame(() => {
              if (isStreaming.value && activeDeviceId.value) {
                tryFetchFrame()
              }
            })
          }
        }
      } else if (response.status === 204) {
        // No new content - retry immediately with requestAnimationFrame
        if (isStreaming.value && activeDeviceId.value) {
          requestAnimationFrame(() => {
            if (isStreaming.value && activeDeviceId.value) {
              tryFetchFrame()
            }
          })
        }
      } else {
        if (isStreaming.value) {
          if (response.status === 423) {
            console.log('Device locked, waiting...')
            setTimeout(() => tryFetchFrame(), 2000)
          } else if (response.status === 503) {
            // Service unavailable - retry quickly but not too aggressively
            setTimeout(() => tryFetchFrame(), 100)
          } else {
            // Other errors - retry after short delay
            setTimeout(() => tryFetchFrame(), 100)
          }
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') return
      if (isStreaming.value) {
        // Network errors - retry after short delay
        setTimeout(() => tryFetchFrame(), 100)
      }
    } finally {
      activeRequests--
      fetchController = null
    }
  }

  const startStreamLoop = async () => {
    // Don't start multiple loops
    if (isStreaming.value) {
      return
    }
    
    isStreaming.value = true
    
    // Reset FPS counters when starting stream
    frameCount = 0
    lastFpsTime = Date.now()
    fps.value = 0
    
    // Try MJPEG stream first if enabled
    if (useMjpegStream.value && activeDeviceId.value) {
      mjpegStreamUrl.value = `${apiBaseUrl}/control/stream/mjpeg`
      // MJPEG stream will be handled by img tag directly
      // Start FPS monitoring for MJPEG stream based on image load events
      let mjpegFrameCount = 0
      let mjpegLastFpsTime = Date.now()
      
      // Monitor MJPEG stream by checking if URL is accessible
      // If MJPEG fails, fallback to HTTP polling
      const checkMjpegHealth = setInterval(() => {
        if (!isStreaming.value) {
          clearInterval(checkMjpegHealth)
          return
        }
        // If MJPEG URL is set but no image loaded after 3 seconds, fallback
        if (mjpegStreamUrl.value && !latestScreenshot.value) {
          const timeSinceStart = Date.now() - mjpegLastFpsTime
          if (timeSinceStart > 3000) {
            console.warn('[useScreenStream] MJPEG stream not loading, falling back to HTTP polling')
            useMjpegStream.value = false
            mjpegStreamUrl.value = ''
            clearInterval(checkMjpegHealth)
            // Start HTTP polling fallback
            if (activeRequests === 0) {
              tryFetchFrame()
            }
          }
        }
      }, 1000)
      return
    }
    
    // Fallback to HTTP polling
    // Start initial frame fetch immediately
    if (activeRequests === 0) {
      tryFetchFrame()
    }

    // Keep the loop running to ensure continuous updates
    // Use aggressive polling to maintain smooth streaming
    while (isStreaming.value && activeDeviceId.value) {
      // Check if we need to trigger a new fetch
      // The recursive calls in tryFetchFrame should handle most updates,
      // but this loop ensures we don't miss any updates
      if (activeRequests < MAX_CONCURRENT_REQUESTS) {
        const timeSinceLastFetch = Date.now() - lastFetchStartTime
        // If it's been too long since last fetch, force a refresh
        // This ensures updates continue even if recursive calls fail
        // Use 100ms timeout instead of THROTTLE_MS * 2 (since THROTTLE_MS is 0)
        if (timeSinceLastFetch > 100) {
          tryFetchFrame()
        }
      }
      // More aggressive polling for smoother updates
      await new Promise(resolve => setTimeout(resolve, 16)) // ~60fps check rate for maximum responsiveness
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
        // Force immediate refresh and ensure stream continues
        forceRefreshFrame()
        // Also ensure stream loop is running (important during recording)
        if (!isStreaming.value && activeDeviceId.value) {
          startStreamLoop()
        }
      } catch (e) { console.error('Tap failed', e) }
    } else {
      try {
        await api.post('/control/swipe', { x1: startX, y1: startY, x2: endX, y2: endY, duration: duration })
        // Force immediate refresh and ensure stream continues
        forceRefreshFrame()
        // Also ensure stream loop is running (important during recording)
        if (!isStreaming.value && activeDeviceId.value) {
          startStreamLoop()
        }
      } catch (e) { console.error('Swipe failed', e) }
    }
  }

  const goHome = async () => { 
    try { 
      await api.post('/control/home')
      // Force immediate refresh and ensure stream continues
      forceRefreshFrame()
      // Also ensure stream loop is running
      if (!isStreaming.value && activeDeviceId.value) {
        startStreamLoop()
      }
    } catch (e) { 
      console.error(e) 
    } 
  }
  
  const goBack = async () => { 
    try { 
      await api.post('/control/back')
      // Force immediate refresh and ensure stream continues
      forceRefreshFrame()
      // Also ensure stream loop is running
      if (!isStreaming.value && activeDeviceId.value) {
        startStreamLoop()
      }
    } catch (e) { 
      console.error(e) 
    } 
  }
  
  const goRecent = async () => { 
    try { 
      await api.post('/control/recent')
      // Force immediate refresh and ensure stream continues
      forceRefreshFrame()
      // Also ensure stream loop is running
      if (!isStreaming.value && activeDeviceId.value) {
        startStreamLoop()
      }
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
    useMjpegStream,
    mjpegStreamUrl,
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

