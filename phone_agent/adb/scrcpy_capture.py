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
import select
import sys
import socket
import struct
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
    fifo_path: Optional[str] = None  # Path to named pipe (FIFO)
    socket_conn: Optional[socket.socket] = None  # Direct socket connection
    socket_port: Optional[int] = None  # Port for socket connection
    
    def __post_init__(self):
        if self.frame_queue is None:
            self.frame_queue = queue.Queue(maxsize=2)  # Keep only latest 2 frames


_scrcpy_connections: dict[str, ScrcpyConnection] = {}
_connection_lock = threading.Lock()

# Cache for scrcpy availability check to avoid repeated warnings
_scrcpy_available_cache: Optional[bool] = None
_scrcpy_warning_printed = False


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _check_scrcpy_available() -> bool:
    """Check if scrcpy is available in PATH.
    
    Uses caching to avoid repeated warnings when scrcpy is not available.
    If scrcpy is available, always re-checks (in case it gets uninstalled).
    """
    global _scrcpy_available_cache, _scrcpy_warning_printed
    
    # If cached as unavailable, return immediately without re-checking or printing
    if _scrcpy_available_cache is False:
        return False
    
    try:
        result = subprocess.run(
            ["scrcpy", "--version"],
            capture_output=True,
            timeout=2
        )
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
            stdout = result.stdout.decode('utf-8', errors='ignore') if result.stdout else ""
            if not _scrcpy_warning_printed:
                print(f"[Scrcpy] Version check failed (code {result.returncode}): stderr={stderr}, stdout={stdout}", flush=True)
                _scrcpy_warning_printed = True
            _scrcpy_available_cache = False
            return False
        # scrcpy is available, don't cache (always re-check in case it gets uninstalled)
        return True
    except FileNotFoundError:
        if not _scrcpy_warning_printed:
            print("[Scrcpy] scrcpy not found in PATH. Please install scrcpy: https://github.com/Genymobile/scrcpy", flush=True)
            _scrcpy_warning_printed = True
        _scrcpy_available_cache = False
        return False
    except subprocess.TimeoutExpired:
        if not _scrcpy_warning_printed:
            print("[Scrcpy] Version check timeout (scrcpy may be slow to respond)", flush=True)
            _scrcpy_warning_printed = True
        _scrcpy_available_cache = False
        return False
    except Exception as e:
        if not _scrcpy_warning_printed:
            print(f"[Scrcpy] Version check error: {e}", flush=True)
            _scrcpy_warning_printed = True
        _scrcpy_available_cache = False
        return False


def _read_png_from_stream(stream, timeout=0.5) -> Optional[Image.Image]:
    """Read a PNG image from stream using PIL's built-in PNG reader.
    
    PIL's Image.open can read PNG from a stream, but it needs the stream to be seekable
    or we need to read the complete PNG into memory first.
    """
    try:
        # First, check if data is available
        if sys.platform != 'win32':
            try:
                fd = stream.fileno()
                ready, _, _ = select.select([fd], [], [], timeout)
                if not ready:
                    return None  # No data available
            except (ValueError, OSError):
                # If select fails, try reading anyway
                pass
        
        # PNG signature: 89 50 4E 47 0D 0A 1A 0A
        signature = b'\x89PNG\r\n\x1a\n'
        
        # Read first 8 bytes to check signature
        header = stream.read(8)
        if not header or len(header) < 8:
            if not hasattr(_read_png_from_stream, '_logged_empty_read'):
                print(f"[Scrcpy] _read_png_from_stream: Empty or incomplete read (got {len(header) if header else 0} bytes)", flush=True)
                _read_png_from_stream._logged_empty_read = True
            return None
        
        # Log first read for debugging (only once)
        if not hasattr(_read_png_from_stream, '_logged_first_read'):
            print(f"[Scrcpy] _read_png_from_stream: First 8 bytes (hex): {header.hex()}", flush=True)
            print(f"[Scrcpy] _read_png_from_stream: First 8 bytes (ascii): {header!r}", flush=True)
            _read_png_from_stream._logged_first_read = True
        
        # Check if we have PNG signature
        if header != signature:
            # Try to find signature in buffer
            buffer = header
            # Read more data to find signature (up to 64KB)
            for _ in range(64):  # Try up to 64KB in 1KB chunks
                if sys.platform != 'win32':
                    try:
                        fd = stream.fileno()
                        if not select.select([fd], [], [], 0.1)[0]:
                            break
                    except (ValueError, OSError):
                        pass
                more = stream.read(1024)
                if not more:
                    break
                buffer += more
                pos = buffer.find(signature)
                if pos >= 0:
                    buffer = buffer[pos:]
                    break
                if len(buffer) > 65536:  # Max 64KB
                    return None
            else:
                # Signature not found - log first few bytes for debugging
                if not hasattr(_read_png_from_stream, '_logged_no_signature'):
                    print(f"[Scrcpy] _read_png_from_stream: No PNG signature found, first 64 bytes (hex): {buffer[:64].hex()}", flush=True)
                    print(f"[Scrcpy] _read_png_from_stream: First 64 bytes (ascii): {buffer[:64]!r}", flush=True)
                    _read_png_from_stream._logged_no_signature = True
                return None
        else:
            buffer = header
        
        # Now read PNG data chunk by chunk until IEND
        png_data = buffer
        iend_found = False
        max_size = 10 * 1024 * 1024  # Max 10MB PNG (safety limit)
        read_attempts = 0
        max_read_attempts = 1000  # Safety limit for chunk reading
        
        while not iend_found and len(png_data) < max_size and read_attempts < max_read_attempts:
            read_attempts += 1
            
            # Check if data is available before reading chunk header
            if sys.platform != 'win32':
                try:
                    fd = stream.fileno()
                    ready, _, _ = select.select([fd], [], [], timeout)
                    if not ready:
                        # No data available, but we've started reading a PNG, so wait a bit
                        if read_attempts > 10:  # After 10 attempts, give up
                            return None
                        time.sleep(0.01)
                        continue
                except (ValueError, OSError):
                    pass
            
            # Read chunk header (8 bytes: length + type)
            chunk_header = stream.read(8)
            if len(chunk_header) < 8:
                return None
            
            chunk_length = int.from_bytes(chunk_header[:4], 'big')
            chunk_type = chunk_header[4:8]
            
            # Safety check: chunk length should be reasonable
            if chunk_length > 10 * 1024 * 1024:  # Max 10MB per chunk
                print(f"[Scrcpy] _read_png_from_stream: Suspicious chunk length: {chunk_length}", flush=True)
                return None
            
            # Read chunk data (may need multiple reads for large chunks)
            chunk_data = b''
            while len(chunk_data) < chunk_length:
                if sys.platform != 'win32':
                    try:
                        fd = stream.fileno()
                        ready, _, _ = select.select([fd], [], [], timeout)
                        if not ready:
                            return None
                    except (ValueError, OSError):
                        pass
                remaining = chunk_length - len(chunk_data)
                data = stream.read(remaining)
                if not data:
                    return None
                chunk_data += data
            
            # Read CRC (4 bytes)
            if sys.platform != 'win32':
                try:
                    fd = stream.fileno()
                    ready, _, _ = select.select([fd], [], [], timeout)
                    if not ready:
                        return None
                except (ValueError, OSError):
                    pass
            
            crc = stream.read(4)
            if len(crc) < 4:
                return None
            
            png_data += chunk_header + chunk_data + crc
            
            if chunk_type == b'IEND':
                iend_found = True
        
        if not iend_found:
            if read_attempts >= max_read_attempts:
                print(f"[Scrcpy] _read_png_from_stream: Max read attempts reached, PNG incomplete", flush=True)
            return None  # PNG incomplete
        
        # Decode PNG using PIL
        try:
            img = Image.open(BytesIO(png_data))
            img.load()  # Force loading to verify it's valid
            return img
        except Exception as e:
            print(f"[Scrcpy] _read_png_from_stream: Failed to decode PNG: {type(e).__name__}: {e}", flush=True)
            return None
    except Exception as e:
        # Log error for debugging
        import traceback
        print(f"[Scrcpy] _read_png_from_stream error: {type(e).__name__}: {e}", flush=True)
        print(f"[Scrcpy] _read_png_from_stream traceback: {traceback.format_exc()}", flush=True)
        return None


