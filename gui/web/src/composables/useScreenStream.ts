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
  const useVideoStream = ref(true)  // Use H.264 video stream (MSE) for best performance
  const videoStreamUrl = ref('')
  const videoElement = ref<HTMLVideoElement | null>(null)
  
  let frameCount = 0
  let lastFpsTime = Date.now()
  let activeRequests = 0
  const MAX_CONCURRENT_REQUESTS = 1
  const THROTTLE_MS = 0  // No throttle - request immediately for maximum responsiveness
  let lastFetchStartTime = 0
  let fetchController: AbortController | null = null
  
  // WebSocket connection for frame streaming
  let wsConnection: WebSocket | null = null
  let wsReconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 5
  let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
  let usingWebSocket = false // Flag to track if we're using WebSocket
  
  // Video stream (MSE) state
  let mediaSource: MediaSource | null = null
  let sourceBuffer: SourceBuffer | null = null
  let streamReader: ReadableStreamDefaultReader<Uint8Array> | null = null
  let videoAbortController: AbortController | null = null
  let usingVideoStream = false // Flag to track if we're using video stream
  
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
    // Don't use HTTP polling if WebSocket is active
    if (usingWebSocket && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      return // WebSocket is handling frames, skip HTTP polling
    }
    
    // Don't use HTTP polling if video stream is active
    if (usingVideoStream) {
      return // Video stream is handling frames, skip HTTP polling
    }
    
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

  const connectWebSocket = (): Promise<boolean> => {
    return new Promise((resolve) => {
      if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        resolve(true)
        return // Already connected
      }

      // Convert HTTP/HTTPS URL to WebSocket URL
      let wsUrl = apiBaseUrl.replace(/^http/, 'ws')
      if (apiBaseUrl.startsWith('https://')) {
        wsUrl = apiBaseUrl.replace(/^https/, 'wss')
      }
      wsUrl = wsUrl + '/control/stream/ws'
    
    try {
      wsConnection = new WebSocket(wsUrl)
      
      wsConnection.onopen = () => {
        console.log('[useScreenStream] WebSocket connected for frame streaming')
        wsReconnectAttempts = 0
        usingWebSocket = true // Mark that we're using WebSocket
        resolve(true) // Resolve promise when connected
      }
      
      wsConnection.onmessage = (event) => {
        if (event.data === 'ping') {
          // Respond to ping to keep connection alive
          if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send('pong')
          }
          return
        }
        
        if (event.data === 'pong') {
          return // Ignore pong responses
        }
        
        // Process frame asynchronously but don't block message handler
        // This ensures we can receive the next frame immediately
        ;(async () => {
          try {
            const message = JSON.parse(event.data)
            if (message.type === 'frame' && message.data) {
              // Decode base64 frame data
              let frameBytes = Uint8Array.from(atob(message.data), c => c.charCodeAt(0))
              
              // Decompress if data is compressed (non-blocking)
              if (message.compressed) {
                try {
                  // Use native DecompressionStream (Chrome 113+, Firefox 113+)
                  if (typeof window !== 'undefined' && 'DecompressionStream' in window) {
                    const stream = new DecompressionStream('gzip')
                    const writer = stream.writable.getWriter()
                    const reader = stream.readable.getReader()
                    
                    await writer.write(frameBytes)
                    await writer.close()
                    
                    const chunks: Uint8Array[] = []
                    let done = false
                    while (!done) {
                      const { value, done: streamDone } = await reader.read()
                      done = streamDone
                      if (value) chunks.push(value)
                    }
                    
                    // Combine chunks
                    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
                    frameBytes = new Uint8Array(totalLength)
                    let offset = 0
                    for (const chunk of chunks) {
                      frameBytes.set(chunk, offset)
                      offset += chunk.length
                    }
                  } else {
                    // Fallback: log warning (shouldn't happen in modern browsers)
                    console.warn('[useScreenStream] DecompressionStream not available')
                    return // Skip compressed frame if we can't decompress
                  }
                } catch (decompressError) {
                  console.error('[useScreenStream] Failed to decompress frame:', decompressError)
                  return // Skip this frame
                }
              }
              
              const blob = new Blob([frameBytes], { type: 'image/jpeg' })
              const url = URL.createObjectURL(blob)
              
              // Update frame timestamp - similar to HTTP logic
              const currentTs = message.timestamp || Date.now()
              
              // Always update if timestamp is newer, or if it's the same (for continuous updates)
              // This matches HTTP behavior where we update even if timestamp is same
              // For smooth animations, update immediately without waiting
              if (currentTs >= lastFrameTs.value) {
                lastFrameTs.value = currentTs
                frameReceiveTime = Date.now()
                
                // Clean up old blob URL asynchronously to avoid blocking frame update
                const oldUrl = latestScreenshot.value
                // Update frame immediately for smooth animation
                latestScreenshot.value = url
                
                // Clean up old URL after a short delay to avoid blocking
                if (oldUrl && oldUrl.startsWith('blob:')) {
                  setTimeout(() => URL.revokeObjectURL(oldUrl), 100)
                }
                
                // Update FPS - count all frames received
                frameCount++
                const now = Date.now()
                const timeElapsed = now - lastFpsTime
                if (timeElapsed >= 1000) {
                  fps.value = Math.round((frameCount * 1000) / timeElapsed)
                  frameCount = 0
                  lastFpsTime = now
                }
              }
            }
          } catch (e) {
            console.error('[useScreenStream] Error parsing WebSocket message:', e)
          }
        })() // Immediately invoke async function, don't await
      }
      
      wsConnection.onerror = (error) => {
        console.error('[useScreenStream] WebSocket error:', error)
        resolve(false) // Resolve as failed
      }
      
      wsConnection.onclose = () => {
        console.log('[useScreenStream] WebSocket closed')
        wsConnection = null
        usingWebSocket = false // Mark that we're no longer using WebSocket
        
        // Attempt to reconnect if streaming is still active
        if (isStreaming.value && activeDeviceId.value && wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          wsReconnectAttempts++
          const delay = Math.min(1000 * wsReconnectAttempts, 5000) // Exponential backoff, max 5s
          console.log(`[useScreenStream] Reconnecting WebSocket in ${delay}ms (attempt ${wsReconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
          wsReconnectTimer = setTimeout(() => {
            connectWebSocket()
          }, delay)
        } else if (isStreaming.value && activeDeviceId.value) {
          // Fallback to HTTP polling if WebSocket fails
          console.warn('[useScreenStream] WebSocket connection failed, falling back to HTTP polling')
          usingWebSocket = false
          if (activeRequests === 0) {
            tryFetchFrame()
          }
        }
      }
      
      // Set timeout to resolve if connection doesn't establish quickly
      setTimeout(() => {
        if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
          if (!usingWebSocket) {
            resolve(false)
          }
        }
      }, 2000) // 2 second timeout
    } catch (error) {
      console.error('[useScreenStream] Failed to create WebSocket:', error)
      usingWebSocket = false
      resolve(false) // Resolve as failed
    }
    }) // Close Promise
  }

  const disconnectWebSocket = () => {
    usingWebSocket = false
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer)
      wsReconnectTimer = null
    }
    if (wsConnection) {
      wsConnection.close()
      wsConnection = null
    }
    wsReconnectAttempts = 0
  }

  /**
   * Start H.264 video stream using MSE (MediaSource Extensions) API.
   * This is the highest priority streaming method for best performance.
   */
  const startVideoStream = async (videoEl: HTMLVideoElement): Promise<boolean> => {
    if (!activeDeviceId.value) {
      console.warn('[useScreenStream] No device selected, cannot start video stream')
      return false
    }

    try {
      // Clean up any existing MediaSource first
      if (mediaSource) {
        try {
          // Only call endOfStream if we have data in the buffer
          // Otherwise it causes DEMUXER_ERROR_COULD_NOT_OPEN
          if (mediaSource.readyState === 'open' && sourceBuffer) {
            // Wait for sourceBuffer to finish updating
            if (sourceBuffer.updating) {
              await new Promise<void>((resolve) => {
                sourceBuffer!.addEventListener('updateend', () => resolve(), { once: true })
              })
            }
            // Only end stream if we have buffered data
            if (sourceBuffer.buffered.length > 0) {
              mediaSource.endOfStream()
            }
          }
        } catch (e) {
          // Ignore cleanup errors
          console.warn('[useScreenStream] Error cleaning up MediaSource:', e)
        }
        if (videoEl.src && videoEl.src.startsWith('blob:')) {
          URL.revokeObjectURL(videoEl.src)
        }
        mediaSource = null
        sourceBuffer = null
      }
      
      // Clear any existing source buffer
      if (sourceBuffer) {
        try {
          if (sourceBuffer.updating) {
            sourceBuffer.abort()
          }
        } catch (e) {
          // Ignore cleanup errors
        }
        sourceBuffer = null
      }
      
      videoElement.value = videoEl
      
      // Check if MediaSource is supported
      if (!('MediaSource' in window)) {
        console.warn('[useScreenStream] MediaSource API not supported, falling back to other methods')
        return false
      }

      // Create MediaSource
      mediaSource = new MediaSource()
      const url = URL.createObjectURL(mediaSource)
      
      // Set src BEFORE checking for errors
      videoEl.src = url
      videoEl.load() // Explicitly load the new source
      
      console.log('[useScreenStream] MediaSource created, URL:', url)
      console.log('[useScreenStream] Video element src set to:', videoEl.src)

      // Wait for MediaSource to be ready
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('MediaSource sourceopen timeout'))
        }, 5000)
        
        mediaSource!.addEventListener('sourceopen', () => {
          clearTimeout(timeout)
          try {
            console.log('[useScreenStream] MediaSource sourceopen event fired')
            
            // Check video element error before proceeding
            if (videoEl.error) {
              reject(new Error(`Video element error before sourceopen: ${videoEl.error.message || 'Unknown'}`))
              return
            }
            
            // Add MP4 source buffer for fragmented MP4
            const codecOptions = [
              'video/mp4; codecs="avc1.42E01E"',  // Baseline profile, level 3.0
              'video/mp4; codecs="avc1.640028"',  // High profile, level 4.0
              'video/mp4; codecs="avc1.4D001E"',  // Main profile, level 3.0
              'video/mp4; codecs="avc1.64001E"',  // High profile, level 3.0
              'video/mp4'  // Fallback
            ]
            
            let supported = false
            for (const mimeType of codecOptions) {
              if (MediaSource.isTypeSupported(mimeType)) {
                console.log(`[useScreenStream] Using codec: ${mimeType}`)
                sourceBuffer = mediaSource!.addSourceBuffer(mimeType)
                supported = true
                break
              }
            }
            
            if (!supported) {
              reject(new Error('MP4/H.264 codec not supported'))
              return
            }

            sourceBuffer!.mode = 'sequence'
            
            // Listen for sourceBuffer errors
            sourceBuffer!.addEventListener('error', (e) => {
              console.error('[useScreenStream] SourceBuffer error:', e)
            })
            
            // Listen for video element errors
            videoEl.addEventListener('error', (e) => {
              console.error('[useScreenStream] Video element error:', videoEl.error)
            })
            
            console.log('[useScreenStream] SourceBuffer created successfully')
            resolve()
          } catch (e) {
            clearTimeout(timeout)
            reject(e)
          }
        }, { once: true })

        mediaSource!.addEventListener('error', (e) => {
          clearTimeout(timeout)
          console.error('[useScreenStream] MediaSource error event:', e)
          reject(new Error('MediaSource error'))
        }, { once: true })
      })

      // Set a timeout to detect if video stream doesn't start receiving data
      let streamStartTimeout: ReturnType<typeof setTimeout> | null = null
      let hasReceivedDataRef = { value: false }  // Use object to share state between functions
      let streamStartTime = Date.now()
      
      streamStartTimeout = setTimeout(() => {
        if (usingVideoStream && !hasReceivedDataRef.value) {
          const elapsed = Date.now() - streamStartTime
          console.warn(`[useScreenStream] Video stream timeout - no data received after ${elapsed}ms, falling back to image stream`)
          console.warn('[useScreenStream] Possible causes:')
          console.warn('  1. Backend VideoStreamer is not sending data')
          console.warn('  2. scrcpy/ffmpeg processes failed to start')
          console.warn('  3. Network connection issue')
          console.warn('  4. Device not connected or scrcpy unavailable')
          stopVideoStream()
          useVideoStream.value = false
          // Trigger restart of stream loop to use image stream
          if (activeDeviceId.value) {
            setTimeout(() => {
              startStreamLoop()
            }, 100)
          }
        }
      }, 8000)  // Increase to 8 seconds to give backend more time to start scrcpy/ffmpeg
      
      // Start fetching H.264 stream in background (don't await - let it run continuously)
      // The stream will run in the background and append data to sourceBuffer
      // Pass streamStartTimeout and hasReceivedDataRef so fetchVideoStream can update them
      fetchVideoStream(streamStartTimeout, hasReceivedDataRef)
        .then(() => {
          if (streamStartTimeout) {
            clearTimeout(streamStartTimeout)
          }
        })
        .catch((e) => {
          if (streamStartTimeout) {
            clearTimeout(streamStartTimeout)
          }
          
          // Check if this is a stream end error (not a fatal error)
          const isStreamEndError = e.message && (
            e.message.includes('Video stream ended') ||
            e.message.includes('will attempt to reconnect')
          )
          
          if (isStreamEndError && hasReceivedDataRef.value) {
            // Stream ended but we received data - backend may have stopped
            // Wait a bit and try to reconnect
            console.log('[useScreenStream] Stream ended after receiving data, will attempt reconnect in 2 seconds...')
            setTimeout(() => {
              if (activeDeviceId.value && useVideoStream.value) {
                console.log('[useScreenStream] Attempting to reconnect video stream...')
                startVideoStream(videoElement.value!)
                  .then((success) => {
                    if (success) {
                      console.log('[useScreenStream] ✅ Video stream reconnected successfully')
                    } else {
                      console.warn('[useScreenStream] Video stream reconnection failed, falling back')
                      stopVideoStream()
                      useVideoStream.value = false
                      startStreamLoop()
                    }
                  })
                  .catch((reconnectError) => {
                    console.error('[useScreenStream] Video stream reconnection error:', reconnectError)
                    stopVideoStream()
                    useVideoStream.value = false
                    startStreamLoop()
                  })
              }
            }, 2000)
            return // Don't stop stream yet, wait for reconnect
          }
          
          console.error('[useScreenStream] Video stream fetch error:', e)
          // If stream fails after starting, stop and fallback
          stopVideoStream()
          useVideoStream.value = false
          // Trigger restart of stream loop to use image stream
          if (activeDeviceId.value) {
            setTimeout(() => {
              startStreamLoop()
            }, 100)
          }
        })
      
      usingVideoStream = true
      useVideoStream.value = true  // Ensure this is true so video element is shown
      videoStreamUrl.value = `${apiBaseUrl}/control/stream/video`
      console.log('[useScreenStream] ✅ Video stream (MSE) started successfully, video element should be visible')
      return true
    } catch (e: any) {
      console.warn(`[useScreenStream] Video stream failed: ${e.message || e}`, e)
      stopVideoStream()
      // Disable video stream to allow fallback to other methods
      useVideoStream.value = false
      return false
    }
  }

  /**
   * Fetch H.264 video stream and append to source buffer.
   */
  const fetchVideoStream = async (timeoutRef?: ReturnType<typeof setTimeout> | null, hasReceivedDataRef?: { value: boolean }) => {
    if (!sourceBuffer || !activeDeviceId.value) {
      return
    }

    videoAbortController = new AbortController()
    const streamUrl = `${apiBaseUrl}/control/stream/video`

    try {
      console.log(`[useScreenStream] Fetching video stream from: ${streamUrl}`)
      const fetchStartTime = Date.now()
      const response = await fetch(streamUrl, {
        signal: videoAbortController.signal,
        headers: {
          'Accept': 'video/mp4'
        }
      })
      
      const fetchTime = Date.now() - fetchStartTime
      console.log(`[useScreenStream] Video stream response received (${fetchTime}ms): status=${response.status}, ok=${response.ok}`)
      console.log(`[useScreenStream] Response headers:`, Object.fromEntries(response.headers.entries()))

      if (!response.ok) {
        console.error(`[useScreenStream] Video stream HTTP error: ${response.status} ${response.statusText}`)
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      streamReader = response.body.getReader()
      const streamReadStartTime = Date.now()
      console.log('[useScreenStream] Video stream reader created, starting to read chunks...')

      // Set a timeout to detect if stream is not receiving data
      let lastChunkTime = Date.now()
      const STREAM_TIMEOUT = 10000  // 10 seconds timeout
      let chunks_yielded = 0  // Track chunks for logging
      let hasReceivedDataInReader = false  // Track if we've received data in the reader
      
      // Process stream chunks continuously
      while (true) {
        const { done, value } = await streamReader.read()
        
        if (done) {
          // Stream ended - this could be normal (connection closed) or an error
          // Check if we received any data before the stream ended
          if (hasReceivedDataInReader && chunks_yielded > 0) {
            console.warn('[useScreenStream] Video stream ended after receiving data - backend may have stopped streaming')
            // Don't throw error immediately - try to reconnect
            // The error will be caught and handled by startVideoStream
            throw new Error('Video stream ended - will attempt to reconnect')
          } else {
            console.warn('[useScreenStream] Video stream ended without receiving data - backend may not be ready')
            throw new Error('Video stream ended without data - backend not ready')
          }
        }
        
        if (!value || value.length === 0) {
          // Empty chunk, check timeout
          if (Date.now() - lastChunkTime > STREAM_TIMEOUT) {
            console.error('[useScreenStream] Video stream timeout - no data received for 10 seconds')
            throw new Error('Video stream timeout - no data received')
          }
          // Wait a bit before next read
          await new Promise(resolve => setTimeout(resolve, 100))
          continue
        }
        
        // Update last chunk time and mark that we've received data
        lastChunkTime = Date.now()
        if (!hasReceivedDataInReader) {
          hasReceivedDataInReader = true
          const timeToFirstChunk = Date.now() - streamReadStartTime
          console.log(`[useScreenStream] ✅ First video chunk received (${value.length} bytes) after ${timeToFirstChunk}ms`)
          // Clear the timeout since we received data
          if (timeoutRef) {
            clearTimeout(timeoutRef)
          }
        }

        // Check if MediaSource and video element are still valid BEFORE processing chunk
        if (!mediaSource) {
          console.warn('[useScreenStream] MediaSource is null, stopping stream')
          throw new Error('MediaSource is null')
        }
        
        if (mediaSource.readyState !== 'open') {
          console.warn(`[useScreenStream] MediaSource is not open (state: ${mediaSource.readyState}), stopping stream`)
          throw new Error(`MediaSource is not open, state: ${mediaSource.readyState}`)
        }
        
        if (videoElement.value && videoElement.value.error) {
          const errorCode = videoElement.value.error.code
          const errorMessage = videoElement.value.error.message || 'Unknown error'
          console.error('[useScreenStream] Video element has error:', {
            code: errorCode,
            message: errorMessage
          })
          throw new Error(`Video element error: code ${errorCode}, ${errorMessage}`)
        }
        
        if (!sourceBuffer) {
          console.warn('[useScreenStream] SourceBuffer is null, stopping stream')
          throw new Error('SourceBuffer is null')
        }

        // Wait for source buffer to be ready (must wait if updating)
        if (sourceBuffer.updating) {
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error('SourceBuffer updateend timeout'))
            }, 5000)
            
            sourceBuffer!.addEventListener('updateend', () => {
              clearTimeout(timeout)
              resolve()
            }, { once: true })
            
            sourceBuffer!.addEventListener('error', (e) => {
              clearTimeout(timeout)
              reject(new Error(`SourceBuffer error: ${e}`))
            }, { once: true })
          })
        }

        // Append MP4 fragment data to source buffer
        try {
          // Final check before appending
          if (sourceBuffer.updating) {
            console.warn('[useScreenStream] SourceBuffer is still updating after wait, skipping chunk')
            continue
          }
          
          if (mediaSource.readyState !== 'open') {
            console.warn('[useScreenStream] MediaSource closed during append, stopping')
            throw new Error('MediaSource closed during append')
          }
          
          // Append buffer (we already waited if it was updating)
          sourceBuffer.appendBuffer(value)
          chunks_yielded++
          if (chunks_yielded === 1) {
            if (hasReceivedDataRef) {
              hasReceivedDataRef.value = true
            }
            console.log('[useScreenStream] ✅ First video chunk appended to source buffer, video stream is working')
            if (timeoutRef) {
              clearTimeout(timeoutRef)
            }
          }
        } catch (e: any) {
          if (e.name === 'QuotaExceededError') {
            // Buffer is full, remove old data
            if (sourceBuffer && sourceBuffer.buffered.length > 0) {
              try {
                sourceBuffer.remove(0, sourceBuffer.buffered.start(1) || sourceBuffer.buffered.end(0))
              } catch {
                // Ignore remove errors
              }
            }
            await new Promise(resolve => setTimeout(resolve, 100))
            continue
          }
          
          // Check if video element has error
          if (videoElement.value && videoElement.value.error) {
            console.error('[useScreenStream] Video element error detected:', {
              code: videoElement.value.error.code,
              message: videoElement.value.error.message
            })
            throw new Error(`Video element error: code ${videoElement.value.error.code}, ${videoElement.value.error.message || 'Unknown error'}`)
          }
          
          // Check if MediaSource is still open
          if (mediaSource && mediaSource.readyState !== 'open') {
            console.error('[useScreenStream] MediaSource is not open, state:', mediaSource.readyState)
            throw new Error(`MediaSource is not open, state: ${mediaSource.readyState}`)
          }
          
          console.error('[useScreenStream] Error appending buffer:', e)
          throw e
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // Stream was aborted, this is normal
        return
      }
      // Re-throw to be handled by startVideoStream
      throw e
    }
  }

  /**
   * Stop video streaming and cleanup resources.
   */
  const stopVideoStream = () => {
    usingVideoStream = false
    videoStreamUrl.value = ''

    // Abort fetch if in progress
    if (videoAbortController) {
      videoAbortController.abort()
      videoAbortController = null
    }

    // Close stream reader
    if (streamReader) {
      streamReader.cancel().catch(() => {})
      streamReader = null
    }

    // Clean up source buffer
    const currentSourceBuffer = sourceBuffer
    if (currentSourceBuffer) {
      try {
        if (currentSourceBuffer.updating) {
          currentSourceBuffer.abort()
        }
      } catch (e) {
        // Ignore errors
      }
      sourceBuffer = null
    }

    // Clean up MediaSource
    const currentMediaSource = mediaSource
    if (currentMediaSource) {
      try {
        // Only call endOfStream if we have data in the buffer
        // Otherwise it causes DEMUXER_ERROR_COULD_NOT_OPEN
        // Note: We check currentSourceBuffer (captured before setting to null)
        // and only end stream if we actually have buffered data
        if (currentMediaSource.readyState === 'open' && currentSourceBuffer) {
          // Only end stream if we have buffered data (metadata received)
          if (currentSourceBuffer.buffered.length > 0) {
            try {
              currentMediaSource.endOfStream()
            } catch (e) {
              // Ignore errors - MediaSource may already be closed
              console.warn('[useScreenStream] Error calling endOfStream:', e)
            }
          }
          // If no buffered data, don't call endOfStream - just close
        }
      } catch (e) {
        // Ignore cleanup errors
        console.warn('[useScreenStream] Error ending MediaSource stream:', e)
      }
      
      if (videoElement.value) {
        const currentSrc = videoElement.value.src
        if (currentSrc && currentSrc.startsWith('blob:')) {
          URL.revokeObjectURL(currentSrc)
        }
        // Don't set src to empty string - let it be cleared naturally
        // Setting to empty string can trigger error events
      }
      
      mediaSource = null
    }

    videoElement.value = null
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
    
    if (!activeDeviceId.value) {
      console.warn('[useScreenStream] No device selected, cannot start streaming')
      isStreaming.value = false
      return
    }
    
    // Priority 1: Try H.264 video stream (MSE) first (best performance, lowest latency, continuous stream)
    // This uses scrcpy's H.264 video stream for optimal performance
    // Note: videoElement should be set by the component before calling startStreamLoop
    if (useVideoStream.value) {
      // Wait longer for video element to be ready (component might not be mounted yet)
      let retries = 10
      while (!videoElement.value && retries > 0) {
        console.log(`[useScreenStream] Waiting for video element... (${retries} retries left)`)
        await new Promise(resolve => setTimeout(resolve, 200))
        retries--
      }
      
      if (videoElement.value) {
        console.log('[useScreenStream] Attempting H.264 video stream (MSE) (priority 1: best performance)')
        try {
          const videoStarted = await startVideoStream(videoElement.value)
          if (videoStarted) {
            console.log('[useScreenStream] ✅ Using H.264 video stream (MSE) (best performance, continuous stream)')
            // Don't return immediately - let the stream start in background
            // But mark that we're using video stream so we don't start other methods
            usingVideoStream = true
            return // Exit early, video stream is active
          }
        } catch (e) {
          console.error('[useScreenStream] Video stream start error:', e)
        }
        // Video stream failed, disable it and continue to fallback methods
        console.warn('[useScreenStream] Video stream failed, disabling and trying fallback methods')
        stopVideoStream() // Ensure cleanup
        useVideoStream.value = false
        videoStreamUrl.value = '' // Clear video stream URL
        // Continue to try other methods below
      } else {
        console.warn('[useScreenStream] Video element still not ready after waiting, skipping video stream')
        // Don't disable video stream - maybe it will be ready next time
        // Just continue to fallback methods for now
      }
    }
    
    // Priority 2: Try WebSocket (good performance, low latency, but frame-by-frame)
    console.log('[useScreenStream] Attempting WebSocket connection (priority 2: good performance)')
    const wsConnected = await connectWebSocket()
    
    // If WebSocket is connected, we're done - no HTTP polling needed
    if (wsConnected && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      console.log('[useScreenStream] ✅ Using WebSocket for frame streaming (good performance, no HTTP polling)')
      return // Exit early, don't start HTTP polling
    }
    
    // Priority 3: Try MJPEG stream if WebSocket failed (good performance, continuous stream)
    if (useMjpegStream.value) {
      console.log('[useScreenStream] WebSocket failed, trying MJPEG stream (priority 3: good performance)')
      mjpegStreamUrl.value = `${apiBaseUrl}/control/stream/mjpeg`
      // MJPEG stream will be handled by img tag directly
      let mjpegStartTime = Date.now()
      
      // Monitor MJPEG stream by checking if URL is accessible
      // If MJPEG fails, fallback to HTTP polling
      const checkMjpegHealth = setInterval(() => {
        if (!isStreaming.value) {
          clearInterval(checkMjpegHealth)
          return
        }
        // If MJPEG URL is set but no image loaded after 3 seconds, fallback
        const timeSinceStart = Date.now() - mjpegStartTime
        if (mjpegStreamUrl.value && !latestScreenshot.value && timeSinceStart > 3000) {
          console.warn('[useScreenStream] MJPEG stream not loading after 3s, falling back to HTTP polling')
          useMjpegStream.value = false
          mjpegStreamUrl.value = ''
          clearInterval(checkMjpegHealth)
          // Start HTTP polling fallback
          if (activeRequests === 0) {
            tryFetchFrame()
          }
        } else if (latestScreenshot.value) {
          // MJPEG is working, clear the health check
          clearInterval(checkMjpegHealth)
          console.log('[useScreenStream] ✅ Using MJPEG stream (good performance)')
        }
      }, 1000)
      return
    }
    
    // Priority 4: Fallback to HTTP polling (lowest performance, highest latency)
    console.log('[useScreenStream] Using HTTP polling for frame streaming (reliable fallback method)')
    // Start initial frame fetch immediately
    if (activeRequests === 0) {
      console.log('[useScreenStream] Starting HTTP polling loop...')
      tryFetchFrame()
    } else {
      console.log('[useScreenStream] HTTP polling already active, skipping start')
    }

    // Keep the loop running to ensure continuous updates
    // Use aggressive polling to maintain smooth streaming
    // BUT: Skip HTTP polling loop if WebSocket is active
    if (usingWebSocket && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
      // WebSocket is handling frames, just monitor connection status
      while (isStreaming.value && activeDeviceId.value) {
        // Check if WebSocket is still connected
        if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
          // WebSocket disconnected, fallback to HTTP polling
          usingWebSocket = false
          break
        }
        await new Promise(resolve => setTimeout(resolve, 1000)) // Check every second
      }
    } else {
      // HTTP polling loop (fallback when WebSocket is not available)
      while (isStreaming.value && activeDeviceId.value) {
        // Don't poll if WebSocket becomes available
        if (usingWebSocket && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
          break // Switch to WebSocket mode
        }
        
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

  const stopStreamLoop = () => {
    isStreaming.value = false
    stopVideoStream()
    disconnectWebSocket()
    if (fetchController) {
      fetchController.abort()
      fetchController = null
    }
    activeRequests = 0
    mjpegStreamUrl.value = ''
  }

  return {
    latestScreenshot,
    isLandscape,
    fps,
    isStreaming,
    clickEffects,
    useMjpegStream,
    mjpegStreamUrl,
    useVideoStream,
    videoStreamUrl,
    videoElement,
    startStreamLoop,
    stopStreamLoop,
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

