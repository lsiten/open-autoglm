import threading
import time
import asyncio
import traceback
from typing import Optional, Tuple
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

                self.latest_frame = screenshot.jpeg_data
                self.latest_frame_ts = time.time()
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

screen_streamer = ScreenStreamer.get_instance()
