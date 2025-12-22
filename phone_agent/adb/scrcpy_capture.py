"""Scrcpy-based screen capture for high-performance screen mirroring.

This module uses scrcpy to capture screen frames via H.264 video stream,
which is much faster than traditional ADB screenshot methods.

Requirements:
- scrcpy must be installed and available in PATH
- ffmpeg must be installed for H.264 decoding (optional, can use OpenCV)
"""

import subprocess
import threading
import time
import queue
import os
from typing import Optional
from dataclasses import dataclass
from io import BytesIO
from PIL import Image

from .screenshot import Screenshot, _process_image


@dataclass
class ScrcpyConnection:
    """Manages scrcpy connection and frame extraction."""
    device_id: str
    process: Optional[subprocess.Popen] = None
    ffmpeg_process: Optional[subprocess.Popen] = None
    frame_queue: queue.Queue = None
    running: bool = False
    thread: Optional[threading.Thread] = None
    max_size: int = 720
    bit_rate: int = 2000000  # 2Mbps
    max_fps: int = 60
    
    def __post_init__(self):
        if self.frame_queue is None:
            self.frame_queue = queue.Queue(maxsize=2)  # Keep only latest 2 frames


_scrcpy_connections: dict[str, ScrcpyConnection] = {}
_connection_lock = threading.Lock()


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _check_scrcpy_available() -> bool:
    """Check if scrcpy is available in PATH."""
    try:
        result = subprocess.run(
            ["scrcpy", "--version"],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _read_png_from_stream(stream) -> Optional[Image.Image]:
    """Read a PNG image from stream."""
    try:
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        signature = b'\x89PNG\r\n\x1a\n'
        
        # Find PNG signature
        buffer = b''
        while len(buffer) < len(signature):
            chunk = stream.read(1)
            if not chunk:
                return None
            buffer += chunk
        
        # Check if we have PNG signature
        if buffer != signature:
            # Try to find signature in buffer
            while True:
                pos = buffer.find(signature)
                if pos >= 0:
                    buffer = buffer[pos:]
                    break
                # Read more data
                chunk = stream.read(1024)
                if not chunk:
                    return None
                buffer += chunk
                if len(buffer) > 65536:  # Max PNG size check
                    return None
        
        # Read PNG data
        # PNG structure: signature + chunks
        # We'll read until IEND chunk
        png_data = buffer
        iend_found = False
        
        while not iend_found:
            # Read chunk header (8 bytes: length + type)
            chunk_header = stream.read(8)
            if len(chunk_header) < 8:
                return None
            
            chunk_length = int.from_bytes(chunk_header[:4], 'big')
            chunk_type = chunk_header[4:8]
            
            # Read chunk data
            chunk_data = stream.read(chunk_length)
            if len(chunk_data) < chunk_length:
                return None
            
            # Read CRC (4 bytes)
            crc = stream.read(4)
            if len(crc) < 4:
                return None
            
            png_data += chunk_header + chunk_data + crc
            
            if chunk_type == b'IEND':
                iend_found = True
        
        # Decode PNG
        img = Image.open(BytesIO(png_data))
        return img
    except Exception as e:
        return None


def _scrcpy_frame_reader(conn: ScrcpyConnection):
    """Background thread to read frames from scrcpy via ffmpeg."""
    try:
        if not conn.ffmpeg_process or not conn.ffmpeg_process.stdout:
            return
        
        while conn.running:
            try:
                # Read PNG frame from ffmpeg output
                img = _read_png_from_stream(conn.ffmpeg_process.stdout)
                if img:
                    # Put frame in queue (drop old frames if queue is full)
                    try:
                        conn.frame_queue.put_nowait(img)
                    except queue.Full:
                        # Remove oldest frame and add new one
                        try:
                            conn.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        conn.frame_queue.put_nowait(img)
                else:
                    # No frame available, check if process is still running
                    if conn.ffmpeg_process.poll() is not None:
                        # Process exited
                        break
                    time.sleep(0.001)  # Small delay to avoid busy waiting
            except Exception as e:
                print(f"[Scrcpy] Error reading frame: {e}", flush=True)
                time.sleep(0.1)
    except Exception as e:
        print(f"[Scrcpy] Frame reader error: {e}", flush=True)


def _start_scrcpy_process(device_id: str | None, max_size: int = 720, 
                          bit_rate: int = 2000000, max_fps: int = 60) -> Optional[subprocess.Popen]:
    """Start scrcpy process with recording to stdout."""
    if not _check_scrcpy_available():
        return None
    
    try:
        # Build scrcpy command
        cmd = ["scrcpy"]
        
        if device_id:
            cmd.extend(["-s", device_id])
        
        cmd.extend([
            "--max-size", str(max_size),
            "--bit-rate", str(bit_rate),
            "--max-fps", str(max_fps),
            "--record=-",  # Output to stdout
            "--no-display",  # Don't show window
            "--no-control",  # Don't accept control
            "--no-audio",  # No audio
        ])
        
        # Start scrcpy process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Give it time to start
        time.sleep(1)
        
        if process.poll() is not None:
            # Process already exited
            stderr = process.stderr.read().decode() if process.stderr else ""
            print(f"[Scrcpy] Process exited: {stderr}", flush=True)
            return None
        
        return process
    except Exception as e:
        print(f"[Scrcpy] Failed to start: {e}", flush=True)
        return None


def _connect_scrcpy(device_id: str | None, max_size: int = 720, 
                    bit_rate: int = 2000000, max_fps: int = 60) -> Optional[ScrcpyConnection]:
    """Connect to scrcpy and start frame reading."""
    with _connection_lock:
        key = device_id or "default"
        if key in _scrcpy_connections:
            conn = _scrcpy_connections[key]
            if conn.running:
                return conn
        
        # Start scrcpy process
        process = _start_scrcpy_process(device_id, max_size, bit_rate, max_fps)
        if not process:
            return None
        
        # Start ffmpeg to decode H.264 stream to images
        try:
            # Use ffmpeg to decode H.264 and output PNG frames
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", "pipe:0",  # Read from stdin (scrcpy output)
                "-vf", f"fps={max_fps}",  # Set frame rate
                "-f", "image2pipe",  # Output as image stream
                "-vcodec", "png",  # PNG format
                "-"  # Output to stdout
            ]
            
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            conn = ScrcpyConnection(
                device_id=key,
                process=process,
                ffmpeg_process=ffmpeg_process,
                running=True,
                max_size=max_size,
                bit_rate=bit_rate,
                max_fps=max_fps
            )
            
            # Start frame reader thread
            conn.thread = threading.Thread(
                target=_scrcpy_frame_reader,
                args=(conn,),
                daemon=True
            )
            conn.thread.start()
            
            _scrcpy_connections[key] = conn
            return conn
        except FileNotFoundError:
            print("[Scrcpy] ffmpeg not found, cannot decode H.264 stream", flush=True)
            if process:
                process.terminate()
            return None
        except Exception as e:
            print(f"[Scrcpy] Failed to setup decoder: {e}", flush=True)
            if process:
                process.terminate()
            return None


