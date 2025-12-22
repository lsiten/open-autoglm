import hashlib
import gzip
import asyncio
import time
from fastapi import APIRouter, HTTPException, Response, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from ..services.device_manager import device_manager
from ..services.screen_streamer import screen_streamer
from ..services.stream_manager import stream_manager
from ..services.recording_manager import recording_manager
from phone_agent.device_factory import get_device_factory, set_device_type, DeviceType

router = APIRouter()

class StreamSettingsRequest(BaseModel):
    quality: Optional[int] = None
    max_width: Optional[int] = None
    fps: Optional[int] = None

class TapRequest(BaseModel):
    x: float
    y: float

class SwipeRequest(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    duration: int = 500

def _get_device_module():
    device_id = device_manager.active_device_id
    if not device_id:
        # Try to auto-select if devices are available (e.g. after backend restart)
        devices = device_manager.list_all_devices()
        if devices:
            # Auto-select the first one
            device = devices[0]
            device_id = device.id # DeviceInfo object, not dict
            d_type = device.type
            device_manager.set_active_device(device_id, d_type)
            # Start streaming for auto-selected device
            screen_streamer.start_streaming()
            print(f"Auto-selected device: {device_id} ({d_type})")
        else:
            raise HTTPException(status_code=400, detail="No device selected and no devices connected")
        
    # Set correct context for the factory
    # Check if WebRTC (safely handle missing keys)
    is_webrtc = False
    try:
        is_webrtc = any(d.get('id') == device_id for d in device_manager.webrtc_devices)
    except (KeyError, TypeError, AttributeError) as e:
        print(f"[_get_device_module] Error checking WebRTC devices: {e}", flush=True)
        is_webrtc = False
    
    if is_webrtc:
        set_device_type(DeviceType.WEBRTC)
    elif device_manager.active_device_type == "hdc":
        set_device_type(DeviceType.HDC)
    else:
        set_device_type(DeviceType.ADB)
        
    return get_device_factory(), device_id

@router.post("/tap")
async def device_tap(req: TapRequest):
    factory, device_id = _get_device_module()
    try:
        factory.tap(req.x, req.y, device_id=device_id)
        
        # Record action if recording is active
        if recording_manager.is_recording(device_id):
            recording_manager.record_action(device_id, "tap", {
                "x": req.x,
                "y": req.y
            })
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/home")
async def device_home():
    factory, device_id = _get_device_module()
    try:
        factory.home(device_id=device_id)
        
        # Record action if recording is active
        if recording_manager.is_recording(device_id):
            recording_manager.record_action(device_id, "home", {})
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/back")
async def device_back():
    factory, device_id = _get_device_module()
    try:
        factory.back(device_id=device_id)
        
        # Record action if recording is active
        if recording_manager.is_recording(device_id):
            recording_manager.record_action(device_id, "back", {})
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/recent")
async def device_recent():
    factory, device_id = _get_device_module()
    try:
        # Check if factory supports recent (it should now)
        if hasattr(factory, "recent"):
            factory.recent(device_id=device_id)
        else:
             # Fallback if using a module that doesn't support it (e.g. HDC might not yet)
             raise NotImplementedError("Recent apps not supported on this device type")
        
        # Record action if recording is active
        if recording_manager.is_recording(device_id):
            recording_manager.record_action(device_id, "recent", {})
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/swipe")
async def device_swipe(req: SwipeRequest):
    factory, device_id = _get_device_module()
    try:
        factory.swipe(req.x1, req.y1, req.x2, req.y2, duration_ms=req.duration, device_id=device_id)
        
        # Record action if recording is active
        if recording_manager.is_recording(device_id):
            recording_manager.record_action(device_id, "swipe", {
                "x1": req.x1,
                "y1": req.y1,
                "x2": req.x2,
                "y2": req.y2,
                "duration": req.duration
            })
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/settings")
async def update_stream_settings(req: StreamSettingsRequest):
    screen_streamer.update_settings(req.quality, req.max_width, req.fps)
    return {"status": "updated", "settings": req.dict(exclude_none=True)}

@router.get("/stream/latest")
async def get_latest_frame(request: Request):
    # Ensure background streaming is started for better performance
    # If not streaming and device is available, start streaming and wait for first frame
    if not screen_streamer.is_streaming:
        device_id = device_manager.active_device_id
        if device_id:
            screen_streamer.start_streaming()
            # Wait for first frame capture (max 1 second, check every 100ms)
            for _ in range(10):
                await asyncio.sleep(0.1)
                with screen_streamer._frame_lock:
                    if screen_streamer.latest_frame and screen_streamer.latest_frame_ts > 0:
                        break
    
    # Asynchronously capture frame on demand (in thread pool)
    # If streaming is active, this will return cached frame immediately
    frame, status = await screen_streamer.capture_frame()
    
    if frame:
        # Calculate ETag
        frame_hash = hashlib.md5(frame).hexdigest()
        client_etag = request.headers.get("if-none-match")
        
        # If client has this frame (ETag matches), return 304 Not Modified
        if client_etag and client_etag == frame_hash:
            return Response(status_code=304)
        
        # Check if client supports gzip compression
        accept_encoding = request.headers.get("accept-encoding", "").lower()
        use_gzip = "gzip" in accept_encoding
        
        # Compress frame data if client supports gzip
        content = frame
        headers = {
            "Cache-Control": "no-cache",
            "ETag": frame_hash,
            "X-Timestamp": str(int(screen_streamer.latest_frame_ts * 1000))
        }
        
        if use_gzip:
            # Compress frame data with gzip
            content = gzip.compress(frame, compresslevel=6)  # Level 6 is a good balance
            headers["Content-Encoding"] = "gzip"
            headers["Vary"] = "Accept-Encoding"  # Important for caching
            
        # Return compressed or uncompressed data
        return Response(
            content=content, 
            media_type="image/jpeg", 
            headers=headers
        )
    elif status == 'unchanged':
        # Even if content unchanged, return the frame with updated timestamp
        # This ensures real-time frame delivery - every captured frame is available
        # Frontend can use timestamp to determine if it's a new frame
        if screen_streamer.latest_frame:
            frame_hash = hashlib.md5(screen_streamer.latest_frame).hexdigest()
            client_etag = request.headers.get("if-none-match")
            
            if client_etag and client_etag == frame_hash:
                return Response(status_code=304)
            
            accept_encoding = request.headers.get("accept-encoding", "").lower()
            use_gzip = "gzip" in accept_encoding
            
            content = screen_streamer.latest_frame
            headers = {
                "Cache-Control": "no-cache",
                "ETag": frame_hash,
                "X-Timestamp": str(int(screen_streamer.latest_frame_ts * 1000))
            }
            
            if use_gzip:
                content = gzip.compress(screen_streamer.latest_frame, compresslevel=6)
                headers["Content-Encoding"] = "gzip"
                headers["Vary"] = "Accept-Encoding"
            
            return Response(
                content=content,
                media_type="image/jpeg",
                headers=headers
            )
        # Fallback to 204 if no frame available
        return Response(status_code=204)
    elif status == 'locked':
        # Return 423 Locked
        raise HTTPException(status_code=423, detail="Device is locked")
    else:
        # Return a 503 Service Unavailable or 500 so frontend knows to retry
        raise HTTPException(status_code=503, detail="Capture failed")

async def _generate_mjpeg_stream() -> AsyncGenerator[bytes, None]:
    """
    Generate MJPEG stream by continuously sending JPEG frames.
    Each frame is prefixed with MJPEG boundary markers.
    MJPEG format: multipart/x-mixed-replace with boundary markers.
    """
    boundary = b'--frame\r\n'
    last_frame_hash = None
    consecutive_errors = 0
    max_consecutive_errors = 20
    target_fps = screen_streamer.fps if screen_streamer.fps > 0 else 60.0
    frame_interval = 1.0 / target_fps
    
    # Check if device is available before starting stream
    if not device_manager.active_device_id:
        print("[MJPEG Stream] No device selected, cannot start stream", flush=True)
        # Yield empty response and exit
        yield b''
        return  # Exit early if no device
    
    # Ensure streaming is started
    if not screen_streamer.is_streaming:
        screen_streamer.start_streaming()
        # Double-check that streaming actually started
        if not screen_streamer.is_streaming:
            print("[MJPEG Stream] Failed to start streaming, no device available", flush=True)
            # Yield empty response and exit
            yield b''
            return
    
    while True:
        try:
            loop_start = time.time()
            
            # Check if device is still available
            if not device_manager.active_device_id:
                print("[MJPEG Stream] Device disconnected, stopping stream", flush=True)
                break
            
            # Get latest frame
            frame, status = await screen_streamer.capture_frame()
            
            if frame:
                # Always send frame to maintain continuous stream, even if unchanged
                # This ensures browser receives regular updates and doesn't timeout
                frame_hash = hashlib.md5(frame).hexdigest()
                if frame_hash != last_frame_hash:
                    last_frame_hash = frame_hash
                    consecutive_errors = 0
                
                # Send MJPEG frame with proper headers
                # Format: --boundary\r\nContent-Type: image/jpeg\r\nContent-Length: <size>\r\n\r\n<data>\r\n
                frame_data = (
                    boundary +
                    b'Content-Type: image/jpeg\r\n' +
                    b'Content-Length: ' + str(len(frame)).encode() + b'\r\n\r\n' +
                    frame +
                    b'\r\n'
                )
                yield frame_data
            elif status == 'unchanged':
                # Frame unchanged but we have a cached frame, send it to maintain stream continuity
                # Get the cached frame
                with screen_streamer._frame_lock:
                    cached_frame = screen_streamer.latest_frame
                    if cached_frame:
                        frame_data = (
                            boundary +
                            b'Content-Type: image/jpeg\r\n' +
                            b'Content-Length: ' + str(len(cached_frame)).encode() + b'\r\n\r\n' +
                            cached_frame +
                            b'\r\n'
                        )
                        yield frame_data
                    else:
                        # No cached frame, wait before next check
                        await asyncio.sleep(frame_interval)
            elif status == 'locked':
                # Device locked, wait longer
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    break
                await asyncio.sleep(1.0)
            else:
                # Error, wait and retry
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    break
                await asyncio.sleep(0.1)
            
            # Maintain target FPS
            elapsed = time.time() - loop_start
            remaining = frame_interval - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[MJPEG Stream] Error: {e}", flush=True)
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                break
            await asyncio.sleep(0.1)

@router.get("/stream/mjpeg")
async def get_mjpeg_stream():
    """
    MJPEG streaming endpoint for continuous frame delivery.
    Browser can display this directly using <img src="/api/control/stream/mjpeg">
    """
    return StreamingResponse(
        _generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Connection": "keep-alive"
        }
    )

@router.websocket("/stream/ws")
async def stream_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for frame streaming.
    Reduces log noise by using long-lived connection instead of HTTP polling.
    """
    await stream_manager.connect_frame_stream(websocket)
    
    # Ensure streaming is started
    if not screen_streamer.is_streaming:
        screen_streamer.start_streaming()
    
    try:
        # Keep connection alive and handle any incoming messages
        while True:
            try:
                # Wait for any message from client (ping/pong or close)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Client can send ping messages to keep connection alive
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        stream_manager.disconnect_frame_stream(websocket)
