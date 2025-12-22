import threading
import time
import asyncio
import traceback
import hashlib
from typing import Optional, Tuple, List, Callable
from .device_manager import device_manager
from .stream_manager import stream_manager
import asyncio
from phone_agent.device_factory import get_device_factory

class ScreenStreamer:
    _instance = None
    
    def __init__(self):
        self.is_streaming = False
        self.stream_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.fps = 60.0 # Increased to 60fps for smoother animations
        # Default settings for smooth streaming
        self.quality = 50
        self.max_width = 540
        
        # Screenshot method cache (remember fastest method)
        self._fastest_method = None  # 'scrcpy', 'raw', 'gzip', 'png', or None (auto-detect)
        self._method_performance = {}  # Track method performance: {'raw': [durations...], 'gzip': [durations...], 'png': [durations...]}
        self._method_performance_samples = 5  # Number of samples to keep per method
        self._method_evaluation_interval = 30  # Re-evaluate method every 30 seconds
        self._last_method_evaluation = 0.0
        
        self.latest_frame: Optional[bytes] = None
        self.latest_frame_ts: float = 0.0
        self.latest_frame_hash: Optional[str] = None  # MD5 hash for fast comparison
        
        # Screen state cache (to reduce ADB calls)
        self._screen_on_cache: Optional[bool] = None
        self._screen_check_ts: float = 0.0
        self._screen_cache_ttl: float = 5.0  # Cache for 5 seconds (increased for better performance)
        self._screen_cache_lock = threading.Lock()  # Lock for screen cache
        self._frame_lock = threading.Lock()  # Lock for frame updates
        
        # Screen change listeners for background tasks
        self.screen_change_listeners: List[Callable[[], None]] = []
        self._listeners_lock = threading.Lock()
        
        # Performance monitoring
        self._capture_times: List[float] = []  # Recent capture durations
        self._max_capture_history = 30  # Keep last 30 captures
        self._last_perf_log = 0.0
        self._perf_log_interval = 10.0  # Log performance every 10 seconds

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def capture_frame(self) -> Tuple[Optional[bytes], str]:
        """
        Asynchronously capture a frame from the device.
        If background streaming is active, returns cached frame immediately.
        Otherwise, captures on-demand.
        Returns: (frame_bytes, status)
        status: 'new', 'unchanged', 'locked', 'error'
        """
        # If background streaming is active, return cached frame immediately
        if self.is_streaming:
            with self._frame_lock:
                if self.latest_frame and self.latest_frame_ts > 0:
                    # Check if frame is too old (older than 5 seconds)
                    frame_age = time.time() - self.latest_frame_ts
                    if frame_age < 5.0:
                        # Always return 'new' when streaming to ensure frontend gets continuous updates
                        # This prevents frontend from retrying too frequently
                        return self.latest_frame, 'new'
                    else:
                        # Frame is too old, fallback to on-demand capture
                        pass  # Fall through to on-demand capture
                else:
                    # No frame cached yet, but streaming is active
                    # Wait a bit for background thread to capture first frame (max 500ms)
                    # This avoids unnecessary on-demand capture when streaming just started
                    for _ in range(5):
                        await asyncio.sleep(0.1)
                        with self._frame_lock:
                            if self.latest_frame and self.latest_frame_ts > 0:
                                frame_age = time.time() - self.latest_frame_ts
                                if frame_age < 5.0:
                                    return self.latest_frame, 'new'
                    # Still no frame after waiting, fallback to on-demand capture
                    pass  # Fall through to on-demand capture
        
        # On-demand capture (fallback when streaming is not active or no cached frame)
        try:
            device_id = device_manager.active_device_id
            if not device_id:
                return None, 'error'
                
            frame, status = await asyncio.to_thread(self._capture_frame_sync, device_id)
            return frame, status
        except Exception as e:
            # print(f"Capture error: {e}")
            return None, 'error'
    
    def _capture_frame_sync(self, device_id: str) -> Tuple[Optional[bytes], str]:
        """
        Synchronous frame capture (runs in thread).
        Uses cached screen state to reduce ADB calls.
        Returns capture duration for performance monitoring.
        """
        capture_start = time.time()
        try:
            factory = get_device_factory()
            
            # Check screen state with cache (reduces ADB calls)
            is_on = self._get_screen_state_cached(device_id, factory)
            if not is_on:
                return None, 'locked'

            # Run blocking ADB call with reasonable timeout
            # Use 5 seconds timeout - balance between speed and reliability
            # Too short timeout causes frequent failures and black screens
            # Use preferred method if available for better performance
            preferred_method = self._get_preferred_method()
            if not hasattr(self, '_first_capture_logged'):
                print(f"[ScreenStreamer] Starting capture with preferred_method={preferred_method}", flush=True)
                self._first_capture_logged = True
            method_start = time.time()
            screenshot = factory.get_screenshot(
                device_id, 
                quality=self.quality, 
                max_width=self.max_width,
                timeout=5,  # 5 seconds - enough for slow devices but not too long
                preferred_method=preferred_method
            )
            method_duration = time.time() - method_start
            if not hasattr(self, '_first_screenshot_logged'):
                if screenshot and screenshot.jpeg_data:
                    print(f"[ScreenStreamer] First screenshot captured successfully: {len(screenshot.jpeg_data)} bytes, method={preferred_method}, duration={method_duration:.3f}s", flush=True)
                else:
                    print(f"[ScreenStreamer] First screenshot failed: screenshot={screenshot}, method={preferred_method}, duration={method_duration:.3f}s", flush=True)
                self._first_screenshot_logged = True
            
            # Record method performance (only if we successfully got screenshot)
            if screenshot and screenshot.jpeg_data:
                # Determine which method was actually used
                # Since we can't know for sure, we'll infer from preferred_method or track all attempts
                # For now, we'll track based on preferred_method if it was used
                if preferred_method:
                    self._record_method_performance(preferred_method, method_duration)
                # Re-evaluate fastest method periodically
                self._evaluate_fastest_method()
            
            if screenshot and screenshot.jpeg_data:
                # Use hash comparison for faster detection
                frame_hash = hashlib.md5(screenshot.jpeg_data).hexdigest()
                
                # Check if frame changed before acquiring lock
                frame_changed = False
                with self._frame_lock:
                    # Compare hash instead of full data
                    if self.latest_frame_hash == frame_hash:
                        # Frame content unchanged, but still update timestamp to ensure real-time updates
                        # This ensures every captured frame is available, even if content is the same
                        self.latest_frame_ts = time.time()
                        capture_duration = time.time() - capture_start
                        self._record_capture_time(capture_duration)
                        # Return 'new' instead of 'unchanged' to ensure frame is pushed
                        # This maintains real-time frame delivery even when content doesn't change
                        return self.latest_frame, 'new'

                    # Frame changed - update cache
                    self.latest_frame = screenshot.jpeg_data
                    self.latest_frame_hash = frame_hash
                    self.latest_frame_ts = time.time()
                    frame_changed = True
                
                # Notify listeners and broadcast via WebSocket outside of lock
                if frame_changed:
                    self._notify_screen_change()
                
                # Always broadcast via WebSocket if there are connections
                # For frame changes, broadcast immediately for smooth animation
                # For unchanged frames, also broadcast to maintain continuous stream
                if stream_manager.frame_connections and self.latest_frame:
                    try:
                        # Use asyncio.run_coroutine_threadsafe to call async function from sync thread
                        loop = stream_manager.main_loop
                        if loop and loop.is_running():
                            # Schedule the coroutine to run in the event loop immediately
                            # This ensures frames are pushed as soon as they're captured
                            asyncio.run_coroutine_threadsafe(
                                stream_manager.broadcast_frame(
                                    self.latest_frame, 
                                    self.latest_frame_ts
                                ),
                                loop
                            )
                            # Don't wait for result to avoid blocking frame capture
                            # Errors will be handled in broadcast_frame
                    except Exception as e:
                        # Don't let WebSocket errors break frame capture
                        pass
                
                capture_duration = time.time() - capture_start
                self._record_capture_time(capture_duration)
                return self.latest_frame, 'new'
                
            return None, 'error'
        except Exception as e:
            # print(f"Capture error: {e}")
            return None, 'error'
    
    def _record_capture_time(self, duration: float):
        """Record capture duration for performance monitoring."""
        self._capture_times.append(duration)
        if len(self._capture_times) > self._max_capture_history:
            self._capture_times.pop(0)
    
    def _record_method_performance(self, method: str, duration: float):
        """Record performance of a screenshot method."""
        if method not in self._method_performance:
            self._method_performance[method] = []
        self._method_performance[method].append(duration)
        # Keep only recent samples
        if len(self._method_performance[method]) > self._method_performance_samples:
            self._method_performance[method].pop(0)
    
    def _evaluate_fastest_method(self):
        """Evaluate and update the fastest screenshot method based on recent performance."""
        now = time.time()
        # Only re-evaluate periodically to avoid overhead
        if now - self._last_method_evaluation < self._method_evaluation_interval:
            return
        
        self._last_method_evaluation = now
        
        # Calculate average duration for each method
        method_avg_times = {}
        for method, durations in self._method_performance.items():
            if durations:
                method_avg_times[method] = sum(durations) / len(durations)
        
        # Find fastest method
        if method_avg_times:
            fastest_method = min(method_avg_times.items(), key=lambda x: x[1])[0]
            if fastest_method != self._fastest_method:
                self._fastest_method = fastest_method
                # Optional: log method change for debugging
                # print(f"[ScreenStreamer] Fastest method changed to: {fastest_method} (avg: {method_avg_times[fastest_method]:.3f}s)", flush=True)
    
    def _get_preferred_method(self) -> Optional[str]:
        """Get the preferred screenshot method based on performance history.
        scrcpy re-enabled with fixed parameters for scrcpy 3.3.4+.
        """
        # scrcpy re-enabled with named pipe (FIFO) implementation
        scrcpy_enabled = True
        
        if scrcpy_enabled:
            # First, check if scrcpy is available (highest priority)
            try:
                from phone_agent.adb.scrcpy_capture import _check_scrcpy_available
                if _check_scrcpy_available():
                    return 'scrcpy'
            except (ImportError, Exception):
                # scrcpy not available or check failed, continue to other methods
                pass
        
        # If scrcpy is not available or disabled, use the fastest method from history
        return self._fastest_method
    
    def _get_actual_fps(self) -> float:
        """Calculate actual FPS based on recent capture times."""
        if not self._capture_times:
            return 0.0
        avg_duration = sum(self._capture_times) / len(self._capture_times)
        if avg_duration <= 0:
            return 0.0
        return 1.0 / avg_duration
    
    def _log_performance(self):
        """Log performance metrics periodically."""
        # Performance logging disabled to reduce noise
        # Uncomment below if debugging is needed
        # now = time.time()
        # if now - self._last_perf_log < self._perf_log_interval:
        #     return
        # 
        # if self._capture_times:
        #     avg_duration = sum(self._capture_times) / len(self._capture_times)
        #     max_duration = max(self._capture_times)
        #     min_duration = min(self._capture_times)
        #     actual_fps = self._get_actual_fps()
        #     
        #     # Calculate frame age (how old is the latest frame)
        #     frame_age = now - self.latest_frame_ts if self.latest_frame_ts > 0 else 0
        #     
        #     print(f"[ScreenStreamer] Performance - Target FPS: {self.fps:.1f}, "
        #           f"Actual FPS: {actual_fps:.1f}, "
        #           f"Avg Capture: {avg_duration*1000:.1f}ms, "
        #           f"Min: {min_duration*1000:.1f}ms, Max: {max_duration*1000:.1f}ms, "
        #           f"Frame Age: {frame_age*1000:.1f}ms, "
        #           f"Streaming: {self.is_streaming}", flush=True)
        # 
        # self._last_perf_log = now
        pass
    
    def _get_screen_state_cached(self, device_id: str, factory) -> bool:
        """
        Get screen state with caching to reduce ADB calls.
        Cache expires after _screen_cache_ttl seconds.
        """
        now = time.time()
        
        with self._screen_cache_lock:
            # Check if cache is valid
            if (self._screen_on_cache is not None and 
                now - self._screen_check_ts < self._screen_cache_ttl):
                return self._screen_on_cache
            
            # Cache expired or not set, check screen state
            try:
                self._screen_on_cache = factory.is_screen_on(device_id)
                self._screen_check_ts = now
                return self._screen_on_cache
            except Exception:
                # On error, assume screen is on (allow retries)
                self._screen_on_cache = True
                self._screen_check_ts = now
                return True
    
    def _background_capture_loop(self):
        """
        Background thread loop that continuously captures frames at configured FPS.
        Uses dynamic frame interval based on actual capture time to maintain target FPS.
        """
        target_frame_interval = 1.0 / self.fps if self.fps > 0 else 0.0167  # Default to ~60fps
        consecutive_errors = 0
        max_consecutive_errors = 20  # Increased to avoid stopping stream too easily
        
        while not self.stop_event.is_set():
            loop_start = time.time()
            try:
                device_id = device_manager.active_device_id
                if not device_id:
                    # No device, wait and retry
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        print("[ScreenStreamer] No device for too long, stopping stream", flush=True)
                        self.stop_streaming()
                        break
                    time.sleep(0.5)
                    continue
                
                # Reset error counter on success
                consecutive_errors = 0
                
                # Capture frame synchronously
                frame, status = self._capture_frame_sync(device_id)
                
                # Log first few captures for debugging
                if not hasattr(self, '_capture_count'):
                    self._capture_count = 0
                self._capture_count += 1
                if self._capture_count <= 3:
                    print(f"[ScreenStreamer] Capture #{self._capture_count}: status={status}, frame={'present' if frame else 'none'}", flush=True)
                
                # Log performance periodically
                self._log_performance()
                
                # Calculate actual capture time
                capture_duration = time.time() - loop_start
                
                # If capture failed, use exponential backoff
                if status == 'error' or status == 'locked':
                    # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, max 1s
                    backoff = min(0.1 * (2 ** min(consecutive_errors, 3)), 1.0)
                    consecutive_errors += 1
                    # Don't wait too long on error - keep trying
                    time.sleep(backoff)
                elif status == 'unchanged':
                    # Frame unchanged is normal, not an error
                    # But we should still update timestamp to ensure real-time frame delivery
                    # This ensures every captured frame is available, even if content is the same
                    consecutive_errors = 0
                    # Update timestamp even for unchanged frames to maintain real-time updates
                    with self._frame_lock:
                        if self.latest_frame:
                            self.latest_frame_ts = time.time()
                    # Still broadcast cached frame via WebSocket to maintain continuous stream
                    # This matches HTTP polling behavior where we always get the latest frame
                    if stream_manager.frame_connections and self.latest_frame:
                        try:
                            loop = stream_manager.main_loop
                            if loop and loop.is_running():
                                asyncio.run_coroutine_threadsafe(
                                    stream_manager.broadcast_frame(
                                        self.latest_frame, 
                                        self.latest_frame_ts
                                    ),
                                    loop
                                )
                        except Exception:
                            pass
                    # Still wait for target interval to maintain consistent FPS
                    remaining_time = target_frame_interval - capture_duration
                    if remaining_time > 0:
                        # Use precise sleep for smooth frame rate (cap at target interval)
                        time.sleep(min(remaining_time, target_frame_interval))
                    else:
                        time.sleep(0.001)  # Minimal wait if capture took too long
                else:
                    # Dynamic frame interval: adjust based on actual capture time
                    # If capture took longer than target interval, use minimal wait
                    # Otherwise, wait for remaining time to maintain target FPS
                    remaining_time = target_frame_interval - capture_duration
                    if remaining_time > 0:
                        # Use precise sleep for smooth frame rate (cap at target interval)
                        time.sleep(min(remaining_time, target_frame_interval))
                    else:
                        # Capture took too long, minimal wait to avoid CPU spinning
                        # But don't wait too long to maintain responsiveness
                        time.sleep(0.001)
                    
                    consecutive_errors = 0
                    
            except Exception as e:
                consecutive_errors += 1
                print(f"[ScreenStreamer] Background capture error: {e}", flush=True)
                # Exponential backoff on exception
                backoff = min(0.1 * (2 ** min(consecutive_errors, 4)), 2.0)
                time.sleep(backoff)
                
                # Stop streaming after too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    print(f"[ScreenStreamer] Too many consecutive errors ({consecutive_errors}), stopping stream", flush=True)
                    self.stop_streaming()
                    break
    
    def start_streaming(self):
        """
        Start background streaming thread to continuously capture frames.
        """
        if self.is_streaming:
            return  # Already streaming
        
        device_id = device_manager.active_device_id
        if not device_id:
            print("[ScreenStreamer] Cannot start streaming: no device selected", flush=True)
            return  # No device selected
        
        self.is_streaming = True
        self.stop_event.clear()
        
        # Reset performance metrics
        self._capture_times.clear()
        self._last_perf_log = time.time()
        
        # Don't clear old frame immediately - keep it until new frame is captured
        # This prevents black screen during stream restart
        # The frame will be updated naturally as new frames are captured
        
        # Start background thread
        self.stream_thread = threading.Thread(
            target=self._background_capture_loop,
            daemon=True,
            name="screen-streamer"
        )
        self.stream_thread.start()
        print(f"[ScreenStreamer] Started background streaming at {self.fps} FPS for device {device_id}", flush=True)
    
    def stop_streaming(self):
        """
        Stop background streaming thread.
        """
        if not self.is_streaming:
            return  # Not streaming
        
        self.is_streaming = False
        self.stop_event.set()
        
        # Wait for thread to finish (with timeout)
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=1.0)
        
        self.stream_thread = None
        print("[ScreenStreamer] Stopped background streaming", flush=True)

    def update_settings(self, quality: int = None, max_width: int = None, fps: int = None):
        """
        Update streaming settings. If FPS changes and streaming is active,
        the background thread will automatically adjust.
        """
        if quality:
            self.quality = quality
        if max_width:
            self.max_width = max_width
        if fps:
            self.fps = fps
            # Note: Background thread will pick up new FPS on next iteration
    
    def register_screen_change_listener(self, callback: Callable[[], None]):
        """Register a callback to be called when screen changes."""
        with self._listeners_lock:
            if callback not in self.screen_change_listeners:
                self.screen_change_listeners.append(callback)
    
    def unregister_screen_change_listener(self, callback: Callable[[], None]):
        """Unregister a screen change listener."""
        with self._listeners_lock:
            if callback in self.screen_change_listeners:
                self.screen_change_listeners.remove(callback)
    
    def _notify_screen_change(self):
        """Notify all registered listeners about screen change.
        This is called from the async capture_frame context, so we use threading
        to ensure listeners are called in separate threads and don't block capture.
        """
        with self._listeners_lock:
            listeners = list(self.screen_change_listeners)  # Copy to avoid lock contention
        
        # Call listeners in separate threads to avoid blocking screen capture
        for callback in listeners:
            try:
                # Use threading to call callback asynchronously
                threading.Thread(target=callback, daemon=True, name="screen-change-notify").start()
            except Exception as e:
                # Don't let one listener's error break others
                print(f"[ScreenStreamer] Error in screen change listener: {e}", flush=True)

screen_streamer = ScreenStreamer.get_instance()
