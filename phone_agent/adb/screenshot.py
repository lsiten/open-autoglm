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
    width: int  # Actual image width (may be resized)
    height: int  # Actual image height (may be resized)
    is_sensitive: bool = False
    jpeg_data: bytes | None = None
    original_width: int | None = None  # Original screen width before resize
    original_height: int | None = None  # Original screen height before resize


def get_screenshot(device_id: str | None = None, timeout: int = 10, quality: int = 75, max_width: int = 720, preferred_method: str | None = None) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.
        quality: JPEG quality (1-100).
        max_width: Maximum width to resize to (maintains aspect ratio).
        preferred_method: Optional preferred method ('scrcpy', 'raw', 'gzip', 'png'). If specified and fails, will try other methods.

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
        
        Methods are tried in order:
        1. scrcpy (if available, fastest method using H.264 stream)
        2. raw (fastest ADB method)
        3. gzip (good for USB 2.0/WiFi)
        4. png (fallback, most compatible)
    """
    start_time = time.time()
    adb_prefix = _get_adb_prefix(device_id)
    
    # Temporarily disable scrcpy due to issues with --record=- outputting logs instead of video data
    # This causes black screens and delays. Will re-enable when scrcpy issue is fixed.
    # Always try scrcpy first if available (highest performance, regardless of preferred_method)
    # This ensures we use the fastest method whenever possible
    scrcpy_tried = False
    scrcpy_error = None
    scrcpy_enabled = True  # Re-enabled with named pipe (FIFO) implementation
    
    if scrcpy_enabled:
        try:
            from .scrcpy_capture import get_screenshot_scrcpy, _check_scrcpy_available
            # Check if scrcpy is available before trying
            if _check_scrcpy_available():
                scrcpy_tried = True
                res = get_screenshot_scrcpy(device_id, timeout, quality, max_width)
                if res:
                    return res
                else:
                    scrcpy_error = "scrcpy returned None (no frame available or connection failed)"
            else:
                scrcpy_error = "scrcpy not available (not in PATH or version check failed)"
        except ImportError:
            # scrcpy module not available, continue to other methods
            scrcpy_error = "scrcpy module import failed"
            pass
        except Exception as e:
            # scrcpy failed, continue to other methods
            scrcpy_error = f"scrcpy exception: {type(e).__name__}: {e}"
            pass
        
        # Log scrcpy failure if we tried it
        if scrcpy_tried and scrcpy_error:
            print(f"[Screenshot] scrcpy failed: {scrcpy_error}, falling back to ADB methods", flush=True)

    # If preferred method is specified, try it first
    if preferred_method == 'raw':
        try:
            t0 = time.time()
            res = _get_screenshot_raw(device_id, timeout, quality, max_width)
            duration = time.time() - t0
            if duration > 0.15:
                print(f"[Perf] Raw Capture took: {duration:.3f}s")
            # Check if result is black screen, if so try other methods
            if res and res.jpeg_data:
                try:
                    check_img = Image.open(BytesIO(res.jpeg_data))
                    if _is_black_screen(check_img):
                        print("[Screenshot] Raw method returned black screen, trying other methods")
                        raise Exception("Black screen detected")
                except Exception:
                    # If check fails or black screen detected, continue to try other methods
                    pass
            return res
        except Exception as e:
            # Preferred method failed, continue to try other methods
            pass
    elif preferred_method == 'gzip':
        try:
            t0 = time.time()
            res = _get_screenshot_gzip(device_id, timeout, quality, max_width)
            duration = time.time() - t0
            if duration > 0.15:
                print(f"[Perf] Gzip Capture took: {duration:.3f}s")
            # Check if result is black screen, if so try other methods
            if res and res.jpeg_data:
                try:
                    check_img = Image.open(BytesIO(res.jpeg_data))
                    if _is_black_screen(check_img):
                        print("[Screenshot] Gzip method returned black screen, trying other methods")
                        raise Exception("Black screen detected")
                except Exception:
                    # If check fails or black screen detected, continue to try other methods
                    pass
            return res
        except Exception as e:
            # Preferred method failed, continue to try other methods
            pass
    elif preferred_method == 'png':
        try:
            t0 = time.time()
            result = subprocess.run(
                adb_prefix + ["exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                 print(f"Screenshot failed: {result.stderr}")
                 raise Exception("PNG capture failed")
                 
            image_data = result.stdout
            
            if not image_data:
                 raise Exception("No image data")
            
            try:
                if len(image_data) < 4:
                     raise Exception("Screenshot data too short")
                     
                if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                    img = Image.open(BytesIO(image_data))
                else:
                    img = Image.open(BytesIO(image_data))
                    
            except Exception as e:
                 raise Exception(f"Screenshot exec-out parse failed: {e}")

            width, height = img.size
            return _process_image(img, width, height, quality, max_width)
        except Exception as e:
            # Preferred method failed, continue to try other methods
            pass

    # Try methods in order of speed (if preferred_method not specified or failed)
    # If preferred_method was 'scrcpy' but scrcpy failed, we'll try other methods here
    # Prioritize fastest method first for mirroring
    # Raw capture is typically fastest on USB 3.0 and modern devices
    methods_tried = []
    last_exception = None
    
    try:
        # 1. Try Raw Capture first (Fastest on USB 3.0 and modern devices)
        t0 = time.time()
        res = _get_screenshot_raw(device_id, timeout, quality, max_width)
        duration = time.time() - t0
        if duration > 0.15:
            print(f"[Perf] Raw Capture took: {duration:.3f}s")
        
        # Temporarily disable black screen check to avoid false positives
        # The device might have a dark theme or the threshold might be too strict
        # Check if result is black screen
        # if res and res.jpeg_data:
        #     try:
        #         check_img = Image.open(BytesIO(res.jpeg_data))
        #         if _is_black_screen(check_img):
        #             print("[Screenshot] Raw method returned black screen, trying other methods")
        #             methods_tried.append("raw (black screen)")
        #             raise Exception("Black screen detected")
        #     except Exception as e:
        #         if "Black screen" in str(e):
        #             raise
        #         # Other errors in check, allow through
        
        methods_tried.append("raw")
        return res
    except Exception as e:
        methods_tried.append("raw (failed)")
        last_exception = e
        # print(f"[Perf] Raw failed: {e}")

    try:
        # 2. Try Gzip Capture (Good for USB 2.0 / WiFi bandwidth)
        # NOTE: If device returns black screen on gzip, it might be due to secure screen or weird framebuffer.
        t0 = time.time()
        res = _get_screenshot_gzip(device_id, timeout, quality, max_width)
        duration = time.time() - t0
        if duration > 0.15:
            print(f"[Perf] Gzip Capture took: {duration:.3f}s")
        
        # Temporarily disable black screen check to avoid false positives
        # The device might have a dark theme or the threshold might be too strict
        # Check if result is black screen
        # if res and res.jpeg_data:
        #     try:
        #         check_img = Image.open(BytesIO(res.jpeg_data))
        #         if _is_black_screen(check_img):
        #             print("[Screenshot] Gzip method returned black screen, trying other methods")
        #             methods_tried.append("gzip (black screen)")
        #             raise Exception("Black screen detected")
        #     except Exception as e:
        #         if "Black screen" in str(e):
        #             raise
        #         # Other errors in check, allow through
        
        methods_tried.append("gzip")
        return res
    except Exception as e:
        methods_tried.append("gzip (failed)")
        last_exception = e
        # print(f"[Perf] Gzip failed: {e}")

    try:
        # 3. Fallback to exec-out screencap -p (slowest but most compatible)
        t0 = time.time()
        result = subprocess.run(
            adb_prefix + ["exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=timeout,  # Use full timeout for fallback method
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
        
        # Check if PNG result is black screen before processing
        # Temporarily disable black screen check to avoid false positives
        # The device might have a dark theme or the threshold might be too strict
        is_black = _is_black_screen(img)
        if is_black:
            print(f"[Screenshot] PNG method detected black screen (size: {width}x{height}), but proceeding anyway to avoid false positives")
            # Don't treat as black screen - proceed with the image
            # This avoids false positives when device has dark theme or is actually showing content
            methods_tried.append("png (detected black but proceeding)")
        else:
            methods_tried.append("png")
        
        methods_tried.append("png")
        return _process_image(img, width, height, quality, max_width)

    except Exception as e:
        print(f"[Screenshot] Error: {e}")
        if methods_tried:
            print(f"[Screenshot] Methods tried: {', '.join(methods_tried)}")
        # Try legacy method as last resort before giving up
        try:
            legacy_res = _get_screenshot_legacy(device_id, timeout, quality, max_width)
            methods_tried.append("legacy")
            return legacy_res
        except Exception as legacy_e:
            if "black screen" in str(legacy_e).lower():
                methods_tried.append("legacy (black screen)")
            else:
                methods_tried.append("legacy (failed)")
        return _create_fallback_screenshot(is_sensitive=False)


def _get_screenshot_gzip(device_id: str | None, timeout: int, quality: int, max_width: int) -> Screenshot:
    adb_prefix = _get_adb_prefix(device_id)
    # Use shell for pipe, use faster compression level (-1 is fastest)
    cmd = adb_prefix + ["shell", "screencap | gzip -1"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,  # Use full timeout - don't cap it too low
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
    
    # Temporarily disable black screen check to avoid false positives
    # The device might have a dark theme or the threshold might be too strict
    # Check if image is black screen before processing
    # if _is_black_screen(img):
    #     raise Exception("Gzip capture returned black screen")
    
    return _process_image(img, w, h, quality, max_width)


def _get_screenshot_raw(device_id: str | None, timeout: int, quality: int, max_width: int) -> Screenshot:
    adb_prefix = _get_adb_prefix(device_id)
    # Use exec-out for direct binary transfer (fastest method)
    result = subprocess.run(
        adb_prefix + ["exec-out", "screencap"],
        capture_output=True,
        timeout=timeout,  # Use full timeout - don't cap it too low
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
    
    # Temporarily disable black screen check to avoid false positives
    # The device might have a dark theme or the threshold might be too strict
    # Check if image is black screen before processing
    # if _is_black_screen(img):
    #     raise Exception("Raw capture returned black screen")
    
    return _process_image(img, w, h, quality, max_width)


def _is_black_screen(img: Image.Image, threshold: float = 0.95) -> bool:
    """
    Check if the image is mostly black (likely a sensitive screen or failed capture).
    
    Args:
        img: PIL Image object
        threshold: Threshold for considering image black (0.0-1.0). 
                   If more than this percentage of pixels are black, consider it black.
    
    Returns:
        True if image is mostly black, False otherwise.
    """
    try:
        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Sample pixels to check (check every 10th pixel for performance)
        width, height = img.size
        total_samples = 0
        black_samples = 0
        
        # Sample pixels across the image
        for y in range(0, height, 10):
            for x in range(0, width, 10):
                pixel = img.getpixel((x, y))
                total_samples += 1
                # Check if pixel is black or very dark (RGB all < 10)
                if pixel[0] < 10 and pixel[1] < 10 and pixel[2] < 10:
                    black_samples += 1
        
        if total_samples == 0:
            return True  # No samples, consider it black
        
        black_ratio = black_samples / total_samples
        return black_ratio >= threshold
    except Exception:
        # On error, don't consider it black (allow it through)
        return False


def _process_image(img: Image.Image, width: int, height: int, quality: int, max_width: int) -> Screenshot:
    # Store original dimensions before any resizing
    original_width = width
    original_height = height
    
    # Optimize: Resize if too large to speed up transfer/processing for local model
    if width > max_width: # Aggressive resize for mirror
        scale = max_width / width # Target max_width
        new_width = max_width
        new_height = int(height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.BILINEAR)
        # Use resized dimensions for the screenshot object
        width = new_width
        height = new_height
    
    buffered = BytesIO()
    # Use JPEG for significantly faster encoding and smaller transfer size
    # Optimize encoding for speed: disable optimize and progressive for faster encoding
    if img.mode != "RGB":
        img = img.convert("RGB")
    # optimize=False and progressive=False for faster encoding (mirroring priority)
    img.save(buffered, format="JPEG", quality=quality, optimize=False, progressive=False)
    
    jpeg_bytes = buffered.getvalue()
    base64_data = base64.b64encode(jpeg_bytes).decode("utf-8")

    return Screenshot(
        base64_data=base64_data, 
        width=width,  # Actual image width (may be resized)
        height=height,  # Actual image height (may be resized)
        is_sensitive=False,
        jpeg_data=jpeg_bytes,
        original_width=original_width if width != original_width else None,  # Only store if resized
        original_height=original_height if height != original_height else None  # Only store if resized
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
        
        # Check if image is black screen before processing
        if _is_black_screen(img):
            img.close()
            os.remove(temp_path)
            raise Exception("Legacy method returned black screen")
        
        # Process before removing file (though image is loaded in memory)
        res = _process_image(img, width, height, quality, max_width)
        img.close()
        os.remove(temp_path)
        
        return res
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        if "black screen" in str(e).lower():
            raise
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
