from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List
import os
from pydantic import BaseModel
from ..services.device_manager import device_manager, DeviceInfo
from ..services.screen_streamer import screen_streamer
from ..services.stream_manager import stream_manager
import json
from phone_agent.adb.device import get_installed_packages
from phone_agent.config.apps import APP_PACKAGES

router = APIRouter()

class ConnectRequest(BaseModel):
    address: str
    type: str = "adb"

class SelectDeviceRequest(BaseModel):
    device_id: str
    type: str

@router.post("/webrtc/init")
async def init_webrtc():
    token, url = device_manager.init_webrtc_session()
    return {"token": token, "url": url}

@router.get("/client/{token}", response_class=HTMLResponse)
async def device_client_page(token: str):
    # Serve the static HTML file
    # In a real app, use Jinja2Templates
    file_path = os.path.join(os.path.dirname(__file__), "../templates/mobile_client.html")
    with open(file_path, "r") as f:
        return f.read()

@router.websocket("/webrtc/connect/{token}")
async def webrtc_connect(websocket: WebSocket, token: str):
    await websocket.accept()
    try:
        # Initial handshake: Device sends its ID
        data = await websocket.receive_json()
        device_id = data.get("device_id", "Unknown WebRTC Device")
        
        success = device_manager.register_webrtc_connection(token, device_id, websocket)
        
        if success:
            await websocket.send_json({"status": "registered", "message": "Connection successful"})
            # Keep connection alive for signaling and data
            while True:
                msg_text = await websocket.receive_text()
                try:
                    msg = json.loads(msg_text)
                    if msg.get("type") == "screenshot":
                        # Store in device manager for agent access
                        device_manager.update_webrtc_device(token, {"latest_screenshot": msg["data"]})
                        
                        # Forward screenshot to frontend
                        # Check if this device is the active one before broadcasting?
                        # For now, just broadcast if it's sending data.
                        await stream_manager.broadcast({
                            "type": "screenshot",
                            "data": msg["data"]
                        })
                    # Handle other types (e.g. handshake info update)
                except json.JSONDecodeError:
                    pass
        else:
            await websocket.close(code=4001, reason="Invalid token")
            
    except WebSocketDisconnect:
        # Handle disconnect (mark as offline)
        device_manager.handle_webrtc_disconnect(token)
        # If this was the active device, stop streaming
        if device_manager.active_device_id:
            for d in device_manager.webrtc_devices:
                if d.get("token") == token and d.get("id") == device_manager.active_device_id:
                    screen_streamer.stop_streaming()
                    break

@router.get("/", response_model=List[DeviceInfo])
async def get_devices():
    return device_manager.list_all_devices()

@router.get("/{device_id}", response_model=DeviceInfo)
async def get_device(device_id: str):
    """Get a specific device by ID."""
    devices = device_manager.list_all_devices()
    for device in devices:
        if device.id == device_id:
            return device
    raise HTTPException(status_code=404, detail=f"Device {device_id} not found")

@router.post("/connect")
async def connect_device(req: ConnectRequest):
    if req.type == "webrtc":
        success = device_manager.add_webrtc_device(req.address)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to add WebRTC device")
    else:
        success, error_message = device_manager.connect_remote(req.address, req.type)
        if not success:
            # Return detailed error message from ADB/HDC connection
            detail = error_message if error_message else "Failed to connect to device"
            raise HTTPException(status_code=400, detail=detail)
    return {"status": "connected", "address": req.address}

@router.post("/wifi/enable")
async def enable_wifi_mode(device_id: str = None):
    success = device_manager.enable_tcpip(device_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to enable TCP/IP mode. Ensure USB is connected.")
    
    # Try to get IP to help the user
    ip = device_manager.get_device_ip(device_id)
    return {"status": "enabled", "ip": ip}

@router.get("/ip")
async def get_device_ip(device_id: str = None):
    ip = device_manager.get_device_ip(device_id)
    if not ip:
        raise HTTPException(status_code=404, detail="Could not determine device IP")
    return {"ip": ip}

@router.post("/select")
async def select_device(req: SelectDeviceRequest):
    # Stop streaming for previous device if any
    screen_streamer.stop_streaming()
    
    # Set new active device
    device_manager.set_active_device(req.device_id, req.type)
    
    # Start background streaming for the new device
    screen_streamer.start_streaming()
    
    return {"status": "selected", "device_id": req.device_id}

@router.delete("/{device_id}")
async def delete_device(device_id: str):
    # If deleting the active device, stop streaming
    if device_manager.active_device_id == device_id:
        screen_streamer.stop_streaming()
    
    success = device_manager.remove_device(device_id)
    if not success:
        # Not finding it might mean it's an ADB device which can't be "deleted" per se, 
        # or it just doesn't exist.
        # For ADB devices, we can't really "delete" them if they are physically connected.
        # But we'll return 404 only if we genuinely couldn't affect anything.
        # However, for UI responsiveness, returning success if it's already gone is fine.
        pass
    return {"status": "deleted", "device_id": device_id}

from pydantic import BaseModel, Field
from typing import List, Dict

# ... existing code ...

class DevicePermissions(BaseModel):
    install_app: bool = Field(default=False, description="Allow installing apps")
    payment: bool = Field(default=False, description="Allow payment operations")
    wechat_reply: bool = Field(default=False, description="Allow replying to WeChat")
    send_sms: bool = Field(default=False, description="Allow sending SMS")
    make_call: bool = Field(default=False, description="Allow making phone calls")

@router.get("/{device_id}/permissions")
async def get_device_permissions(device_id: str):
    # In a real app, this would be fetched from a DB
    # For now, we default to False (safe)
    # We can store this in device_manager if needed
    return device_manager.get_device_permissions(device_id)

@router.post("/{device_id}/permissions")
async def update_device_permissions(device_id: str, permissions: DevicePermissions):
    device_manager.set_device_permissions(device_id, permissions.dict())
    return {"status": "updated", "permissions": permissions}

@router.get("/{device_id}/apps")
async def get_device_apps(device_id: str):
    try:
        # Get User Installed (3rd party) - These are definitely "operable"
        # Note: This endpoint only returns user-installed apps, not system apps
        # System apps are fetched separately by the backend when needed for LLM
        user_packages = get_installed_packages(device_id, include_system=False)
        
        # Invert APP_PACKAGES for lookup: package -> name
        pkg_to_name = {v: k for k, v in APP_PACKAGES.items()}
        
        apps = []
        
        # Add ALL user packages only
        for pkg in user_packages:
            name = pkg_to_name.get(pkg, pkg)
            is_supported = pkg in pkg_to_name
            apps.append({"name": name, "package": pkg, "type": "supported" if is_supported else "other"})

        # Sort: Supported first, then alphabetical
        apps.sort(key=lambda x: (0 if x["type"] == "supported" else 1, x["name"]))
        
        return {"apps": apps}
    except Exception as e:
        print(f"Error fetching apps: {e}")
        return {"apps": []}
