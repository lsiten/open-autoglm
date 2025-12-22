"""Video streamer service for H.264 video streaming via HTTP.

This service provides real-time H.264 video streaming from scrcpy,
which is much more efficient than JPEG frame streaming.
Uses HTTP chunked transfer encoding for streaming.
"""

import asyncio
import subprocess
import time
from typing import Optional, AsyncGenerator
from .device_manager import device_manager


class VideoStreamer:
    """Manages H.264 video streaming from scrcpy."""
    
    _instance = None
    
    def __init__(self):
        self.scrcpy_process: Optional[subprocess.Popen] = None
        
        # Stream configuration
        self.max_size = 720
        self.bit_rate = 2000000  # 2Mbps
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
        if not self._check_scrcpy_available():
            print("[VideoStreamer] scrcpy not available, cannot stream video", flush=True)
            return
        
        if not device_id:
            device_id = device_manager.active_device_id
        
        if not device_id:
            print("[VideoStreamer] No device available", flush=True)
            return
        
        scrcpy_process = None
        ffmpeg_process = None
        
        try:
            # Build scrcpy command
            scrcpy_cmd = ["scrcpy"]
            
            if device_id:
                scrcpy_cmd.extend(["-s", device_id])
            
            scrcpy_cmd.extend([
                "--max-size", str(self.max_size),
                "--video-bit-rate", str(self.bit_rate),  # Use --video-bit-rate for scrcpy 3.3.4+
                "--max-fps", str(self.max_fps),
                "--record=-",  # Output to stdout
                "--record-format=mkv",  # Required format for --record=- in scrcpy 3.3.4+
                "--no-window",  # Disable window (implies --no-video-playback in scrcpy 3.3.4+)
                "--no-control",  # Don't accept control
                "--no-audio",  # No audio
                "--encoder", "h264",  # Use H.264 encoder
            ])
            
            # Start scrcpy process
            scrcpy_process = subprocess.Popen(
                scrcpy_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Give it time to start
            await asyncio.sleep(1)
            
            if scrcpy_process.poll() is not None:
                stderr = scrcpy_process.stderr.read().decode() if scrcpy_process.stderr else ""
                print(f"[VideoStreamer] scrcpy process exited: {stderr}", flush=True)
                return
            
            # Use ffmpeg to convert H.264 to fragmented MP4
            # Fragmented MP4 is required for MSE API playback
            ffmpeg_cmd = [
                "ffmpeg",
                "-i", "pipe:0",  # Read from stdin (scrcpy output)
                "-c:v", "copy",  # Copy video codec (H.264)
                "-f", "mp4",  # MP4 format
                "-movflags", "frag_keyframe+empty_moov",  # Fragmented MP4 for streaming
                "-reset_timestamps", "1",  # Reset timestamps for streaming
                "pipe:1"  # Output to stdout
            ]
            
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=scrcpy_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            # Close scrcpy stdout in this process (ffmpeg will read it)
            scrcpy_process.stdout.close()
            
            # Stream MP4 data
            chunk_size = 8192  # 8KB chunks
            try:
                while ffmpeg_process.poll() is None:
                    chunk = ffmpeg_process.stdout.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            except Exception as e:
                print(f"[VideoStreamer] Error reading stream: {e}", flush=True)
        except FileNotFoundError:
            print("[VideoStreamer] ffmpeg not found, cannot convert to MP4", flush=True)
        except Exception as e:
            print(f"[VideoStreamer] Failed to start streaming: {e}", flush=True)
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
    
    def update_settings(self, max_size: int = None, bit_rate: int = None, max_fps: int = None):
        """Update streaming settings."""
        if max_size:
            self.max_size = max_size
        if bit_rate:
            self.bit_rate = bit_rate
        if max_fps:
            self.max_fps = max_fps


video_streamer = VideoStreamer.get_instance()