def _scrcpy_socket_frame_reader(conn: ScrcpyConnection):
    """Background thread to read frames from scrcpy socket and decode with ffmpeg.
    
    Note: This function is currently not used. The current implementation uses
    stdout mode with _scrcpy_frame_reader() which is simpler and more reliable.
    This socket reader code is kept for potential future use.
    """
    try:
        if not conn.socket_conn:
            print(f"[Scrcpy] Socket frame reader: socket not available", flush=True)
            return
        
        print(f"[Scrcpy] Socket frame reader: Started, reading H.264 from socket...", flush=True)
        
        # Start ffmpeg to decode H.264 stream
        ffmpeg_cmd = [
            "ffmpeg",
            "-loglevel", "warning",
            "-f", "h264",  # Input format is raw H.264
            "-i", "pipe:0",  # Read from stdin
            "-f", "image2pipe",  # Output as image stream
            "-vcodec", "png",  # PNG format
            "-pix_fmt", "rgb24",  # Use RGB24 pixel format
            "-fps_mode", "passthrough",  # Use fps_mode instead of deprecated -vsync
            "-"  # Output to stdout
        ]
        
        print(f"[Scrcpy] Starting ffmpeg for socket stream: {' '.join(ffmpeg_cmd)}", flush=True)
        
        ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        conn.ffmpeg_process = ffmpeg_process
        
        frame_count = 0
        error_count = 0
        
        # Read H.264 packets from socket and feed to ffmpeg
        def feed_ffmpeg():
            try:
                while conn.running and ffmpeg_process.poll() is None:
                    h264_data = _read_h264_from_socket(conn.socket_conn)
                    if h264_data:
                        try:
                            ffmpeg_process.stdin.write(h264_data)
                            ffmpeg_process.stdin.flush()
                        except BrokenPipeError:
                            print(f"[Scrcpy] Socket frame reader: ffmpeg stdin broken pipe", flush=True)
                            break
                        except Exception as e:
                            print(f"[Scrcpy] Socket frame reader: Error writing to ffmpeg: {e}", flush=True)
                            break
                    else:
                        # No data, wait a bit
                        time.sleep(0.01)
            except Exception as e:
                print(f"[Scrcpy] Socket frame reader: Error in feed_ffmpeg: {e}", flush=True)
            finally:
                if ffmpeg_process.stdin:
                    ffmpeg_process.stdin.close()
        
        # Start thread to feed H.264 data to ffmpeg
        feed_thread = threading.Thread(target=feed_ffmpeg, daemon=True, name="scrcpy-socket-feed")
        feed_thread.start()
        
        # Read PNG frames from ffmpeg output
        time.sleep(2)  # Wait for ffmpeg to start
        
        while conn.running:
            try:
                if ffmpeg_process.poll() is not None:
                    print(f"[Scrcpy] Socket frame reader: ffmpeg process exited (code {ffmpeg_process.returncode})", flush=True)
                    break
                
                # Read PNG frame from ffmpeg output
                img = _read_png_from_stream(ffmpeg_process.stdout, timeout=0.5)
                if img:
                    frame_count += 1
                    error_count = 0
                    
                    # Put frame in queue
                    try:
                        conn.frame_queue.put_nowait(img)
                    except queue.Full:
                        try:
                            conn.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                        conn.frame_queue.put_nowait(img)
                    
                    if frame_count <= 3:
                        print(f"[Scrcpy] Socket frame reader: Successfully read frame {frame_count} (size: {img.size})", flush=True)
                else:
                    error_count += 1
                    if error_count > 100:
                        print(f"[Scrcpy] Socket frame reader: Too many errors, stopping", flush=True)
                        break
                    
                time.sleep(0.05)
            except Exception as e:
                print(f"[Scrcpy] Socket frame reader: Error: {type(e).__name__}: {e}", flush=True)
                time.sleep(0.1)
        
    except Exception as e:
        print(f"[Scrcpy] Socket frame reader: Fatal error: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] Socket frame reader: Traceback: {traceback.format_exc()}", flush=True)
    finally:
        if conn.socket_conn:
            try:
                conn.socket_conn.close()
            except:
                pass


