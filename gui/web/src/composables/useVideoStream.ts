import { ref, type Ref } from 'vue'

/**
 * Composable for H.264 video streaming using MSE (MediaSource Extensions) API.
 * Provides real-time video streaming from scrcpy for better performance.
 */
export function useVideoStream(
  apiBaseUrl: string,
  activeDeviceId: Ref<string>
) {
  const videoElement = ref<HTMLVideoElement | null>(null)
  const isStreaming = ref(false)
  const error = ref<string | null>(null)
  
  let mediaSource: MediaSource | null = null
  let sourceBuffer: SourceBuffer | null = null
  let streamReader: ReadableStreamDefaultReader<Uint8Array> | null = null
  let abortController: AbortController | null = null

  /**
   * Initialize MediaSource and start streaming H.264 video.
   */
  const startVideoStream = async (videoEl: HTMLVideoElement) => {
    if (!activeDeviceId.value) {
      error.value = 'No device selected'
      return
    }

    try {
      videoElement.value = videoEl
      
      // Check if MediaSource is supported
      if (!('MediaSource' in window)) {
        error.value = 'MediaSource API not supported in this browser'
        return
      }

      // Create MediaSource
      mediaSource = new MediaSource()
      const url = URL.createObjectURL(mediaSource)
      videoEl.src = url

      // Wait for MediaSource to be ready
      await new Promise<void>((resolve, reject) => {
        mediaSource!.addEventListener('sourceopen', () => {
          try {
            // Add MP4 source buffer for fragmented MP4
            // Try common H.264 codec strings
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
                sourceBuffer = mediaSource!.addSourceBuffer(mimeType)
                supported = true
                break
              }
            }
            
            if (!supported) {
              reject(new Error('MP4/H.264 codec not supported in this browser'))
              return
            }

            sourceBuffer!.mode = 'sequence' // Use sequence mode for better compatibility
            resolve()
          } catch (e) {
            reject(e)
          }
        }, { once: true })

        mediaSource!.addEventListener('error', (e) => {
          reject(new Error('MediaSource error'))
        }, { once: true })
      })

      // Start fetching H.264 stream
      await fetchVideoStream()
      
      isStreaming.value = true
      error.value = null
    } catch (e: any) {
      error.value = e.message || 'Failed to start video stream'
      console.error('[useVideoStream] Error:', e)
      stopVideoStream()
    }
  }

  /**
   * Fetch H.264 video stream and append to source buffer.
   */
  const fetchVideoStream = async () => {
    if (!sourceBuffer || !activeDeviceId.value) {
      return
    }

    abortController = new AbortController()
    const streamUrl = `${apiBaseUrl}/control/stream/video`

    try {
      const response = await fetch(streamUrl, {
        signal: abortController.signal,
        headers: {
          'Accept': 'video/mp4'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      streamReader = response.body.getReader()
      const decoder = new TextDecoder()

      // Process stream chunks
      while (true) {
        const { done, value } = await streamReader.read()
        
        if (done) {
          break
        }

        // Wait for source buffer to be ready
        if (sourceBuffer.updating) {
          await new Promise(resolve => {
            sourceBuffer!.addEventListener('updateend', resolve, { once: true })
          })
        }

        // Append MP4 fragment data to source buffer
        try {
          if (!sourceBuffer.updating) {
            sourceBuffer.appendBuffer(value)
          } else {
            // Wait for current update to finish
            await new Promise(resolve => {
              sourceBuffer!.addEventListener('updateend', resolve, { once: true })
            })
            sourceBuffer.appendBuffer(value)
          }
        } catch (e: any) {
          // Handle append errors (e.g., buffer full)
          if (e.name === 'QuotaExceededError') {
            // Buffer is full, remove old data and try again
            if (sourceBuffer.buffered.length > 0) {
              try {
                sourceBuffer.remove(0, sourceBuffer.buffered.start(1) || sourceBuffer.buffered.end(0))
              } catch {
                // Ignore remove errors
              }
            }
            await new Promise(resolve => setTimeout(resolve, 100))
            continue
          }
          throw e
        }
      }

      // End of stream
      if (mediaSource && mediaSource.readyState === 'open') {
        await new Promise<void>((resolve) => {
          if (sourceBuffer && !sourceBuffer.updating) {
            mediaSource!.endOfStream()
            resolve()
          } else {
            sourceBuffer?.addEventListener('updateend', () => {
              if (mediaSource) {
                mediaSource.endOfStream()
              }
              resolve()
            }, { once: true })
          }
        })
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // Stream was aborted, this is normal
        return
      }
      throw e
    }
  }

  /**
   * Stop video streaming and cleanup resources.
   */
  const stopVideoStream = () => {
    isStreaming.value = false

    // Abort fetch if in progress
    if (abortController) {
      abortController.abort()
      abortController = null
    }

    // Close stream reader
    if (streamReader) {
      streamReader.cancel().catch(() => {})
      streamReader = null
    }

    // Clean up source buffer
    if (sourceBuffer) {
      try {
        if (sourceBuffer.updating) {
          sourceBuffer.abort()
        }
      } catch (e) {
        // Ignore errors during cleanup
      }
      sourceBuffer = null
    }

    // Clean up MediaSource
    if (mediaSource) {
      try {
        if (mediaSource.readyState === 'open') {
          mediaSource.endOfStream()
        }
      } catch (e) {
        // Ignore errors during cleanup
      }
      
      if (videoElement.value && videoElement.value.src) {
        URL.revokeObjectURL(videoElement.value.src)
        videoElement.value.src = ''
      }
      
      mediaSource = null
    }

    videoElement.value = null
  }

  return {
    videoElement,
    isStreaming,
    error,
    startVideoStream,
    stopVideoStream
  }
}

