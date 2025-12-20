"""Screenshot utilities for capturing Android device screen."""

import base64
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple
import time
import zlib

from PIL import Image


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False
    jpeg_data: bytes | None = None


def get_screenshot(device_id: str | None = None, timeout: int = 10, quality: int = 75, max_width: int = 720) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.
        quality: JPEG quality (1-100).
        max_width: Maximum width to resize to (maintains aspect ratio).

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
    """
    start_time = time.time()
    adb_prefix = _get_adb_prefix(device_id)

    try:
        # 1. Try Gzip Capture (Best for USB 2.0 / WiFi bandwidth)
        # NOTE: If device returns black screen on gzip, it might be due to secure screen or weird framebuffer.
        # Fallback if result is suspicious? For now, trust it.
        t0 = time.time()
        res = _get_screenshot_gzip(device_id, timeout, quality, max_width)
        duration = time.time() - t0
        # Check if result is valid black (sensitive) or just error?
        # Gzip function raises exception on error.
        return res
    except Exception as e:
        # print(f"[Perf] Gzip failed: {e}")
        pass

    try:
        # 2. Try Raw Capture (Fastest on USB 3.0)
        t0 = time.time()
        res = _get_screenshot_raw(device_id, timeout, quality, max_width)
        duration = time.time() - t0
        if duration > 0.1:
            print(f"[Perf] Raw Capture took: {duration:.3f}s")
        return res
    except Exception as e:
        # print(f"[Perf] Raw failed: {e}")
        pass

    try:
        # 3. Fallback to exec-out screencap -p
        t0 = time.time()
        result = subprocess.run(
            adb_prefix + ["exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=timeout,
        )

        if result.returncode != 0:
             print(f"Screenshot failed: {result.stderr}")
             return _create_fallback_screenshot(is_sensitive=False)
             
        image_data = result.stdout
        
        if not image_data:
             return _create_fallback_screenshot(is_sensitive=False)
        
        try:
            # Check for header
            if len(image_data) < 4:
                 print("Screenshot data too short")
                 return _create_fallback_screenshot(is_sensitive=False)
                 
            # Detect PNG header
            if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                img = Image.open(BytesIO(image_data))
            else:
                # Try raw RGB if not PNG (some older Androids or specific ROMs)
                # But exec-out screencap -p implies PNG.
                # If we are here, it might be raw data if -p was ignored?
                # Let's try to open it anyway, PIL is robust
                img = Image.open(BytesIO(image_data))
                
        except Exception as e:
             print(f"Screenshot exec-out parse failed: {e}")
             # Fallback to legacy only if truly broken
             return _get_screenshot_legacy(device_id, timeout, quality, max_width)

        width, height = img.size
        return _process_image(img, width, height, quality, max_width)

    except Exception as e:
        print(f"Screenshot error: {e}")
        return _create_fallback_screenshot(is_sensitive=False)


def _get_screenshot_gzip(device_id: str | None, timeout: int, quality: int, max_width: int) -> Screenshot:
    adb_prefix = _get_adb_prefix(device_id)
    # Use shell for pipe
    cmd = adb_prefix + ["shell", "screencap | gzip -1"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
    )
    
    if result.returncode != 0 or not result.stdout:
        raise Exception("Gzip capture failed")
        
    # Decompress
    try:
        # 16 + MAX_WBITS handles gzip header
        data = zlib.decompress(result.stdout, 16 + zlib.MAX_WBITS)
    except Exception:
        # Fallback to standard zlib if no gzip header
        data = zlib.decompress(result.stdout)
        
    if len(data) < 12:
        raise Exception("Invalid header")
        
    w = int.from_bytes(data[0:4], byteorder='little')
    h = int.from_bytes(data[4:8], byteorder='little')
    fmt = int.from_bytes(data[8:12], byteorder='little')
    
    if fmt != 1: 
        raise Exception(f"Unsupported format: {fmt}")
        
    pixels = data[12:]
    # Sanity check length
    if len(pixels) != w * h * 4:
         raise Exception("Incomplete data")

    img = Image.frombuffer("RGBA", (w, h), pixels, "raw", "RGBA", 0, 1)
    return _process_image(img, w, h, quality, max_width)


def _get_screenshot_raw(device_id: str | None, timeout: int, quality: int, max_width: int) -> Screenshot:
    adb_prefix = _get_adb_prefix(device_id)
    result = subprocess.run(
        adb_prefix + ["exec-out", "screencap"],
        capture_output=True,
        timeout=timeout,
    )
    
    if result.returncode != 0 or not result.stdout:
        raise Exception("Raw capture failed")
        
    data = result.stdout
    if len(data) < 12:
        raise Exception("Invalid header")
        
    w = int.from_bytes(data[0:4], byteorder='little')
    h = int.from_bytes(data[4:8], byteorder='little')
    fmt = int.from_bytes(data[8:12], byteorder='little')
    
    # Format 1 is RGBA_8888. 
    # If not 1, might need adjustment, but for now fallback.
    if fmt != 1: 
        raise Exception(f"Unsupported format: {fmt}")
        
    pixels = data[12:]
    expected_len = w * h * 4
    if len(pixels) != expected_len:
        raise Exception(f"Incomplete data: got {len(pixels)}, expected {expected_len}")
        
    img = Image.frombuffer("RGBA", (w, h), pixels, "raw", "RGBA", 0, 1)
    return _process_image(img, w, h, quality, max_width)


def _process_image(img: Image.Image, width: int, height: int, quality: int, max_width: int) -> Screenshot:
    # Optimize: Resize if too large to speed up transfer/processing for local model
    if width > max_width: # Aggressive resize for mirror
        scale = max_width / width # Target max_width
        new_width = max_width
        new_height = int(height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
    
    buffered = BytesIO()
    # Use JPEG for significantly faster encoding and smaller transfer size
    # Quality 75 is a good balance for OCR and visual clarity
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buffered, format="JPEG", quality=quality)
    
    jpeg_bytes = buffered.getvalue()
    base64_data = base64.b64encode(jpeg_bytes).decode("utf-8")

    return Screenshot(
        base64_data=base64_data, 
        width=width, 
        height=height, 
        is_sensitive=False,
        jpeg_data=jpeg_bytes
    )


def _get_screenshot_legacy(device_id: str | None = None, timeout: int = 10, quality: int = 75, max_width: int = 720) -> Screenshot:
    """Legacy method using file pull."""
    temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{uuid.uuid4()}.png")
    adb_prefix = _get_adb_prefix(device_id)
    
    try:
        subprocess.run(
            adb_prefix + ["shell", "screencap", "-p", "/sdcard/tmp.png"],
            capture_output=True,
            timeout=timeout,
        )
        
        subprocess.run(
            adb_prefix + ["pull", "/sdcard/tmp.png", temp_path],
            capture_output=True,
            timeout=5,
        )
        
        if not os.path.exists(temp_path):
             return _create_fallback_screenshot(is_sensitive=False)
             
        img = Image.open(temp_path)
        width, height = img.size
        
        # Process before removing file (though image is loaded in memory)
        res = _process_image(img, width, height, quality, max_width)
        img.close()
        os.remove(temp_path)
        
        return res
    except Exception:
        return _create_fallback_screenshot(is_sensitive=False)


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="JPEG", quality=50)
    jpeg_bytes = buffered.getvalue()
    base64_data = base64.b64encode(jpeg_bytes).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
        jpeg_data=jpeg_bytes
    )