def _scrcpy_frame_reader(conn: ScrcpyConnection):
    """Background thread to read frames from scrcpy via ffmpeg."""
    try:
        if not conn.ffmpeg_process or not conn.ffmpeg_process.stdout:
            print(f"[Scrcpy] Frame reader: ffmpeg process or stdout not available", flush=True)
            return
        
        print(f"[Scrcpy] Frame reader: Started, waiting for frames from ffmpeg...", flush=True)
        
        # Check ffmpeg process status
        if conn.ffmpeg_process:
            return_code = conn.ffmpeg_process.poll()
            if return_code is not None:
                print(f"[Scrcpy] Frame reader: WARNING - ffmpeg process already exited with code {return_code}", flush=True)
                # Try to read stderr to see what happened
                if conn.ffmpeg_process.stderr:
                    try:
                        stderr_data = conn.ffmpeg_process.stderr.read()
                        if stderr_data:
                            print(f"[Scrcpy] Frame reader: ffmpeg stderr: {stderr_data.decode('utf-8', errors='ignore')}", flush=True)
                    except:
                        pass
        
        frame_count = 0
        error_count = 0
        last_error_time = 0
        no_data_count = 0
        
        # Check if stdout is readable and wait a bit for ffmpeg to start outputting
        # ffmpeg may need to wait for the first keyframe (I-frame) before it can decode
        # Note: ffmpeg has detected the stream (from stderr logs), but may need keyframe to start outputting PNG
        print(f"[Scrcpy] Frame reader: Waiting 10 seconds for ffmpeg to receive first keyframe and start outputting PNG frames...", flush=True)
        print(f"[Scrcpy] Frame reader: ffmpeg has detected video stream, waiting for first I-frame...", flush=True)
        time.sleep(10)  # Give ffmpeg more time to receive keyframe and start outputting data
        
        # Check process status again
        if conn.ffmpeg_process:
            return_code = conn.ffmpeg_process.poll()
            if return_code is not None:
                print(f"[Scrcpy] Frame reader: ERROR - ffmpeg process exited with code {return_code}", flush=True)
                return
        
        if sys.platform != 'win32':
            try:
                fd = conn.ffmpeg_process.stdout.fileno()
                ready, _, _ = select.select([fd], [], [], 0.1)
                if ready:
                    print(f"[Scrcpy] Frame reader: stdout is readable (fd={fd})", flush=True)
                else:
                    print(f"[Scrcpy] Frame reader: stdout not ready yet (fd={fd}), will keep trying...", flush=True)
            except Exception as e:
                print(f"[Scrcpy] Frame reader: Error checking stdout: {e}", flush=True)
        
        while conn.running:
            try:
                # Check if data is available before attempting to read
                if sys.platform != 'win32':
                    try:
                        fd = conn.ffmpeg_process.stdout.fileno()
                        ready, _, _ = select.select([fd], [], [], 0.5)
                        if not ready:
                            no_data_count += 1
                            if no_data_count % 20 == 0:  # Log every 20 attempts (~10s)
                                print(f"[Scrcpy] Frame reader: Still no frame after {no_data_count} attempts (~{no_data_count * 0.5:.1f}s)", flush=True)
                            time.sleep(0.1)
                            continue
                    except (ValueError, OSError) as e:
                        print(f"[Scrcpy] Frame reader: Error in select: {e}", flush=True)
                        time.sleep(0.1)
                        continue
                
                # Read PNG frame from ffmpeg output
                img = _read_png_from_stream(conn.ffmpeg_process.stdout, timeout=0.5)
                if img:
                    frame_count += 1
                    error_count = 0  # Reset error count on success
                    
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
                    
                    # Log first few frames for debugging
                    if frame_count <= 3:
                        print(f"[Scrcpy] Frame reader: Successfully read frame {frame_count} (size: {img.size})", flush=True)
                    no_data_count = 0  # Reset no data counter on success
                else:
                    # No frame available
                    no_data_count += 1
                    # Log periodically if no frames after a while
                    if no_data_count == 1:
                        print(f"[Scrcpy] Frame reader: No frame available (attempt {no_data_count}), waiting...", flush=True)
                    elif no_data_count % 20 == 0:  # Log every 20 attempts (~10 seconds with 0.5s timeout)
                        print(f"[Scrcpy] Frame reader: Still no frame after {no_data_count} attempts (~{no_data_count * 0.5:.1f}s)", flush=True)
                    
                    # Check if process is still running
                    if conn.ffmpeg_process.poll() is not None:
                        # Process exited
                        exit_code = conn.ffmpeg_process.returncode
                        stderr = ""
                        try:
                            if conn.ffmpeg_process.stderr:
                                stderr = conn.ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                        except:
                            pass
                        print(f"[Scrcpy] Frame reader: ffmpeg process exited (code {exit_code})", flush=True)
                        if stderr:
                            print(f"[Scrcpy] Frame reader: ffmpeg stderr: {stderr}", flush=True)
                        break
                    
                    # Check if ffmpeg is actually receiving data from scrcpy
                    # Log periodically if no frames after a while (for debugging)
                    if frame_count == 0 and error_count == 0:
                        # First time waiting, log after 2 seconds
                        if time.time() - (getattr(conn, '_reader_start_time', time.time())) > 2.0:
                            if not hasattr(conn, '_logged_waiting'):
                                print(f"[Scrcpy] Frame reader: Still waiting for first frame (scrcpy may need more time to start streaming)", flush=True)
                                # Check if scrcpy process is still running
                                if conn.process:
                                    scrcpy_status = "running" if conn.process.poll() is None else f"exited (code {conn.process.returncode})"
                                    print(f"[Scrcpy] Frame reader: scrcpy process status: {scrcpy_status}", flush=True)
                                # Check if ffmpeg process is still running
                                if conn.ffmpeg_process:
                                    ffmpeg_status = "running" if conn.ffmpeg_process.poll() is None else f"exited (code {conn.ffmpeg_process.returncode})"
                                    print(f"[Scrcpy] Frame reader: ffmpeg process status: {ffmpeg_status}", flush=True)
                                conn._logged_waiting = True
                    
                    time.sleep(0.05)  # 50ms delay to reduce CPU usage and give data time to arrive
            except Exception as e:
                error_count += 1
                current_time = time.time()
                # Only log errors occasionally to avoid spam
                if current_time - last_error_time > 5.0 or error_count == 1:
                    print(f"[Scrcpy] Frame reader: Error reading frame (count: {error_count}): {type(e).__name__}: {e}", flush=True)
                    last_error_time = current_time
                
                # If too many errors, stop trying
                if error_count > 100:
                    print(f"[Scrcpy] Frame reader: Too many errors ({error_count}), stopping", flush=True)
                    break
                    
                time.sleep(0.1)
    except Exception as e:
        print(f"[Scrcpy] Frame reader: Fatal error: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] Frame reader: Traceback: {traceback.format_exc()}", flush=True)


def _start_scrcpy_stdout(device_id: str | None, max_size: int = 720, 
                          bit_rate: int = 2000000, max_fps: int = 60) -> Optional[subprocess.Popen]:
    """Start scrcpy process with stdout output (MKV stream).
    
    Uses --record=- to output video stream to stdout, which is then decoded by ffmpeg.
    This is the recommended method as it's simpler and more reliable than socket connection.
    
    Returns:
        scrcpy process or None if failed.
    """
    if not _check_scrcpy_available():
        print("[Scrcpy] scrcpy not available, cannot start process", flush=True)
        return None
    
    try:
        # Build scrcpy command with stdout output
        cmd = ["scrcpy"]
        
        if device_id:
            cmd.extend(["-s", device_id])
        
        cmd.extend([
            "--max-size", str(max_size),
            "--video-bit-rate", str(bit_rate),
            "--max-fps", str(max_fps),
            "--record=-",  # Output to stdout (required, otherwise scrcpy exits with error)
            "--record-format=mkv",  # Required format for --record=- in scrcpy 3.3.4+
            "--no-window",
            "--no-control",
            "--no-audio",
        ])
        
        print(f"[Scrcpy] Starting scrcpy with stdout output: {' '.join(cmd)}", flush=True)
        
        # Start scrcpy process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            env=dict(os.environ, PYTHONUNBUFFERED='1')
        )
        
        # Give scrcpy time to start and establish connection
        time.sleep(3)  # Wait for scrcpy to start and establish connection
        
        if process.poll() is not None:
            stderr = ""
            try:
                if process.stderr:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"[Scrcpy] Error reading process output: {e}", flush=True)
            
            exit_code = process.returncode
            print(f"[Scrcpy] Process exited immediately (code {exit_code})", flush=True)
            if stderr:
                print(f"[Scrcpy] stderr: {stderr}", flush=True)
            return None
        
        print(f"[Scrcpy] Process started successfully (PID: {process.pid})", flush=True)
        return process
        
    except Exception as e:
        print(f"[Scrcpy] Failed to start scrcpy process: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] Traceback: {traceback.format_exc()}", flush=True)
        return None


