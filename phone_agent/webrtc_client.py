from gui.server.services.device_manager import device_manager
from gui.server.services.stream_manager import stream_manager
import asyncio
import json
import time
from typing import Optional

# Mock the Screenshot object to match what PhoneAgent expects
class WebRTCScreenshot:
    def __init__(self, base64_data):
        self.base64_data = base64_data

def get_screenshot(device_id: str | None = None, timeout: int = 10):
    # Get the latest screenshot from DeviceManager or StreamManager?
    # Actually, DeviceManager doesn't store the screenshot. 
    # StreamManager broadcasts it.
    # We need to store the latest screenshot in DeviceManager for this purpose.
    
    # Check if device exists
    device = None
    for d in device_manager.webrtc_devices:
        if d['id'] == device_id:
            device = d
            break
            
    if not device:
        print(f"WebRTC device {device_id} not found")
        return None
        
    # In a real impl, we should cache the latest frame in the device dict
    # For now, let's assume device_manager has it (we need to add it)
    base64_data = device.get('latest_screenshot')
    if base64_data:
        return WebRTCScreenshot(base64_data)
    return None

def tap(x: int, y: int, device_id: str | None = None, delay: float | None = None):
    _send_command(device_id, {"type": "tap", "x": x, "y": y})
    if delay:
        time.sleep(delay)

def type_text(text: str, device_id: str | None = None):
    # WebRTC client might not support typing yet, but we can send it
    _send_command(device_id, {"type": "type", "text": text})

def home(device_id: str | None = None, delay: float | None = None):
    _send_command(device_id, {"type": "home"})

def back(device_id: str | None = None, delay: float | None = None):
    _send_command(device_id, {"type": "back"})

# Stub other methods
def get_current_app(device_id: str | None = None) -> str:
    return "unknown"

def double_tap(x, y, device_id=None, delay=None):
    tap(x, y, device_id, delay)
    time.sleep(0.1)
    tap(x, y, device_id, delay)

def long_press(x, y, duration_ms=1000, device_id=None, delay=None):
    _send_command(device_id, {"type": "long_press", "x": x, "y": y, "duration": duration_ms})

def swipe(sx, sy, ex, ey, duration=None, device_id=None, delay=None):
    _send_command(device_id, {"type": "swipe", "sx": sx, "sy": sy, "ex": ex, "ey": ey})

def launch_app(app_name, device_id=None, delay=None):
    return False

def clear_text(device_id=None):
    pass

def detect_and_set_adb_keyboard(device_id=None):
    return "default"

def restore_keyboard(ime, device_id=None):
    pass

def list_devices():
    return []

def _send_command(device_id, cmd_dict):
    device = None
    for d in device_manager.webrtc_devices:
        if d['id'] == device_id:
            device = d
            break
    
    if device and device.get('socket'):
        asyncio.run(device['socket'].send_text(json.dumps(cmd_dict)))
