import threading
import time
import asyncio
import traceback
from typing import Optional, Tuple, List, Callable
from .device_manager import device_manager
from .stream_manager import stream_manager
from phone_agent.device_factory import get_device_factory

class ScreenStreamer:
    _instance = None
    
    def __init__(self):
        self.is_streaming = False
        self.stream_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.fps = 30.0 # Increased for smoother mirror (User requested at least 30)
        # Default settings for smooth streaming
        self.quality = 50
        self.max_width = 540
        
        self.latest_frame: Optional[bytes] = None
        self.latest_frame_ts: float = 0.0
        
        # Screen change listeners for background tasks
        self.screen_change_listeners: List[Callable[[], None]] = []
        self._listeners_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def capture_frame(self) -> Tuple[Optional[bytes], str]:
        """
        Asynchronously capture a frame from the device using a thread executor.
        Returns: (frame_bytes, status)
        status: 'new', 'unchanged', 'locked', 'error'
        """
        try:
            device_id = device_manager.active_device_id
            if not device_id:
                return None, 'error'
                
            factory = get_device_factory()
            
            # Check lock status first (fast)
            # Run in thread as it calls ADB
            is_on = await asyncio.to_thread(factory.is_screen_on, device_id)
            if not is_on:
                return None, 'locked'

            # Run blocking ADB call in a separate thread
            screenshot = await asyncio.to_thread(
                factory.get_screenshot,
                device_id, 
                quality=self.quality, 
                max_width=self.max_width,
                timeout=5
            )
            
            if screenshot and screenshot.jpeg_data:
                # Compare with latest frame to detect changes
                if self.latest_frame and screenshot.jpeg_data == self.latest_frame:
                    return self.latest_frame, 'unchanged'

                # Frame changed - notify listeners
                self.latest_frame = screenshot.jpeg_data
                self.latest_frame_ts = time.time()
                
                # Notify all screen change listeners (for background tasks)
                self._notify_screen_change()
                
                return self.latest_frame, 'new'
                
            return None, 'error'
        except Exception as e:
            # print(f"Capture error: {e}")
            return None, 'error'

    def update_settings(self, quality: int = None, max_width: int = None, fps: int = None):
        if quality:
            self.quality = quality
        if max_width:
            self.max_width = max_width
        if fps:
            self.fps = fps
    
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