def _connect_scrcpy_socket(port: int, timeout: int = 5) -> Optional[socket.socket]:
    """Connect directly to scrcpy socket and read H.264 stream.
    
    scrcpy protocol:
    1. Device name (64 bytes, null-terminated)
    2. Initial configuration (12 bytes)
    3. Video stream (H.264 NAL units)
    
    Note: This function is currently not used. The current implementation uses
    stdout mode (--record=-) which is simpler and more reliable. This socket
    connection code is kept for potential future use.
    
    Returns:
        socket connection or None if failed.
    """
    try:
        # Connect to localhost:port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(('localhost', port))
        sock.settimeout(None)  # Remove timeout after connection
        print(f"[Scrcpy] Connected to socket on port {port}", flush=True)
        
        # Read device name (64 bytes)
        device_name = sock.recv(64)
        if len(device_name) < 64:
            print(f"[Scrcpy] Failed to read device name (got {len(device_name)} bytes)", flush=True)
            sock.close()
            return None
        
        device_name_str = device_name.rstrip(b'\x00').decode('utf-8', errors='ignore')
        print(f"[Scrcpy] Device name: {device_name_str}", flush=True)
        
        # Read initial configuration (12 bytes)
        config = sock.recv(12)
        if len(config) < 12:
            print(f"[Scrcpy] Failed to read configuration (got {len(config)} bytes)", flush=True)
            sock.close()
            return None
        
        # Parse configuration
        width = struct.unpack('>H', config[0:2])[0]
        height = struct.unpack('>H', config[2:4])[0]
        # Other fields are not needed for now
        
        print(f"[Scrcpy] Video configuration: {width}x{height}", flush=True)
        
        return sock
        
    except socket.timeout:
        print(f"[Scrcpy] Socket connection timeout on port {port}", flush=True)
        return None
    except ConnectionRefusedError:
        print(f"[Scrcpy] Connection refused on port {port} (scrcpy may not be ready)", flush=True)
        return None
    except Exception as e:
        print(f"[Scrcpy] Failed to connect to socket: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] Traceback: {traceback.format_exc()}", flush=True)
        return None


def _read_h264_from_socket(sock: socket.socket) -> Optional[bytes]:
    """Read H.264 packet from scrcpy socket.
    
    scrcpy video packet format:
    - 1 byte: flags (0x00 = keyframe, 0x01 = P-frame, etc.)
    - 4 bytes: PTS (presentation timestamp) in microseconds
    - 4 bytes: packet size
    - N bytes: H.264 data
    
    Note: This function is currently not used. The current implementation uses
    stdout mode (--record=-) which is simpler and more reliable. This socket
    reading code is kept for potential future use.
    
    Returns:
        H.264 data bytes or None if failed.
    """
    try:
        # Read packet header (9 bytes)
        header = sock.recv(9)
        if len(header) < 9:
            return None
        
        flags = header[0]
        pts = struct.unpack('>I', header[1:5])[0]
        size = struct.unpack('>I', header[5:9])[0]
        
        # Safety check
        if size > 10 * 1024 * 1024:  # Max 10MB
            print(f"[Scrcpy] Suspicious packet size: {size}", flush=True)
            return None
        
        # Read packet data
        data = b''
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        
        return data
        
    except Exception as e:
        print(f"[Scrcpy] Error reading H.264 packet: {type(e).__name__}: {e}", flush=True)
        return None


def _start_scrcpy_process(device_id: str | None, max_size: int = 720, 
                          bit_rate: int = 2000000, max_fps: int = 60, fifo_path: str | None = None) -> tuple[Optional[subprocess.Popen], str | None]:
    """Start scrcpy process with recording to named pipe (FIFO).
    
    Returns:
        (process, fifo_path) tuple. fifo_path is None if using stdout.
    """
    if not _check_scrcpy_available():
        print("[Scrcpy] scrcpy not available, cannot start process", flush=True)
        return None, None
    
    try:
        # Create named pipe (FIFO) for better data flow control
        if not fifo_path:
            import tempfile
            fifo_path = os.path.join(tempfile.gettempdir(), f"scrcpy_{device_id or 'default'}_{os.getpid()}.fifo")
        
        # Remove existing FIFO if any
        if os.path.exists(fifo_path):
            os.remove(fifo_path)
        
        # Create FIFO
        try:
            os.mkfifo(fifo_path)
            print(f"[Scrcpy] Created FIFO: {fifo_path}", flush=True)
        except OSError as e:
            print(f"[Scrcpy] Failed to create FIFO {fifo_path}: {e}", flush=True)
            return None, None
        
        # Build scrcpy command
        cmd = ["scrcpy"]
        
        if device_id:
            cmd.extend(["-s", device_id])
        
        cmd.extend([
            "--max-size", str(max_size),
            "--video-bit-rate", str(bit_rate),  # Use --video-bit-rate for scrcpy 3.3.4+
            "--max-fps", str(max_fps),
            "--record", fifo_path,  # Output to named pipe
            "--record-format=mkv",  # Required format for --record in scrcpy 3.3.4+
            # Don't specify --video-encoder, let scrcpy auto-detect the best encoder
            # Different devices support different encoders (OMX.hisi.video.encoder.avc, c2.android.avc.encoder, etc.)
            "--no-window",  # Disable window (implies --no-video-playback in scrcpy 3.3.4+)
            "--no-control",  # Don't accept control
            "--no-audio",  # No audio
            # Note: --turn-screen-off requires --control, so we can't use it with --no-control
        ])
        
        print(f"[Scrcpy] Starting scrcpy with command: {' '.join(cmd)}", flush=True)
        
        # Start scrcpy process
        # No need for stdout pipe when using FIFO
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,  # Still capture stdout for stderr messages
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered
            env=dict(os.environ, PYTHONUNBUFFERED='1')  # Ensure unbuffered output
        )
        
        # Give scrcpy time to start and establish connection
        # scrcpy needs time to connect to device and start streaming
        time.sleep(2)  # Increased wait time for scrcpy to establish connection
        
        if process.poll() is not None:
            # Process already exited
            stderr = ""
            stdout = ""
            try:
                if process.stderr:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
                if process.stdout:
                    stdout = process.stdout.read().decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"[Scrcpy] Error reading process output: {e}", flush=True)
            
            exit_code = process.returncode
            print(f"[Scrcpy] Process exited immediately (code {exit_code})", flush=True)
            if stderr:
                print(f"[Scrcpy] stderr: {stderr}", flush=True)
            if stdout:
                print(f"[Scrcpy] stdout: {stdout}", flush=True)
            
            # Common error patterns
            if "device offline" in stderr.lower() or "no devices" in stderr.lower():
                print("[Scrcpy] Error: Device not found or offline. Check ADB connection.", flush=True)
            elif "adb" in stderr.lower() and "error" in stderr.lower():
                print("[Scrcpy] Error: ADB connection issue. Check device connection.", flush=True)
            elif "encoder" in stderr.lower() or "codec" in stderr.lower():
                print("[Scrcpy] Error: Video encoder issue. Device may not support H.264 encoding.", flush=True)
            
            # Clean up FIFO on error
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.remove(fifo_path)
                except:
                    pass
            return None, None
        
        print(f"[Scrcpy] Process started successfully (PID: {process.pid})", flush=True)
        return process, fifo_path
    except FileNotFoundError:
        print("[Scrcpy] scrcpy executable not found. Please install scrcpy: https://github.com/Genymobile/scrcpy", flush=True)
        # Clean up FIFO on error
        if fifo_path and os.path.exists(fifo_path):
            try:
                os.remove(fifo_path)
            except:
                pass
        return None, None
    except Exception as e:
        print(f"[Scrcpy] Failed to start: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] Traceback: {traceback.format_exc()}", flush=True)
        # Clean up FIFO on error
        if fifo_path and os.path.exists(fifo_path):
            try:
                os.remove(fifo_path)
            except:
                pass
        return None, None


