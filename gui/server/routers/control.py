import hashlib
from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
from typing import Optional
from ..services.device_manager import device_manager
from ..services.screen_streamer import screen_streamer
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
            print(f"Auto-selected device: {device_id} ({d_type})")
        else:
            raise HTTPException(status_code=400, detail="No device selected and no devices connected")
        
    # Set correct context for the factory
    # Check if WebRTC
    is_webrtc = any(d['id'] == device_id for d in device_manager.webrtc_devices)
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
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/home")
async def device_home():
    factory, device_id = _get_device_module()
    try:
        factory.home(device_id=device_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/back")
async def device_back():
    factory, device_id = _get_device_module()
    try:
        factory.back(device_id=device_id)
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
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/swipe")
async def device_swipe(req: SwipeRequest):
    factory, device_id = _get_device_module()
    try:
        factory.swipe(req.x1, req.y1, req.x2, req.y2, duration_ms=req.duration, device_id=device_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream/settings")
async def update_stream_settings(req: StreamSettingsRequest):
    screen_streamer.update_settings(req.quality, req.max_width, req.fps)
    return {"status": "updated", "settings": req.dict(exclude_none=True)}

@router.get("/stream/latest")
async def get_latest_frame(request: Request):
    # Asynchronously capture frame on demand (in thread pool)
    frame, status = await screen_streamer.capture_frame()
    
    if frame:
        # Calculate ETag
        frame_hash = hashlib.md5(frame).hexdigest()
        client_etag = request.headers.get("if-none-match")
        
        # If client has this frame (ETag matches), return 304 Not Modified
        if client_etag and client_etag == frame_hash:
            return Response(status_code=304)
            
        # Otherwise return new data (200)
        return Response(
            content=frame, 
            media_type="image/jpeg", 
            headers={
                "Cache-Control": "no-cache",
                "ETag": frame_hash,
                "X-Timestamp": str(int(screen_streamer.latest_frame_ts * 1000))
            }
        )
    elif status == 'unchanged':
        # Return 204 No Content to indicate success but no new data
        # Frontend should handle this by waiting and retrying
        return Response(status_code=204)
    elif status == 'locked':
        # Return 423 Locked
        raise HTTPException(status_code=423, detail="Device is locked")
    else:
        # Return a 503 Service Unavailable or 500 so frontend knows to retry
        raise HTTPException(status_code=503, detail="Capture failed")
