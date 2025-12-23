"""Video streamer service for H.264 video streaming via HTTP.

This service provides real-time H.264 video streaming from scrcpy,
which is much more efficient than JPEG frame streaming.
Uses HTTP chunked transfer encoding for streaming.
"""

import asyncio
import subprocess
import time
import os
import tempfile
from typing import Optional, AsyncGenerator
from .device_manager import device_manager


class VideoStreamer:
    """Manages H.264 video streaming from scrcpy."""
    
    _instance = None
    
    def __init__(self):
        self.scrcpy_process: Optional[subprocess.Popen] = None
        
        # Stream configuration - Higher quality for better video streaming
        self.max_size = 1080  # Higher resolution (was 720)
        self.bit_rate = 8000000  # 8Mbps for better quality (was 2Mbps)
        self.max_fps = 60
        
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _check_scrcpy_available(self) -> bool:
        """Check if scrcpy is available."""
        try:
            result = subprocess.run(
                ["scrcpy", "--version"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    async def generate_mp4_stream(self, device_id: str | None = None) -> AsyncGenerator[bytes, None]:
        """
        Generate fragmented MP4 video stream from scrcpy.
        Uses ffmpeg to convert H.264 to fragmented MP4 for browser playback via MSE API.
        Uses HTTP chunked transfer encoding for streaming.
        """
        print(f"[VideoStreamer] generate_mp4_stream called, device_id={device_id}", flush=True)
        
        if not self._check_scrcpy_available():
            print("[VideoStreamer] ERROR: scrcpy not available, cannot stream video", flush=True)
            return
        
        if not device_id:
            device_id = device_manager.active_device_id
            print(f"[VideoStreamer] Using active device_id: {device_id}", flush=True)
        
        if not device_id:
            print("[VideoStreamer] ERROR: No device available", flush=True)
            return
        
        print(f"[VideoStreamer] Starting video stream for device: {device_id}", flush=True)
        
        scrcpy_process = None
        ffmpeg_process = None
        fifo_path = None
        
        try:
            # Create named pipe (FIFO) for better data flow control
            # FIFO mode avoids potential deadlock issues with --record=- stdout mode
            fifo_path = os.path.join(tempfile.gettempdir(), f"scrcpy_video_{device_id or 'default'}_{os.getpid()}.fifo")
            
            # Remove existing FIFO if any
            if os.path.exists(fifo_path):
                os.remove(fifo_path)
            
            # Create FIFO
            try:
                os.mkfifo(fifo_path)
                print(f"[VideoStreamer] Created FIFO: {fifo_path}", flush=True)
            except OSError as e:
                print(f"[VideoStreamer] Failed to create FIFO {fifo_path}: {e}", flush=True)
                return
            
            # Build scrcpy command with FIFO
            scrcpy_cmd = ["scrcpy"]
            
            if device_id:
                scrcpy_cmd.extend(["-s", device_id])
            
            scrcpy_cmd.extend([
                "--max-size", str(self.max_size),
                "--video-bit-rate", str(self.bit_rate),  # Use --video-bit-rate for scrcpy 3.3.4+
                "--max-fps", str(self.max_fps),
                "--record", fifo_path,  # Output to named pipe (FIFO)
                "--record-format=mkv",  # Required format for --record in scrcpy 3.3.4+
                "--no-window",  # Disable window (implies --no-video-playback in scrcpy 3.3.4+)
                "--no-control",  # Don't accept control
                "--no-audio",  # No audio
                # Don't specify --video-encoder, let scrcpy auto-detect the best encoder
            ])
            
            print(f"[VideoStreamer] Starting video stream with settings: max_size={self.max_size}, bit_rate={self.bit_rate/1000000:.1f}Mbps, max_fps={self.max_fps}", flush=True)
            print(f"[VideoStreamer] Starting scrcpy with FIFO: {' '.join(scrcpy_cmd)}", flush=True)
            
            # Start scrcpy process
            scrcpy_process = subprocess.Popen(
                scrcpy_cmd,
                stdout=subprocess.PIPE,  # Still capture stdout for stderr messages
                stderr=subprocess.PIPE,
                bufsize=0,
                env=dict(os.environ, PYTHONUNBUFFERED='1')
            )
            
            # Give scrcpy time to start and establish connection
            await asyncio.sleep(3)  # Wait longer for scrcpy to establish connection
            
            if scrcpy_process.poll() is not None:
                stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                print(f"[VideoStreamer] ERROR: scrcpy process exited immediately: {stderr}", flush=True)
                # Read any remaining stderr
                if scrcpy_process.stderr:
                    remaining_stderr = scrcpy_process.stderr.read().decode()
                    if remaining_stderr:
                        print(f"[VideoStreamer] scrcpy stderr: {remaining_stderr}", flush=True)
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return
            
            # Check if scrcpy is actually outputting data
            print(f"[VideoStreamer] scrcpy process started (PID: {scrcpy_process.pid}), waiting for data...", flush=True)
            
            # Use ffmpeg to convert H.264 to fragmented MP4
            # Fragmented MP4 is required for MSE API playback
            # Read from FIFO instead of stdin
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", fifo_path,  # Read from FIFO (named pipe)
                "-c:v", "copy",  # Copy video codec (H.264)
                "-f", "mp4",  # MP4 format
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",  # Fragmented MP4 for streaming
                "-reset_timestamps", "1",  # Reset timestamps for streaming
                "-loglevel", "warning",  # Show warnings to debug issues
                "-flush_packets", "1",  # Force immediate flushing
                "-fflags", "nobuffer+genpts",  # Disable buffering and generate PTS
                "-flags", "low_delay",  # Low delay flag
                "-analyzeduration", "1000000",  # Reduce analysis time
                "-probesize", "1000000",  # Reduce probe size
                "pipe:1"  # Output to stdout
            ]
            
            print(f"[VideoStreamer] Starting ffmpeg to read from FIFO: {' '.join(ffmpeg_cmd)}", flush=True)
            
            # IMPORTANT: Start ffmpeg AFTER scrcpy has started
            # FIFO behavior: 
            # - If only reader opens FIFO, it blocks until writer opens
            # - If only writer opens FIFO, it blocks until reader opens
            # - Both need to be open for data to flow
            # scrcpy will open FIFO when it's ready to start recording
            # ffmpeg will block on opening FIFO until scrcpy opens it for writing
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Give ffmpeg time to attempt opening the FIFO
            # This will block until scrcpy opens the FIFO for writing
            print(f"[VideoStreamer] Waiting for scrcpy to open FIFO (ffmpeg will block until then)...", flush=True)
            await asyncio.sleep(2)
            
            # Check if scrcpy is still running (it should be)
            if scrcpy_process.poll() is not None:
                stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                print(f"[VideoStreamer] ERROR: scrcpy process exited before ffmpeg could read: {stderr}", flush=True)
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return
            
            # Check if ffmpeg process is still running
            if ffmpeg_process.poll() is not None:
                stderr = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                print(f"[VideoStreamer] ERROR: ffmpeg process exited immediately: {stderr}", flush=True)
                # Also check scrcpy status
                if scrcpy_process.poll() is not None:
                    scrcpy_stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                    print(f"[VideoStreamer] scrcpy also exited with code {scrcpy_process.returncode}: {scrcpy_stderr}", flush=True)
                # Clean up FIFO on error
                if fifo_path and os.path.exists(fifo_path):
                    try:
                        os.remove(fifo_path)
                    except:
                        pass
                return
            
            print(f"[VideoStreamer] ffmpeg process started (PID: {ffmpeg_process.pid}), both processes running, starting to stream data...", flush=True)
            
            # Stream MP4 data
            chunk_size = 8192  # 8KB chunks
            chunks_yielded = 0
            no_data_count = 0
            max_no_data_count = 50  # Allow up to 5 seconds of no data (50 * 0.1s)
            try:
                while ffmpeg_process.poll() is None:
                    # Check if scrcpy is still running
                    if scrcpy_process.poll() is not None:
                        stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                        print(f"[VideoStreamer] ERROR: scrcpy process exited (code {scrcpy_process.returncode}): {stderr}", flush=True)
                        break
                    
                    # Use non-blocking read with timeout
                    try:
                        chunk = await asyncio.wait_for(
                            asyncio.to_thread(ffmpeg_process.stdout.read, chunk_size),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        print(f"[VideoStreamer] Timeout reading from ffmpeg stdout (no data for 5s)", flush=True)
                        # Check process status
                        if ffmpeg_process.poll() is not None:
                            stderr = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                            print(f"[VideoStreamer] ffmpeg process exited during timeout: {stderr}", flush=True)
                            break
                        # Check scrcpy status
                        if scrcpy_process.poll() is not None:
                            stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                            print(f"[VideoStreamer] scrcpy process exited during timeout (code {scrcpy_process.returncode}): {stderr}", flush=True)
                            break
                        # Check ffmpeg stderr for any warnings/errors
                        if ffmpeg_process.stderr:
                            try:
                                # Try to read stderr without blocking
                                import select
                                if select.select([ffmpeg_process.stderr], [], [], 0)[0]:
                                    stderr_line = ffmpeg_process.stderr.readline().decode().strip()
                                    if stderr_line:
                                        print(f"[VideoStreamer] ffmpeg stderr: {stderr_line}", flush=True)
                            except:
                                pass
                        # Check scrcpy stderr
                        if scrcpy_process.stderr:
                            try:
                                import select
                                if select.select([scrcpy_process.stderr], [], [], 0)[0]:
                                    stderr_line = scrcpy_process.stderr.readline().decode().strip()
                                    if stderr_line:
                                        print(f"[VideoStreamer] scrcpy stderr: {stderr_line}", flush=True)
                            except:
                                pass
                        # Continue to check again
                        continue
                    
                    if not chunk:
                        # No data available, check if process is still running
                        if ffmpeg_process.poll() is not None:
                            stderr = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                            print(f"[VideoStreamer] ffmpeg process exited: {stderr}", flush=True)
                            break
                        # Process still running but no data - wait a bit
                        no_data_count += 1
                        if no_data_count >= max_no_data_count:
                            print(f"[VideoStreamer] WARNING: No data received for {max_no_data_count * 0.1}s, stopping stream", flush=True)
                            break
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Reset no_data_count when we receive data
                    no_data_count = 0
                    chunks_yielded += 1
                    if chunks_yielded == 1:
                        print(f"[VideoStreamer] ✅ First chunk received ({len(chunk)} bytes), streaming started", flush=True)
                    elif chunks_yielded % 100 == 0:
                        print(f"[VideoStreamer] Streaming: {chunks_yielded} chunks sent", flush=True)
                    yield chunk
            except asyncio.TimeoutError:
                print(f"[VideoStreamer] Timeout waiting for data from ffmpeg", flush=True)
                # Check if processes are still running
                if ffmpeg_process.poll() is not None:
                    stderr = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                    print(f"[VideoStreamer] ffmpeg process exited during timeout: {stderr}", flush=True)
                if scrcpy_process.poll() is not None:
                    stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                    print(f"[VideoStreamer] scrcpy process exited during timeout: {stderr}", flush=True)
            except Exception as e:
                print(f"[VideoStreamer] Error reading stream: {e}", flush=True)
                import traceback
                print(f"[VideoStreamer] Traceback: {traceback.format_exc()}", flush=True)
                # Check process status
                if ffmpeg_process.poll() is not None:
                    stderr = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                    print(f"[VideoStreamer] ffmpeg process status: exited with code {ffmpeg_process.returncode}, stderr: {stderr}", flush=True)
                if scrcpy_process.poll() is not None:
                    stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                    print(f"[VideoStreamer] scrcpy process status: exited with code {scrcpy_process.returncode}, stderr: {stderr}", flush=True)
        except FileNotFoundError:
            print("[VideoStreamer] ffmpeg not found, cannot convert to MP4", flush=True)
        except Exception as e:
            print(f"[VideoStreamer] Failed to start streaming: {e}", flush=True)
            import traceback
            print(f"[VideoStreamer] Traceback: {traceback.format_exc()}", flush=True)
        finally:
            # Clean up processes
            if ffmpeg_process:
                try:
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=2)
                except:
                    try:
                        ffmpeg_process.kill()
                    except:
                        pass
            
            if scrcpy_process:
                try:
                    scrcpy_process.terminate()
                    scrcpy_process.wait(timeout=2)
                except:
                    try:
                        scrcpy_process.kill()
                    except:
                        pass
            
            # Clean up FIFO
            if fifo_path and os.path.exists(fifo_path):
                try:
                    os.remove(fifo_path)
                    print(f"[VideoStreamer] Cleaned up FIFO: {fifo_path}", flush=True)
                except Exception as e:
                    print(f"[VideoStreamer] Failed to remove FIFO {fifo_path}: {e}", flush=True)
    
    def update_settings(self, max_size: int = None, bit_rate: int = None, max_fps: int = None):
        """Update streaming settings."""
        if max_size:
            self.max_size = max_size
        if bit_rate:
            self.bit_rate = bit_rate
        if max_fps:
            self.max_fps = max_fps


video_streamer = VideoStreamer.get_instance()