def _connect_scrcpy(device_id: str | None, max_size: int = 720, 
                    bit_rate: int = 2000000, max_fps: int = 60, 
                    use_socket: bool = True) -> Optional[ScrcpyConnection]:
    """Connect to scrcpy and start frame reading.
    
    Args:
        device_id: Device ID
        max_size: Maximum size
        bit_rate: Bit rate
        max_fps: Maximum FPS
        use_socket: If True, use stdout mode (--record=-) for video stream.
                    If False, use FIFO (named pipe) mode.
                    Note: Despite the name, both modes use scrcpy's stdout/FIFO output,
                    not direct socket connection. Socket connection code exists but is
                    not currently used as stdout mode is simpler and more reliable.
    """
    with _connection_lock:
        key = device_id or "default"
        if key in _scrcpy_connections:
            conn = _scrcpy_connections[key]
            if conn.running:
                print(f"[Scrcpy] Reusing existing connection for device {key}", flush=True)
                return conn
        
        print(f"[Scrcpy] Creating new connection for device {key} (use_socket={use_socket})", flush=True)
        
        if use_socket:
            # Use stdout pipe mode (simpler and more reliable than FIFO)
            # scrcpy outputs MKV stream to stdout via --record=-, which is then decoded by ffmpeg
            # Note: use_socket=True actually uses stdout mode, not direct socket connection
            # This is the recommended approach as it's simpler and more reliable
            process = _start_scrcpy_stdout(device_id, max_size, bit_rate, max_fps)
            if not process:
                print("[Scrcpy] Failed to start scrcpy process with stdout output", flush=True)
                return None
            
            # Use ffmpeg to decode H.264 from MKV stream (from stdout)
            ffmpeg_process = None
            try:
                ffmpeg_cmd = [
                    "ffmpeg",
                    "-loglevel", "warning",
                    "-probesize", "32768",
                    "-analyzeduration", "1000000",
                    "-fflags", "nobuffer+discardcorrupt",
                    "-flags", "low_delay",
                    "-thread_queue_size", "512",
                    "-f", "matroska",  # Input format is MKV (from scrcpy --record-format=mkv)
                    "-i", "pipe:0",  # Read from stdin (scrcpy stdout)
                    "-f", "image2pipe",  # Output as image stream
                    "-vcodec", "png",  # PNG format
                    "-pix_fmt", "rgb24",  # Use RGB24 pixel format
                    "-fps_mode", "passthrough",  # Use fps_mode instead of deprecated -vsync
                    "-"  # Output to stdout
                ]
                
                print(f"[Scrcpy] Starting ffmpeg for stdout stream: {' '.join(ffmpeg_cmd)}", flush=True)
                
                ffmpeg_process = subprocess.Popen(
                    ffmpeg_cmd,
                    stdin=process.stdout,  # Read from scrcpy stdout
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                
                # Start thread to monitor ffmpeg stderr
                def monitor_ffmpeg_stderr():
                    try:
                        if ffmpeg_process.stderr:
                            output_lines = []
                            while ffmpeg_process.poll() is None:
                                line = ffmpeg_process.stderr.readline()
                                if line:
                                    decoded = line.decode('utf-8', errors='ignore').strip()
                                    if decoded:
                                        output_lines.append(decoded)
                                        print(f"[Scrcpy] ffmpeg stderr: {decoded}", flush=True)
                                else:
                                    time.sleep(0.1)
                            # If process exited, print all output
                            if output_lines:
                                print(f"[Scrcpy] ffmpeg: All output: {output_lines}", flush=True)
                    except Exception as e:
                        print(f"[Scrcpy] Error monitoring ffmpeg stderr: {e}", flush=True)
                
                stderr_monitor = threading.Thread(target=monitor_ffmpeg_stderr, daemon=True, name="ffmpeg-stderr-monitor")
                stderr_monitor.start()
                
                # Start thread to monitor scrcpy stderr
                def monitor_scrcpy_stderr():
                    try:
                        if process.stderr:
                            while process.poll() is None:
                                line = process.stderr.readline()
                                if line:
                                    decoded = line.decode('utf-8', errors='ignore').strip()
                                    if decoded:
                                        print(f"[Scrcpy] scrcpy stderr: {decoded}", flush=True)
                                else:
                                    time.sleep(0.1)
                    except Exception as e:
                        print(f"[Scrcpy] Error monitoring scrcpy stderr: {e}", flush=True)
                
                scrcpy_stderr_monitor = threading.Thread(target=monitor_scrcpy_stderr, daemon=True, name="scrcpy-stderr-monitor")
                scrcpy_stderr_monitor.start()
                
                # Wait a bit for processes to initialize
                time.sleep(1)  # Give ffmpeg time to start
                
                # Check if scrcpy process is still running
                if process.poll() is not None:
                    exit_code = process.returncode
                    stderr = ""
                    try:
                        if process.stderr:
                            stderr = process.stderr.read().decode('utf-8', errors='ignore')
                    except:
                        pass
                    print(f"[Scrcpy] scrcpy process exited during initialization (code {exit_code})", flush=True)
                    if stderr:
                        print(f"[Scrcpy] scrcpy stderr: {stderr}", flush=True)
                    if ffmpeg_process:
                        try:
                            ffmpeg_process.terminate()
                        except:
                            pass
                    return None
                
                # Check if ffmpeg process is still running
                if ffmpeg_process.poll() is not None:
                    exit_code = ffmpeg_process.returncode
                    stderr = ""
                    try:
                        if ffmpeg_process.stderr:
                            stderr = ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                    except:
                        pass
                    print(f"[Scrcpy] ffmpeg process exited during initialization (code {exit_code})", flush=True)
                    if stderr:
                        print(f"[Scrcpy] ffmpeg stderr: {stderr}", flush=True)
                    if process:
                        try:
                            process.terminate()
                        except:
                            pass
                    return None
                
                # Check if scrcpy stdout has data (peek at first few bytes)
                time.sleep(2)  # Wait a bit more for scrcpy to start outputting
                if sys.platform != 'win32':
                    try:
                        fd = process.stdout.fileno()
                        ready, _, _ = select.select([fd], [], [], 0.5)
                        if ready:
                            print(f"[Scrcpy] scrcpy stdout is readable (fd={fd})", flush=True)
                        else:
                            print(f"[Scrcpy] scrcpy stdout not ready yet (fd={fd})", flush=True)
                            # Check if scrcpy process is still running
                            if process.poll() is not None:
                                print(f"[Scrcpy] WARNING: scrcpy process exited (code {process.returncode})", flush=True)
                                # Try to read stderr for more info
                                try:
                                    if process.stderr:
                                        stderr_data = process.stderr.read()
                                        if stderr_data:
                                            print(f"[Scrcpy] scrcpy stderr (after exit): {stderr_data.decode('utf-8', errors='ignore')}", flush=True)
                                except:
                                    pass
                    except Exception as e:
                        print(f"[Scrcpy] Error checking scrcpy stdout: {e}", flush=True)
                
                # Don't close scrcpy stdout - ffmpeg needs it to read data
                # process.stdout.close()  # DON'T close - ffmpeg reads from it
                
                # Create connection object
                conn = ScrcpyConnection(
                    device_id=key,
                    process=process,
                    ffmpeg_process=ffmpeg_process,
                    running=True,
                    max_size=max_size,
                    bit_rate=bit_rate,
                    max_fps=max_fps
                )
                
                # Start frame reader thread (use regular frame reader, not socket reader)
                conn.thread = threading.Thread(
                    target=_scrcpy_frame_reader,
                    args=(conn,),
                    daemon=True,
                    name=f"scrcpy-stdout-reader-{key}"
                )
                conn.thread.start()
                
                _scrcpy_connections[key] = conn
                print(f"[Scrcpy] Connection established successfully for device {key} (stdout mode)", flush=True)
                return conn
            except FileNotFoundError:
                print("[Scrcpy] ffmpeg not found, cannot decode H.264 stream. Please install ffmpeg: https://ffmpeg.org/download.html", flush=True)
                if process:
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except:
                        try:
                            process.kill()
                        except:
                            pass
                return None
            except Exception as e:
                print(f"[Scrcpy] Failed to start ffmpeg: {type(e).__name__}: {e}", flush=True)
                import traceback
                print(f"[Scrcpy] Traceback: {traceback.format_exc()}", flush=True)
                if process:
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except:
                        try:
                            process.kill()
                        except:
                            pass
                if ffmpeg_process:
                    try:
                        ffmpeg_process.terminate()
                        ffmpeg_process.wait(timeout=2)
                    except:
                        try:
                            ffmpeg_process.kill()
                        except:
                            pass
                return None
        else:
            # Use FIFO (original method)
            process, fifo_path = _start_scrcpy_process(device_id, max_size, bit_rate, max_fps)
            if not process or not fifo_path:
                print("[Scrcpy] Failed to start scrcpy process or create FIFO", flush=True)
                return None
        
        # Start ffmpeg to decode H.264 stream to images
        try:
            # Use ffmpeg to decode H.264 from MKV and output PNG frames
            # scrcpy outputs MKV format with H.264 video
            # Note: ffmpeg may need to wait for scrcpy to start outputting data
            # Increase probesize and analyzeduration to ensure ffmpeg can properly detect the stream
            # Use -thread_queue_size to handle buffering better
            # Use -loglevel info to see when ffmpeg starts reading input
            ffmpeg_cmd = [
                "ffmpeg",
                "-loglevel", "warning",  # Use warning level to reduce noise
                "-probesize", "32768",  # Smaller probe size for faster startup
                "-analyzeduration", "1000000",  # Reduced analysis duration (1 second) for faster startup
                "-fflags", "nobuffer+discardcorrupt",  # Reduce buffering and discard corrupt frames
                "-flags", "low_delay",  # Low delay mode for real-time streaming
                "-thread_queue_size", "512",  # Larger queue for better buffering
                "-err_detect", "ignore_err",  # Ignore errors and continue decoding
                "-f", "matroska",  # Input format is MKV (from scrcpy --record-format=mkv)
                "-i", fifo_path,  # Read from named pipe (FIFO)
                # Force output frames immediately
                "-f", "image2pipe",  # Output as image stream
                "-vcodec", "png",  # PNG format
                "-pix_fmt", "rgb24",  # Use RGB24 pixel format for better compatibility
                "-fps_mode", "passthrough",  # Use fps_mode instead of deprecated -vsync
                "-update", "1",  # Force output of each frame (important for image2pipe)
                "-flush_packets", "1",  # Flush packets immediately to reduce latency
                "-"  # Output to stdout
            ]
            
            print(f"[Scrcpy] Starting ffmpeg with command: {' '.join(ffmpeg_cmd)}", flush=True)
            
            # IMPORTANT: Start ffmpeg AFTER scrcpy has started (but scrcpy may not have opened FIFO yet)
            # FIFO behavior: 
            # - If only reader opens FIFO, it blocks until writer opens
            # - If only writer opens FIFO, it blocks until reader opens
            # - Both need to be open for data to flow
            # scrcpy will open FIFO when it's ready to start recording
            # ffmpeg will block on opening FIFO until scrcpy opens it for writing
            print(f"[Scrcpy] Starting ffmpeg to read from FIFO (will block until scrcpy opens FIFO for writing)...", flush=True)
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Give ffmpeg a moment to attempt opening the FIFO
            # This will block until scrcpy opens the FIFO for writing
            time.sleep(1)
            
            # Start threads to monitor both scrcpy and ffmpeg stderr for debugging
            def monitor_scrcpy_stderr():
                try:
                    if process.stderr:
                        # Read stderr in chunks
                        while process.poll() is None:
                            line = process.stderr.readline()
                            if line:
                                decoded = line.decode('utf-8', errors='ignore').strip()
                                if decoded:
                                    print(f"[Scrcpy] scrcpy stderr: {decoded}", flush=True)
                except Exception as e:
                    print(f"[Scrcpy] Error monitoring scrcpy stderr: {e}", flush=True)
            
            def monitor_ffmpeg_stderr():
                try:
                    if ffmpeg_process.stderr:
                        # Read stderr in chunks
                        last_output_time = time.time()
                        first_output = True
                        output_lines = []
                        while ffmpeg_process.poll() is None:
                            line = ffmpeg_process.stderr.readline()
                            if line:
                                decoded = line.decode('utf-8', errors='ignore').strip()
                                # Show all ffmpeg output for debugging
                                if decoded:
                                    output_lines.append(decoded)
                                    if first_output:
                                        print(f"[Scrcpy] ffmpeg: First output received", flush=True)
                                        first_output = False
                                    # Log ALL ffmpeg stderr output for debugging (since we're using warning level)
                                    print(f"[Scrcpy] ffmpeg stderr: {decoded}", flush=True)
                                    # Log important messages with emphasis
                                    if any(keyword in decoded.lower() for keyword in ['error', 'failed', 'cannot', 'invalid']):
                                        print(f"[Scrcpy] ffmpeg ERROR: {decoded}", flush=True)
                                    last_output_time = time.time()
                            else:
                                # No output for a while, check if ffmpeg is stuck
                                if time.time() - last_output_time > 3.0:
                                    # Check if ffmpeg is reading from stdin
                                    # This is just a warning, not an error
                                    if not hasattr(ffmpeg_process, '_warned_no_output'):
                                        print(f"[Scrcpy] ffmpeg: No output for 3 seconds, may be waiting for input from scrcpy", flush=True)
                                        # Print recent output lines for debugging
                                        if output_lines:
                                            print(f"[Scrcpy] ffmpeg: Recent output: {output_lines[-5:]}", flush=True)
                                        ffmpeg_process._warned_no_output = True
                                time.sleep(0.1)  # Small delay when no output
                        # If process exited, print all output
                        if output_lines:
                            print(f"[Scrcpy] ffmpeg: All output: {output_lines}", flush=True)
                except Exception as e:
                    print(f"[Scrcpy] Error monitoring ffmpeg stderr: {e}", flush=True)
            
            scrcpy_stderr_monitor = threading.Thread(target=monitor_scrcpy_stderr, daemon=True, name="scrcpy-stderr-monitor")
            scrcpy_stderr_monitor.start()
            
            stderr_monitor = threading.Thread(target=monitor_ffmpeg_stderr, daemon=True, name="ffmpeg-stderr-monitor")
            stderr_monitor.start()
            
            # Check if scrcpy process is still running
            if process.poll() is not None:
                exit_code = process.returncode
                stderr = ""
                try:
                    if process.stderr:
                        stderr = process.stderr.read().decode('utf-8', errors='ignore')
                except:
                    pass
                print(f"[Scrcpy] scrcpy process exited before ffmpeg setup (code {exit_code})", flush=True)
                if stderr:
                    print(f"[Scrcpy] scrcpy stderr: {stderr}", flush=True)
                if ffmpeg_process:
                    ffmpeg_process.terminate()
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return None
            
            # Wait for scrcpy to establish connection and start streaming
            # scrcpy needs time to:
            # 1. Push server to device
            # 2. Start server on device
            # 3. Establish connection
            # 4. Start encoding and outputting data
            # Based on testing, scrcpy needs at least 3-5 seconds to start outputting data
            print(f"[Scrcpy] Waiting for scrcpy to start streaming and ffmpeg to decode...", flush=True)
            print(f"[Scrcpy] FIFO path: {fifo_path}", flush=True)
            print(f"[Scrcpy] Checking if FIFO exists and is accessible...", flush=True)
            if fifo_path and os.path.exists(fifo_path):
                print(f"[Scrcpy] FIFO exists: {fifo_path}", flush=True)
                # Check FIFO permissions and type
                try:
                    import stat
                    fifo_stat = os.stat(fifo_path)
                    fifo_mode = stat.filemode(fifo_stat.st_mode)
                    print(f"[Scrcpy] FIFO stat: mode={fifo_mode}, size={fifo_stat.st_size}", flush=True)
                    # Check if it's actually a FIFO
                    if not stat.S_ISFIFO(fifo_stat.st_mode):
                        print(f"[Scrcpy] WARNING: Path exists but is not a FIFO!", flush=True)
                except Exception as e:
                    print(f"[Scrcpy] Error checking FIFO stat: {e}", flush=True)
            else:
                print(f"[Scrcpy] WARNING: FIFO does not exist: {fifo_path}", flush=True)
            
            # Wait for scrcpy to start outputting data (can take 5-10 seconds)
            # scrcpy needs time to establish connection and start encoding
            # Check if ffmpeg is receiving data by checking if it's still running and hasn't errored
            for i in range(30):  # Wait up to 15 seconds (30 * 0.5s) to allow scrcpy to start streaming
                time.sleep(0.5)
                # Check if scrcpy process is still running
                if process.poll() is not None:
                    exit_code = process.returncode
                    stderr = ""
                    try:
                        if process.stderr:
                            # Try to read remaining stderr
                            remaining_stderr = process.stderr.read()
                            if remaining_stderr:
                                stderr = remaining_stderr.decode('utf-8', errors='ignore')
                    except:
                        pass
                    print(f"[Scrcpy] scrcpy process exited during wait (code {exit_code})", flush=True)
                    if stderr:
                        print(f"[Scrcpy] scrcpy stderr (full): {stderr}", flush=True)
                    if ffmpeg_process:
                        ffmpeg_process.terminate()
                    # Clean up FIFO on error
                    if fifo_path and os.path.exists(fifo_path):
                        try:
                            os.remove(fifo_path)
                        except:
                            pass
                    return None
                # Check if ffmpeg process is still running
                if ffmpeg_process.poll() is not None:
                    exit_code = ffmpeg_process.returncode
                    stderr = ""
                    try:
                        if ffmpeg_process.stderr:
                            # Try to read remaining stderr
                            remaining_stderr = ffmpeg_process.stderr.read()
                            if remaining_stderr:
                                stderr = remaining_stderr.decode('utf-8', errors='ignore')
                    except:
                        pass
                    print(f"[Scrcpy] ffmpeg process exited during wait (code {exit_code})", flush=True)
                    if stderr:
                        print(f"[Scrcpy] ffmpeg stderr (full): {stderr}", flush=True)
                    if process:
                        process.terminate()
                    # Clean up FIFO on error
                    if fifo_path and os.path.exists(fifo_path):
                        try:
                            os.remove(fifo_path)
                        except:
                            pass
                    return None
                # Log progress every 2 seconds
                if i > 0 and i % 4 == 0:  # Every 2 seconds
                    print(f"[Scrcpy] Still waiting for scrcpy to start streaming... ({i * 0.5:.1f}s)", flush=True)
                    # Check if FIFO is being written to (on macOS/Linux)
                    if sys.platform != 'win32' and fifo_path and os.path.exists(fifo_path):
                        try:
                            import stat
                            fifo_stat = os.stat(fifo_path)
                            print(f"[Scrcpy] FIFO stat: mode={oct(fifo_stat.st_mode)}, size={fifo_stat.st_size}", flush=True)
                        except Exception as e:
                            print(f"[Scrcpy] Could not stat FIFO: {e}", flush=True)
            
            # Check scrcpy process status again
            if process.poll() is not None:
                exit_code = process.returncode
                print(f"[Scrcpy] scrcpy process exited during initialization (code {exit_code})", flush=True)
                if ffmpeg_process:
                    ffmpeg_process.terminate()
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return None
            
            # Check if ffmpeg started successfully
            if ffmpeg_process.poll() is not None:
                stderr = ""
                try:
                    if ffmpeg_process.stderr:
                        # Read remaining stderr
                        remaining = ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                        if remaining:
                            stderr = remaining
                except:
                    pass
                print(f"[Scrcpy] ffmpeg process exited immediately (code {ffmpeg_process.returncode})", flush=True)
                if stderr:
                    print(f"[Scrcpy] ffmpeg stderr: {stderr}", flush=True)
                if process:
                    process.terminate()
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return None
            
            conn = ScrcpyConnection(
                device_id=key,
                process=process,
                ffmpeg_process=ffmpeg_process,
                running=True,
                max_size=max_size,
                bit_rate=bit_rate,
                max_fps=max_fps,
                fifo_path=fifo_path
            )
            
            # Mark start time for frame reader
            conn._reader_start_time = time.time()
            conn._logged_waiting = False
            
            # Start frame reader thread
            conn.thread = threading.Thread(
                target=_scrcpy_frame_reader,
                args=(conn,),
                daemon=True,
                name=f"scrcpy-reader-{key}"
            )
            conn.thread.start()
            
            # Give frame reader a moment to start
            time.sleep(0.1)
            
            print(f"[Scrcpy] Connection established successfully for device {key}", flush=True)
            _scrcpy_connections[key] = conn
            return conn
        except FileNotFoundError:
            print("[Scrcpy] ffmpeg not found, cannot decode H.264 stream. Please install ffmpeg: https://ffmpeg.org/download.html", flush=True)
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            # Clean up FIFO on error
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.remove(fifo_path)
                except:
                    pass
            return None
        except Exception as e:
            print(f"[Scrcpy] Failed to setup decoder: {type(e).__name__}: {e}", flush=True)
            import traceback
            print(f"[Scrcpy] Traceback: {traceback.format_exc()}", flush=True)
            if process:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            # Clean up FIFO on error
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.remove(fifo_path)
                except:
                    pass
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
            
            # Clean up socket connection
            if conn.socket_conn:
                try:
                    conn.socket_conn.close()
                    print(f"[Scrcpy] Closed socket connection on port {conn.socket_port}", flush=True)
                except Exception as e:
                    print(f"[Scrcpy] Failed to close socket: {e}", flush=True)
            
            # Clean up FIFO
            if conn.fifo_path and os.path.exists(conn.fifo_path):
                try:
                    os.remove(conn.fifo_path)
                    print(f"[Scrcpy] Removed FIFO: {conn.fifo_path}", flush=True)
                except Exception as e:
                    print(f"[Scrcpy] Failed to remove FIFO {conn.fifo_path}: {e}", flush=True)
            
            del _scrcpy_connections[key]


def get_screenshot_scrcpy(device_id: str | None = None, timeout: int = 10, 
                          quality: int = 75, max_width: int = 720,
                          bit_rate: int = 2000000, max_fps: int = 60) -> Optional[Screenshot]:
    """
    Capture screenshot using scrcpy H.264 stream.
    
    This method is much faster than traditional ADB screenshot methods,
    but requires scrcpy and ffmpeg to be installed.
    
    The implementation uses scrcpy's stdout mode (--record=-) to output
    MKV video stream, which is then decoded by ffmpeg to extract frames.
    This approach is simpler and more reliable than direct socket connection.
    
    Args:
        device_id: Optional ADB device ID
        timeout: Timeout in seconds (not used for scrcpy, but used for frame wait)
        quality: JPEG quality (1-100)
        max_width: Maximum width to resize to
        bit_rate: Video bitrate in bps (default 2Mbps)
        max_fps: Maximum frame rate (default 60)
    
    Returns:
        Screenshot object or None if scrcpy is not available or connection fails
    """
    try:
        # Connect to scrcpy using FIFO mode (more reliable than stdout mode)
        # FIFO mode avoids potential deadlock issues with --record=- stdout mode
        conn = _connect_scrcpy(device_id, max_width, bit_rate, max_fps, use_socket=False)
        if not conn:
            print(f"[Scrcpy] get_screenshot_scrcpy: Failed to connect for device {device_id}", flush=True)
            return None
        
        # Wait for first frame if queue is empty
        # Based on testing, scrcpy needs 3-5 seconds to start, then ffmpeg needs time to decode
        # Total wait time: up to 10 seconds (200 attempts * 50ms)
        max_wait = 200  # 200 attempts * 50ms = 10000ms (10 seconds)
        wait_count = 0
        img = None
        
        while wait_count < max_wait:
            try:
                img = conn.frame_queue.get_nowait()
                if wait_count > 0:
                    print(f"[Scrcpy] get_screenshot_scrcpy: Got first frame after {wait_count * 50}ms", flush=True)
                break
            except queue.Empty:
                # Check if connection is still running
                if not conn.running:
                    print(f"[Scrcpy] get_screenshot_scrcpy: Connection stopped for device {device_id}", flush=True)
                    return None
                
                # Check if ffmpeg process is still running
                if conn.ffmpeg_process and conn.ffmpeg_process.poll() is not None:
                    exit_code = conn.ffmpeg_process.returncode
                    stderr = ""
                    try:
                        if conn.ffmpeg_process.stderr:
                            stderr = conn.ffmpeg_process.stderr.read().decode('utf-8', errors='ignore')
                    except:
                        pass
                    print(f"[Scrcpy] get_screenshot_scrcpy: ffmpeg process exited (code {exit_code})", flush=True)
                    if stderr:
                        print(f"[Scrcpy] get_screenshot_scrcpy: ffmpeg stderr: {stderr}", flush=True)
                    return None
                
                time.sleep(0.05)  # Wait 50ms before retry
                wait_count += 1
                
                # Log progress every second
                if wait_count > 0 and wait_count % 20 == 0:
                    print(f"[Scrcpy] get_screenshot_scrcpy: Still waiting for frame... ({wait_count * 50}ms)", flush=True)
        
        if img is None:
            print(f"[Scrcpy] get_screenshot_scrcpy: No frame available after {wait_count * 50}ms for device {device_id}", flush=True)
            return None
        
        # Process image
        width, height = img.size
        return _process_image(img, width, height, quality, max_width)
        
    except Exception as e:
        print(f"[Scrcpy] get_screenshot_scrcpy: Error: {type(e).__name__}: {e}", flush=True)
        import traceback
        print(f"[Scrcpy] get_screenshot_scrcpy: Traceback: {traceback.format_exc()}", flush=True)
        return None


def cleanup_scrcpy(device_id: str | None = None):
    """Clean up scrcpy connection for a device."""
    _disconnect_scrcpy(device_id)


def cleanup_all_scrcpy():
    """Clean up all scrcpy connections. Useful for system shutdown or cleanup."""
    with _connection_lock:
        keys = list(_scrcpy_connections.keys())
        for key in keys:
            _disconnect_scrcpy(key)
        print(f"[Scrcpy] Cleaned up {len(keys)} scrcpy connection(s)", flush=True)