def _disconnect_scrcpy(device_id: str | None):
    """Disconnect from scrcpy server."""
    with _connection_lock:
        key = device_id or "default"
        if key in _scrcpy_connections:
            conn = _scrcpy_connections[key]
            conn.running = False
            
            if conn.ffmpeg_process:
                try:
                    conn.ffmpeg_process.terminate()
                    conn.ffmpeg_process.wait(timeout=2)
                except:
                    try:
                        conn.ffmpeg_process.kill()
                    except:
                        pass
            
            if conn.process:
                try:
                    conn.process.terminate()
                    conn.process.wait(timeout=2)
                except:
                    try:
                        conn.process.kill()
                    except:
                        pass
            
            if conn.thread:
                conn.thread.join(timeout=1.0)
            
            del _scrcpy_connections[key]


def get_screenshot_scrcpy(device_id: str | None = None, timeout: int = 10, 
                          quality: int = 75, max_width: int = 720,
                          bit_rate: int = 2000000, max_fps: int = 60) -> Optional[Screenshot]:
    """
    Capture screenshot using scrcpy H.264 stream.
    
    This method is much faster than traditional ADB screenshot methods,
    but requires scrcpy and ffmpeg to be installed.
    
    Args:
        device_id: Optional ADB device ID
        timeout: Timeout in seconds (not used for scrcpy)
        quality: JPEG quality (1-100)
        max_width: Maximum width to resize to
        bit_rate: Video bitrate in bps (default 2Mbps)
        max_fps: Maximum frame rate (default 60)
    
    Returns:
        Screenshot object or None if scrcpy is not available
    """
    try:
        # Connect to scrcpy
        conn = _connect_scrcpy(device_id, max_width, bit_rate, max_fps)
        if not conn:
            return None
        
        # Get latest frame from queue (non-blocking)
        try:
            img = conn.frame_queue.get_nowait()
        except queue.Empty:
            # No frame available yet, return None to fallback to other methods
            return None
        
        # Process image
        width, height = img.size
        return _process_image(img, width, height, quality, max_width)
        
    except Exception as e:
        print(f"[Scrcpy] Screenshot error: {e}", flush=True)
        return None


def cleanup_scrcpy(device_id: str | None = None):
    """Clean up scrcpy connection for a device."""
    _disconnect_scrcpy(device_id)

